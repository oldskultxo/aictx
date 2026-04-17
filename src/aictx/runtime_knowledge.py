from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from .runtime_io import (
    file_md5,
    file_mtime,
    mtime_changed,
    now_iso,
    relative_posix,
    slugify,
    truncate_words,
    write_text,
)
from .runtime_versioning import compat_version_payload


def _cr():
    from . import core_runtime as cr

    return cr


class HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.in_pre = False
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {'script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg'}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {'title'}:
            self.in_title = True
        if tag in {'pre', 'code'}:
            self.in_pre = True
            self.parts.append('\n```text\n')
        elif tag in {'br'}:
            self.parts.append('\n')
        elif tag in {'p', 'div', 'section', 'article', 'main', 'tr'}:
            self.parts.append('\n\n')
        elif tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}:
            level = min(int(tag[1]), 6)
            self.parts.append(f"\n\n{'#' * level} ")
        elif tag == 'li':
            self.parts.append('\n- ')

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {'script', 'style', 'nav', 'footer', 'header', 'noscript', 'svg'}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if self.skip_depth:
            return
        if tag == 'title':
            self.in_title = False
        if tag in {'pre', 'code'}:
            self.parts.append('\n```\n')
            self.in_pre = False
        elif tag in {'p', 'div', 'section', 'article', 'main', 'table'}:
            self.parts.append('\n\n')

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        value = html.unescape(data)
        if not value.strip():
            if self.in_pre:
                self.parts.append(value)
            return
        if self.in_title:
            self.title_parts.append(re.sub(r'\s+', ' ', value).strip())
        if self.in_pre:
            self.parts.append(value)
        else:
            self.parts.append(re.sub(r'\s+', ' ', value).strip() + ' ')

    def result(self) -> tuple[str, str]:
        text = ''.join(self.parts)
        text = re.sub(r'\n{3,}', '\n\n', text)
        lines = [line.rstrip() for line in text.splitlines()]
        compact_lines = []
        previous_blank = False
        for line in lines:
            blank = not line.strip()
            if blank and previous_blank:
                continue
            compact_lines.append(line)
            previous_blank = blank
        title = re.sub(r'\s+', ' ', ' '.join(self.title_parts)).strip()
        return '\n'.join(compact_lines).strip(), title


def load_mod_manifest(root: Path) -> dict[str, Any]:
    cr = _cr()
    return cr.read_json(root / 'mod.json', {})


def save_mod_manifest(root: Path, manifest: dict[str, Any]) -> None:
    cr = _cr()
    manifest['manifest_path'] = (root / 'mod.json').as_posix()
    manifest['library_root'] = root.as_posix()
    manifest['updated_at'] = now_iso()
    cr.write_json(root / 'mod.json', manifest)


def default_mod_state() -> dict[str, Any]:
    return {'version': 2, 'last_processed': None, 'processed_docs': {}, 'referenced_files': {}}


def load_mod_state(root: Path) -> dict[str, Any]:
    cr = _cr()
    state = cr.read_json(root / 'manifests' / 'state.json', default_mod_state())
    state.setdefault('version', 2)
    state.setdefault('last_processed', None)
    state.setdefault('processed_docs', {})
    state.setdefault('referenced_files', {})
    return state


def save_mod_state(root: Path, state: dict[str, Any]) -> None:
    cr = _cr()
    state['version'] = 2
    cr.write_json(root / 'manifests' / 'state.json', state)


def references_template_text() -> str:
    return (
        '# References Template\n\n'
        'List one file path per line to ingest knowledge from files that live outside the mod inbox.\n\n'
        '- Lines starting with `#` are comments.\n'
        '- A comment immediately before a path is stored as the label for that file.\n'
        '- Relative paths are resolved from the engine root.\n'
        '- Supported referenced formats: `.md`, `.txt`, `.html`, `.htm`, `.pdf`, `.sql`, `.xml`, `.json`, `.yaml`, `.yml`, `.py`, `.csv`.\n\n'
        'Example:\n\n'
        '```md\n'
        '# API schema\n'
        'docs/api/openapi.yaml\n\n'
        '# SQL views\n'
        '/absolute/path/to/reporting_view.sql\n'
        '```\n'
    )


def references_stub_text(mod_id: str) -> str:
    return (
        f'# Knowledge References — {slugify(mod_id)}\n\n'
        '# Add one absolute or repo-relative path per line.\n'
        '# See ../../REFERENCES_TEMPLATE.md for the full format.\n'
        '# Example:\n'
        '# /absolute/path/to/file.sql\n'
        '# docs/architecture/api.yaml\n'
    )


def ensure_references_template() -> None:
    cr = _cr()
    template_path = cr.LIBRARY_DIR / 'REFERENCES_TEMPLATE.md'
    if not template_path.exists():
        write_text(template_path, references_template_text())


def ensure_remote_manifest(root: Path) -> None:
    manifest_path = root / 'remote_sources' / 'manifest.json'
    if not manifest_path.exists():
        _cr().write_json(manifest_path, {'version': 1, 'sources': []})


def remote_manifest_path(root: Path) -> Path:
    return root / 'remote_sources' / 'manifest.json'


def load_remote_sources_manifest(root: Path) -> dict[str, Any]:
    cr = _cr()
    ensure_remote_manifest(root)
    manifest = cr.read_json(remote_manifest_path(root), {'version': 1, 'sources': []})
    manifest.setdefault('version', 1)
    manifest.setdefault('sources', [])
    return manifest


def save_remote_sources_manifest(root: Path, manifest: dict[str, Any]) -> None:
    manifest['version'] = 1
    _cr().write_json(remote_manifest_path(root), manifest)


def should_process_inbox_file(path: Path) -> bool:
    cr = _cr()
    return path.is_file() and path.name != 'references.md' and path.suffix.lower() in cr.SUPPORTED_INBOX_EXTENSIONS


def resolve_reference_path(raw_path: str) -> Path:
    cr = _cr()
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate.resolve()
    return (cr.BASE / raw_path).resolve()


def parse_references_file(path: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not path.exists():
        return references
    current_label: str | None = None
    for raw_line in path.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = raw_line.strip()
        if not line:
            current_label = None
            continue
        if line.startswith('#'):
            current_label = line.lstrip('#').strip() or None
            continue
        resolved = resolve_reference_path(line)
        references.append({'path': resolved, 'raw_path': line, 'label': current_label})
    return references


def sanitize_source_name(value: str, fallback: str = 'source') -> str:
    cleaned = slugify(Path(value).stem if value else fallback)
    return cleaned[:80] or fallback


def delete_artifact_paths(root: Path, paths: list[str]) -> None:
    for raw_path in paths:
        if not raw_path:
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = root / raw_path
        if candidate.exists() and candidate.is_file():
            candidate.unlink()


def invalidate_source_artifacts(root: Path, previous: dict[str, Any]) -> None:
    delete_artifact_paths(root, list(previous.get('note_files', [])))
    delete_artifact_paths(root, list(previous.get('summary_files', [])))
    delete_artifact_paths(root, [previous.get('processed_path', ''), previous.get('manifest_path', '')])


def rebuild_mod_indices(root: Path, state: dict[str, Any]) -> dict[str, list[str]]:
    cr = _cr()
    topic_index: dict[str, list[str]] = defaultdict(list)
    keyword_index: dict[str, list[str]] = defaultdict(list)
    notes: list[str] = []
    summaries: list[str] = []
    for bucket_name in ['processed_docs', 'referenced_files']:
        for entry in state.get(bucket_name, {}).values():
            if entry.get('status') != 'processed':
                continue
            for path in entry.get('note_files', []):
                notes.append(path)
            for path in entry.get('summary_files', []):
                summaries.append(path)
            for keyword in entry.get('keywords', [])[:8]:
                for path in entry.get('note_files', [])[:1]:
                    if path not in topic_index[keyword]:
                        topic_index[keyword].append(path)
                for path in entry.get('summary_files', [])[:1]:
                    if path not in keyword_index[keyword]:
                        keyword_index[keyword].append(path)
            for section in entry.get('sections', []):
                for keyword in section.get('keywords', [])[:10]:
                    note_path = section.get('note_path')
                    summary_path = section.get('summary_path')
                    if note_path and note_path not in topic_index[keyword]:
                        topic_index[keyword].append(note_path)
                    if summary_path and summary_path not in keyword_index[keyword]:
                        keyword_index[keyword].append(summary_path)
    topic_path = root / 'indices' / 'topic_index.json'
    keyword_path = root / 'indices' / 'keyword_index.json'
    retrieval_path = root / 'indices' / 'retrieval_map.json'
    cr.write_json(topic_path, dict(sorted(topic_index.items())))
    cr.write_json(keyword_path, dict(sorted(keyword_index.items())))
    cr.write_json(
        retrieval_path,
        {
            'version': 1,
            'mod_id': root.name,
            'notes': notes,
            'summaries': summaries,
            'generated_at': now_iso(),
        },
    )
    return {
        'topic_index': [relative_posix(topic_path, root)],
        'keyword_index': [relative_posix(keyword_path, root)],
        'retrieval_map': [relative_posix(retrieval_path, root)],
    }


def library_registry() -> dict[str, Any]:
    cr = _cr()
    cr.ensure_library_artifacts()
    return cr.read_json(cr.LIBRARY_REGISTRY_PATH, {'version': 1, 'generated_at': date.today().isoformat(), 'mods': {}})


def extract_text_from_html(raw_html: str) -> tuple[str, str]:
    parser = HTMLTextExtractor()
    parser.feed(raw_html)
    text, title = parser.result()
    parser.close()
    return text, title


def extract_text_for_knowledge(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {'.md', '.txt', '.json', '.yaml', '.yml', '.rst', '.sql', '.xml', '.py', '.csv'}:
        return path.read_text(encoding='utf-8', errors='ignore').strip()
    if suffix in {'.html', '.htm'}:
        text, _ = extract_text_from_html(path.read_text(encoding='utf-8', errors='ignore'))
        return text
    if suffix == '.pdf':
        if shutil.which('pdftotext'):
            result = subprocess.run(
                ['pdftotext', '-layout', '-nopgbrk', '-q', path.as_posix(), '-'],
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
            )
            text = result.stdout.strip()
            if text and not text.lstrip().startswith('%PDF-'):
                return text
        for module_name in ['pypdf', 'PyPDF2']:
            try:
                module = __import__(module_name, fromlist=['PdfReader'])
                reader = module.PdfReader(path.as_posix())
                pages = []
                for index, page in enumerate(reader.pages):
                    if index >= 120:
                        break
                    page_text = (page.extract_text() or '').strip()
                    if page_text:
                        pages.append(page_text)
                    if sum(len(chunk) for chunk in pages) >= 80000:
                        break
                text = '\n\n'.join(pages).strip()
                if text:
                    return text
            except Exception:
                continue
    return ''


def clean_extracted_knowledge_text(text: str) -> str:
    if not text.strip():
        return ''
    raw_lines = [line.replace('\x00', '').strip() for line in text.splitlines()]
    normalized_counts: dict[str, int] = defaultdict(int)
    for line in raw_lines:
        normalized = re.sub(r'\s+', ' ', line).strip().lower()
        if normalized:
            normalized_counts[normalized] += 1

    cleaned_lines: list[str] = []
    index = 0
    while index < len(raw_lines):
        line = re.sub(r'\s+', ' ', raw_lines[index]).strip()
        next_line = re.sub(r'\s+', ' ', raw_lines[index + 1]).strip() if index + 1 < len(raw_lines) else ''
        if line.endswith('-') and next_line and next_line[:1].islower():
            line = f'{line[:-1]}{next_line}'
            index += 1
        normalized = line.lower()
        if not line:
            cleaned_lines.append('')
            index += 1
            continue
        if re.match(r'^\d+_\d+ .* page [ivxlcdm0-9]+$', normalized):
            index += 1
            continue
        if re.match(r'^page [ivxlcdm0-9]+$', normalized):
            index += 1
            continue
        if re.match(r'^\d+( \d+)+$', normalized):
            index += 1
            continue
        if len(line) <= 80 and normalized_counts.get(normalized, 0) >= 3:
            index += 1
            continue
        if any(
            normalized.startswith(prefix)
            for prefix in [
                'copyright',
                'published by',
                'library of congress cataloging',
                'trademarks:',
                'for general information on our other products',
                'limit of liability/disclaimer',
                'requests to the publisher',
                'wiley also publishes',
            ]
        ):
            index += 1
            continue
        cleaned_lines.append(line)
        index += 1

    paragraphs: list[str] = []
    current: list[str] = []
    for line in cleaned_lines:
        if not line:
            if current:
                paragraphs.append(' '.join(current).strip())
                current = []
            continue
        current.append(line)
    if current:
        paragraphs.append(' '.join(current).strip())

    compact_paragraphs = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        paragraph = re.sub(r'\s+', ' ', paragraph).strip()
        if len(paragraph) < 40:
            continue
        signature = paragraph.lower()
        if signature in seen:
            continue
        seen.add(signature)
        compact_paragraphs.append(paragraph)
    return '\n\n'.join(compact_paragraphs).strip()


def normalize_knowledge_text(text: str) -> str:
    cleaned = clean_extracted_knowledge_text(text)
    if cleaned:
        return cleaned
    fallback = text.replace('\x00', '').replace('\r\n', '\n').replace('\r', '\n').strip()
    fallback = re.sub(r'[ \t]+\n', '\n', fallback)
    fallback = re.sub(r'\n{3,}', '\n\n', fallback)
    return fallback.strip()


def summarize_knowledge_text(text: str) -> str:
    cleaned = normalize_knowledge_text(text)
    if not cleaned:
        return ''
    paragraphs = [paragraph.strip() for paragraph in cleaned.split('\n\n') if paragraph.strip()]
    scored: list[tuple[int, str]] = []
    for paragraph in paragraphs:
        haystack = paragraph.lower()
        if any(
            marker in haystack
            for marker in [
                'copyright',
                'isbn',
                'wiley publishing',
                'library of congress',
                'trademarks',
                'permissions',
                'fax',
                'executive editor',
                'production editor',
                'credits',
            ]
        ):
            continue
        score = 0
        for keyword in ['goal', 'design', 'user', 'interaction', 'product', 'behavior', 'persona', 'workflow', 'research', 'interface']:
            if keyword in haystack:
                score += 2
        if 'chapter 1' in haystack or 'goal-directed design' in haystack:
            score += 4
        if len(paragraph) >= 120:
            score += 1
        scored.append((score, paragraph))
    scored.sort(key=lambda item: (-item[0], -len(item[1])))
    preferred = [paragraph for score, paragraph in scored if score > 0][:3]
    if preferred:
        return truncate_words(' '.join(preferred), 60)
    return truncate_words(cleaned, 60)


def detect_main_content_start(text: str) -> str:
    for marker in [
        'What This Book Is and What It Is Not',
        'Chapter 1 Goal-Directed Design',
        'Chapter 1',
    ]:
        index = text.find(marker)
        if index != -1:
            return text[index:]
    return text


def chapter_title_from_chunk(chunk: str, fallback_index: int) -> str:
    chunk = re.sub(r'\s+', ' ', chunk).strip()
    match = re.match(r'^Chapter\s+(\d+)\s+(.+)$', chunk)
    if match:
        number = match.group(1)
        tail = re.sub(r'\s+', ' ', match.group(2)).strip(' -:')
        title_words = []
        for word in tail.split():
            if len(title_words) >= 10:
                break
            if re.fullmatch(r'\d{1,3}', word):
                break
            title_words.append(word)
        title = ' '.join(title_words).strip(' -:')
        return f'Chapter {number} — {title}' if title else f'Chapter {number}'
    if chunk.startswith('What This Book Is and What It Is Not'):
        return 'Introduction — What This Book Is and What It Is Not'
    words = chunk.split()
    return f"Section {fallback_index} — {' '.join(words[:8])}".strip()


def section_title_from_keywords(text: str, fallback_index: int) -> str:
    keywords = topic_keywords(text, limit=4)
    if keywords:
        return f"Section {fallback_index} — {' / '.join(keywords)}"
    words = text.split()
    return f"Section {fallback_index} — {' '.join(words[:8])}".strip()


def split_knowledge_sections(text: str) -> list[dict[str, Any]]:
    cleaned = normalize_knowledge_text(text)
    if not cleaned:
        return []
    main_text = detect_main_content_start(cleaned)
    parts = re.split(r'(?=Chapter\s+\d+\s)', main_text)
    sections: list[dict[str, Any]] = []
    preface = parts[0].strip() if parts else ''
    section_index = 1
    if preface and len(preface) > 400:
        title = chapter_title_from_chunk(preface, section_index)
        sections.append({'title': title, 'slug': slugify(title)[:80], 'text': preface})
        section_index += 1
    for chunk in parts[1:] if len(parts) > 1 else ([] if preface else parts):
        chunk = chunk.strip()
        if len(chunk) < 300:
            continue
        title = chapter_title_from_chunk(chunk, section_index)
        sections.append({'title': title, 'slug': slugify(title)[:80], 'text': chunk})
        section_index += 1
    chapter_numbers = []
    for section in sections:
        match = re.match(r'^Chapter\s+(\d+)', section['title'])
        if match:
            chapter_numbers.append(int(match.group(1)))
    chapter_split_is_valid = len(chapter_numbers) >= 5 and chapter_numbers[:3] == [1, 2, 3]
    if not sections or not chapter_split_is_valid:
        sections = []
        section_index = 1
        paragraphs = [paragraph.strip() for paragraph in main_text.split('\n\n') if paragraph.strip()]
        buffer: list[str] = []
        target_size = 4500
        for paragraph in paragraphs:
            buffer.append(paragraph)
            if len(' '.join(buffer)) >= target_size:
                text_chunk = '\n\n'.join(buffer)
                title = section_title_from_keywords(text_chunk, section_index)
                sections.append({'title': title, 'slug': slugify(title)[:80], 'text': text_chunk})
                section_index += 1
                buffer = []
        if buffer:
            text_chunk = '\n\n'.join(buffer)
            title = section_title_from_keywords(text_chunk, section_index)
            sections.append({'title': title, 'slug': slugify(title)[:80], 'text': text_chunk})
    return sections[:18]


def topic_keywords(text: str, *, limit: int = 12) -> list[str]:
    text = normalize_knowledge_text(text)
    words = re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{3,}', text.lower())
    stop = {'this', 'that', 'with', 'from', 'have', 'into', 'your', 'about', 'para', 'cuando', 'where', 'which', 'using', 'there', 'their', 'will', 'should', 'after', 'page', 'pages', 'chapter', 'copyright', 'published'}
    counts: dict[str, int] = defaultdict(int)
    for word in words:
        if word in stop:
            continue
        counts[word] += 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [word for word, _ in ranked[:limit]]


def stable_source_name(source_path: Path, source_kind: str, source_key: str, previous: dict[str, Any] | None = None) -> str:
    existing = (previous or {}).get('source_name')
    if existing:
        return str(existing)
    base = sanitize_source_name(source_path.stem if source_kind == 'inbox' else f"{source_path.stem}_{hashlib.md5(source_key.encode('utf-8')).hexdigest()[:8]}")
    return base


def process_knowledge_source(
    root: Path,
    *,
    source_path: Path,
    source_kind: str,
    source_key: str,
    title: str,
    label: str | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cr = _cr()
    text = extract_text_for_knowledge(source_path)
    cleaned_text = normalize_knowledge_text(text)
    source_name = stable_source_name(source_path, source_kind, source_key, previous)
    if source_kind == 'inbox':
        copied_source = root / 'sources' / source_path.name
        copied_source.write_bytes(source_path.read_bytes())
    status = 'processed' if cleaned_text else 'unsupported'
    sections = split_knowledge_sections(cleaned_text) if cleaned_text else []
    excerpt = truncate_words(cleaned_text, 120) if cleaned_text else f"Unsupported source type: {source_path.suffix or 'unknown'}"
    summary_text = summarize_knowledge_text(cleaned_text) if cleaned_text else 'No extractable text was generated for this source.'
    note_path = root / 'notes' / f'{source_name}.md'
    summary_path = root / 'summaries' / f'{source_name}.md'
    manifest_path = root / 'manifests' / f'{source_name}.json'
    processed_path = root / 'processed' / f'{source_name}.txt'
    write_text(note_path, f'# {title}\n\n{excerpt}\n')
    write_text(summary_path, f'# {title} summary\n\n- {summary_text}\n')
    write_text(processed_path, cleaned_text + ('\n' if cleaned_text else ''))
    keywords = topic_keywords(cleaned_text)
    note_files = [relative_posix(note_path, root)]
    summary_files = [relative_posix(summary_path, root)]
    section_entries: list[dict[str, Any]] = []
    for section in sections:
        section_note_path = root / 'notes' / f"{source_name}__{section['slug']}.md"
        section_summary_path = root / 'summaries' / f"{source_name}__{section['slug']}.md"
        section_excerpt = truncate_words(section['text'], 160)
        section_summary = summarize_knowledge_text(section['text'])
        write_text(section_note_path, f"# {section['title']}\n\n{section_excerpt}\n")
        write_text(section_summary_path, f"# {section['title']} summary\n\n- {section_summary}\n")
        section_keywords = topic_keywords(section['text'], limit=10)
        section_entries.append(
            {
                'title': section['title'],
                'slug': section['slug'],
                'note_path': relative_posix(section_note_path, root),
                'summary_path': relative_posix(section_summary_path, root),
                'keywords': section_keywords,
            }
        )
        note_files.append(relative_posix(section_note_path, root))
        summary_files.append(relative_posix(section_summary_path, root))
    cr.write_json(
        manifest_path,
        {
            'source': source_key,
            'source_kind': source_kind,
            'title': title,
            'label': label,
            'status': status,
            'processed_path': relative_posix(processed_path, root),
            'note_path': relative_posix(note_path, root),
            'summary_path': relative_posix(summary_path, root),
            'keywords': keywords,
            'sections': section_entries,
            'updated_at': now_iso(),
        },
    )
    return {
        'status': status,
        'processed_at': now_iso(),
        'source_name': source_name,
        'title': title,
        'label': label,
        'keywords': keywords,
        'sections': section_entries,
        'note_files': note_files,
        'summary_files': summary_files,
        'index_files': [],
        'processed_path': relative_posix(processed_path, root),
        'manifest_path': relative_posix(manifest_path, root),
    }


def canonicalize_url(raw_url: str) -> str:
    parsed = urllib_parse.urlsplit(raw_url.strip())
    scheme = (parsed.scheme or 'https').lower()
    host = (parsed.hostname or '').lower()
    port = parsed.port
    netloc = host
    if port and not ((scheme == 'http' and port == 80) or (scheme == 'https' and port == 443)):
        netloc = f'{host}:{port}'
    path = parsed.path or '/'
    if path != '/' and path.endswith('/'):
        path = path.rstrip('/')
    query_pairs = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    kept_query = [(key, value) for key, value in query_pairs if key.lower() not in {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content'}]
    query = urllib_parse.urlencode(kept_query, doseq=True)
    return urllib_parse.urlunsplit((scheme, netloc, path, query, ''))


def build_source_id(url: str, existing_sources: list[dict[str, Any]]) -> str:
    parsed = urllib_parse.urlsplit(url)
    base = slugify('_'.join(part for part in [parsed.hostname or '', parsed.path.strip('/').replace('/', '_')] if part))
    base = base[:80] or 'remote_source'
    existing_ids = {row.get('id') for row in existing_sources}
    if base not in existing_ids:
        return base
    suffix = hashlib.md5(url.encode('utf-8')).hexdigest()[:8]
    return f'{base[:71]}_{suffix}'


def detect_remote_type(url: str, declared_type: str, content_type_header: str, raw_bytes: bytes) -> str:
    if declared_type != 'auto':
        return declared_type
    header = (content_type_header or '').lower()
    if 'pdf' in header or raw_bytes.startswith(b'%PDF-'):
        return 'pdf'
    if 'html' in header:
        return 'html'
    if 'markdown' in header:
        return 'md'
    if header.startswith('text/plain'):
        return 'txt'
    suffix = Path(urllib_parse.urlsplit(url).path).suffix.lower()
    if suffix in {'.html', '.htm'}:
        return 'html'
    if suffix == '.pdf':
        return 'pdf'
    if suffix in {'.md', '.markdown'}:
        return 'md'
    if suffix == '.txt':
        return 'txt'
    sample = raw_bytes[:2048].decode('utf-8', errors='ignore').lower()
    if '<html' in sample or '<body' in sample:
        return 'html'
    return 'txt'


def title_from_text(text: str, fallback: str) -> str:
    for line in text.splitlines():
        candidate = line.strip().lstrip('#').strip()
        if len(candidate) >= 4:
            return candidate[:160]
    return fallback


def extract_remote_payload(raw_path: Path, detected_type: str) -> tuple[str, str, list[str]]:
    notes: list[str] = []
    if detected_type == 'html':
        html_text = raw_path.read_text(encoding='utf-8', errors='ignore')
        extracted, title = extract_text_from_html(html_text)
        if title:
            notes.append('Preserved HTML title')
        notes.append('Removed obvious HTML boilerplate')
        return extracted, title, notes
    if detected_type == 'pdf':
        extracted = extract_text_for_knowledge(raw_path)
        notes.append('Used PDF text extraction')
        return extracted, '', notes
    extracted = raw_path.read_text(encoding='utf-8', errors='ignore')
    notes.append('Preserved text content with normalized UTF-8 decoding')
    return extracted, '', notes


def remote_frontmatter(tags: list[str]) -> str:
    if not tags:
        return 'tags: []'
    lines = ['tags:']
    lines.extend(f'  - {tag}' for tag in tags)
    return '\n'.join(lines)


def parse_http_headers(raw_headers: str) -> tuple[int, dict[str, str]]:
    normalized = raw_headers.replace('\r\n', '\n')
    blocks = [block.strip() for block in re.split(r'\n\s*\n', normalized) if block.strip()]
    if not blocks:
        return 0, {}
    final_block = blocks[-1]
    lines = [line.strip() for line in final_block.splitlines() if line.strip()]
    status_line = lines[0] if lines else ''
    match = re.match(r'HTTP/\S+\s+(\d+)', status_line)
    status_code = int(match.group(1)) if match else 0
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()
    return status_code, headers


def fetch_remote_payload_bytes(url: str) -> tuple[bytes, int, dict[str, str]]:
    request = urllib_request.Request(
        url,
        headers={'User-Agent': 'ai-context-engine/16 (+local knowledge ingestion)'},
    )
    try:
        with urllib_request.urlopen(request, timeout=20) as response:
            raw_bytes = response.read()
            status_code = getattr(response, 'status', response.getcode())
            headers = {key: value for key, value in response.headers.items()}
        return raw_bytes, int(status_code), headers
    except urllib_error.URLError as exc:
        if not shutil.which('curl'):
            raise
        with tempfile.TemporaryDirectory(prefix='ai_context_engine_fetch_') as temp_dir:
            headers_path = Path(temp_dir) / 'headers.txt'
            body_path = Path(temp_dir) / 'body.bin'
            result = subprocess.run(
                [
                    'curl',
                    '-L',
                    '-sS',
                    '--fail',
                    '-D',
                    headers_path.as_posix(),
                    '-o',
                    body_path.as_posix(),
                    url,
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                raise exc
            raw_bytes = body_path.read_bytes()
            status_code, headers = parse_http_headers(headers_path.read_text(encoding='utf-8', errors='ignore'))
            return raw_bytes, status_code or 200, headers


def bootstrap_mod(
    mod_id: str,
    *,
    aliases: list[str] | None = None,
    title: str | None = None,
    create_reference_stub: bool = False,
) -> dict[str, Any]:
    cr = _cr()

    cr.ensure_library_artifacts()
    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    for name in ['inbox', 'sources', 'processed', 'notes', 'summaries', 'indices', 'manifests', 'remote_sources', 'remote_sources/raw', 'remote_sources/snapshots', 'remote_sources/extracted']:
        (root / name).mkdir(parents=True, exist_ok=True)
    ensure_remote_manifest(root)
    manifest = load_mod_manifest(root)
    created_at = manifest.get('created_at') or now_iso()
    existing_aliases = set(manifest.get('aliases', []))
    manifest.update({'id': normalized, 'title': title or manifest.get('title') or normalized.replace('_', ' ').title(), 'aliases': sorted({normalized, *(slugify(alias) for alias in (aliases or [])), *existing_aliases}), 'created_at': created_at, 'status': 'ready', 'last_processed': manifest.get('last_processed'), 'inbox_count': int(manifest.get('inbox_count', 0) or 0), 'referenced_count': int(manifest.get('referenced_count', 0) or 0), 'remote_sources_count': int(manifest.get('remote_sources_count', 0) or 0)})
    save_mod_manifest(root, manifest)
    if create_reference_stub:
        references_path = root / 'inbox' / 'references.md'
        if not references_path.exists():
            write_text(references_path, references_stub_text(normalized))
    registry = library_registry()
    registry.setdefault('mods', {})[normalized] = {'title': manifest['title'], 'aliases': manifest['aliases'], 'manifest_path': (root / 'mod.json').as_posix(), 'library_root': root.as_posix(), 'updated_at': manifest['updated_at']}
    registry['generated_at'] = date.today().isoformat()
    cr.write_json(cr.LIBRARY_REGISTRY_PATH, registry)
    status = cr.read_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, {})
    status.update({**compat_version_payload(), 'mods_total': len(registry.get('mods', {})), 'supports_reference_ingestion': True, 'supports_remote_ingestion': True})
    cr.write_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return manifest


def register_remote_source(mod_id: str, url: str, declared_type: str = 'auto', tags: list[str] | None = None) -> dict[str, Any]:
    cr = _cr()

    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    if not (root / 'mod.json').exists():
        raise ValueError(f'Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.')
    if declared_type not in cr.REMOTE_DECLARED_TYPES:
        raise ValueError(f'Unsupported source type `{declared_type}`.')
    parsed = urllib_parse.urlsplit(url.strip())
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('URL must use http or https and include a host.')
    manifest = load_remote_sources_manifest(root)
    canonical_url = canonicalize_url(url)
    if any(row.get('canonical_url') == canonical_url for row in manifest.get('sources', [])):
        raise ValueError(f'Source already registered for `{canonical_url}`.')
    source_id = build_source_id(canonical_url, manifest.get('sources', []))
    row = {'id': source_id, 'url': url.strip(), 'canonical_url': canonical_url, 'declared_type': declared_type, 'detected_type': None, 'tags': sorted(set(tags or [])), 'status': 'pending', 'created_at': now_iso(), 'updated_at': now_iso(), 'last_fetched_at': None, 'last_successful_snapshot_id': None, 'last_error': None}
    manifest.setdefault('sources', []).append(row)
    save_remote_sources_manifest(root, manifest)
    mod_manifest = load_mod_manifest(root)
    mod_manifest['remote_sources_count'] = len(manifest.get('sources', []))
    save_mod_manifest(root, mod_manifest)
    return {'mod_id': normalized, 'source': row, 'manifest_path': remote_manifest_path(root).as_posix(), 'events': [f'registered:{source_id}']}


def fetch_remote_sources(mod_id: str, source_id: str | None = None, force: bool = False) -> dict[str, Any]:
    cr = _cr()

    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    if not (root / 'mod.json').exists():
        raise ValueError(f'Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.')
    manifest = load_remote_sources_manifest(root)
    sources = manifest.get('sources', [])
    selected = [row for row in sources if source_id in {None, row.get('id')}]
    if source_id and not selected:
        raise ValueError(f'Unknown source id `{source_id}` for mod `{normalized}`.')
    events: list[str] = []
    results: list[dict[str, Any]] = []
    success_count = 0
    for row in selected:
        try:
            raw_bytes, status_code, response_headers = fetch_remote_payload_bytes(row['url'])
            content_type_header = response_headers.get('Content-Type', '')
            etag = response_headers.get('ETag')
            last_modified = response_headers.get('Last-Modified')
            if int(status_code) < 200 or int(status_code) >= 300:
                raise RuntimeError(f'HTTP status {status_code}')
            detected_type = detect_remote_type(row['canonical_url'], row.get('declared_type', 'auto'), content_type_header, raw_bytes)
            if detected_type not in cr.REMOTE_TYPE_EXTENSIONS:
                raise RuntimeError(f'Unsupported detected type `{detected_type}`')
            checksum = hashlib.sha256(raw_bytes).hexdigest()
            if not force and checksum == row.get('last_checksum_sha256'):
                row['status'] = 'fetched'
                row['updated_at'] = now_iso()
                row['last_error'] = None
                events.append(f"skipped_unchanged:{row['id']}")
                results.append({'source_id': row['id'], 'status': 'skipped', 'reason': 'unchanged'})
                continue
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            snapshot_id = f"{row['id']}_{timestamp}"
            raw_extension = cr.REMOTE_TYPE_EXTENSIONS[detected_type]
            raw_path = root / 'remote_sources' / 'raw' / f'{snapshot_id}{raw_extension}'
            raw_path.write_bytes(raw_bytes)
            extracted_text, extracted_title, extraction_notes = extract_remote_payload(raw_path, detected_type)
            cleaned_text = normalize_knowledge_text(extracted_text)
            if not cleaned_text:
                raise RuntimeError('Extraction produced empty content')
            title = extracted_title or title_from_text(cleaned_text, row['id'].replace('_', ' ').title())
            extracted_path = root / 'remote_sources' / 'extracted' / f'{snapshot_id}.md'
            write_text(extracted_path, cleaned_text + '\n')
            inbox_path = root / 'inbox' / f"remote_{row['id']}.md"
            canonical_doc = ('---\n' f"source_kind: remote_url\nsource_id: {row['id']}\nsnapshot_id: {snapshot_id}\nsource_url: {row['url']}\ncanonical_url: {row['canonical_url']}\ndetected_type: {detected_type}\nfetched_at: {now_iso()}\ntitle: {title}\n{remote_frontmatter(row.get('tags', []))}\n---\n\n" f"# {title}\n\n{cleaned_text}\n")
            write_text(inbox_path, canonical_doc)
            snapshot = {'snapshot_id': snapshot_id, 'source_id': row['id'], 'url': row['url'], 'canonical_url': row['canonical_url'], 'fetched_at': now_iso(), 'declared_type': row.get('declared_type', 'auto'), 'detected_type': detected_type, 'content_type_header': content_type_header, 'http_status': status_code, 'checksum_sha256': checksum, 'raw_path': relative_posix(raw_path, root), 'extracted_path': relative_posix(extracted_path, root), 'inbox_path': relative_posix(inbox_path, root), 'title': title, 'etag': etag, 'last_modified': last_modified, 'word_count': len(cleaned_text.split()), 'extraction_notes': extraction_notes}
            cr.write_json(root / 'remote_sources' / 'snapshots' / f'{snapshot_id}.json', snapshot)
            row.update({'status': 'fetched', 'detected_type': detected_type, 'updated_at': now_iso(), 'last_fetched_at': snapshot['fetched_at'], 'last_successful_snapshot_id': snapshot_id, 'last_checksum_sha256': checksum, 'last_error': None})
            success_count += 1
            events.extend([f"fetched:{row['id']}", f'snapshot_created:{snapshot_id}', f"extracted:{relative_posix(extracted_path, root)}", f"inbox_emitted:{relative_posix(inbox_path, root)}"])
            results.append({'source_id': row['id'], 'status': 'fetched', 'snapshot_id': snapshot_id, 'inbox_path': inbox_path.as_posix()})
        except (urllib_error.URLError, RuntimeError, OSError, ValueError) as exc:
            row['status'] = 'failed'
            row['updated_at'] = now_iso()
            row['last_error'] = str(exc)
            events.append(f"failed:{row['id']}")
            results.append({'source_id': row['id'], 'status': 'failed', 'error': str(exc)})
    save_remote_sources_manifest(root, manifest)
    mod_manifest = load_mod_manifest(root)
    mod_manifest['remote_sources_count'] = len(manifest.get('sources', []))
    save_mod_manifest(root, mod_manifest)
    all_failed = bool(selected) and success_count == 0 and all(result.get('status') == 'failed' for result in results)
    return {'mod_id': normalized, 'selected_sources': [row.get('id') for row in selected], 'results': results, 'events': events, 'exit_code': 1 if all_failed else 0}


def process_mod_documents(mod_id: str) -> dict[str, Any]:
    cr = _cr()

    manifest = bootstrap_mod(mod_id)
    root = cr.mod_root(mod_id)
    state = load_mod_state(root)
    warnings: list[str] = []
    pending: list[dict[str, Any]] = []
    seen_sources: list[str] = []
    for source_path in sorted((root / 'inbox').glob('*')):
        if not should_process_inbox_file(source_path):
            continue
        source_key = source_path.name
        seen_sources.append(source_key)
        current_hash = file_md5(source_path)
        current_mtime = file_mtime(source_path)
        previous = state['processed_docs'].get(source_key, {})
        if previous.get('hash') != current_hash or mtime_changed(previous.get('mtime'), current_mtime):
            invalidate_source_artifacts(root, previous)
            pending.append({'kind': 'inbox', 'path': source_path, 'key': source_key, 'title': source_path.stem, 'hash': current_hash, 'mtime': current_mtime, 'previous': previous})
    references = parse_references_file(root / 'inbox' / 'references.md')
    for reference in references:
        reference_path = reference['path']
        reference_key = reference_path.as_posix()
        if reference_path.suffix.lower() not in cr.SUPPORTED_REFERENCED_EXTENSIONS:
            warnings.append(f'unsupported_reference:{reference_key}')
            continue
        previous = state['referenced_files'].get(reference_key, {})
        if not reference_path.exists():
            warnings.append(f'missing_reference:{reference_key}')
            continue
        current_mtime = file_mtime(reference_path)
        if mtime_changed(previous.get('mtime'), current_mtime) or previous.get('label') != reference.get('label'):
            invalidate_source_artifacts(root, previous)
            pending.append({'kind': 'reference', 'path': reference_path, 'key': reference_key, 'title': reference.get('label') or reference_path.stem, 'label': reference.get('label'), 'mtime': current_mtime, 'previous': previous})
    for item in pending:
        processed = process_knowledge_source(root, source_path=item['path'], source_kind=item['kind'], source_key=item['key'], title=item['title'], label=item.get('label'), previous=item.get('previous'))
        processed['mtime'] = item['mtime']
        if item['kind'] == 'inbox':
            processed['hash'] = item['hash']
            state['processed_docs'][item['key']] = processed
        else:
            state['referenced_files'][item['key']] = processed
    index_files = rebuild_mod_indices(root, state)
    for bucket_name in ['processed_docs', 'referenced_files']:
        for entry in state.get(bucket_name, {}).values():
            entry['index_files'] = sorted({path for paths in index_files.values() for path in paths})
    state['last_processed'] = now_iso()
    save_mod_state(root, state)
    manifest = bootstrap_mod(mod_id, aliases=manifest.get('aliases', []), title=manifest.get('title'))
    manifest['last_processed'] = state['last_processed']
    manifest['inbox_count'] = len(seen_sources)
    manifest['referenced_count'] = len(references)
    manifest['remote_sources_count'] = len(load_remote_sources_manifest(root).get('sources', []))
    save_mod_manifest(root, manifest)
    return {'mod_id': slugify(mod_id), 'sources_seen': seen_sources, 'pending_count': len(pending), 'notes_generated': sum(len(entry.get('note_files', [])) for entry in state['processed_docs'].values()) + sum(len(entry.get('note_files', [])) for entry in state['referenced_files'].values()), 'summaries_generated': sum(len(entry.get('summary_files', [])) for entry in state['processed_docs'].values()) + sum(len(entry.get('summary_files', [])) for entry in state['referenced_files'].values()), 'referenced_count': len(references), 'warnings': warnings, 'status': 'processed' if state['processed_docs'] or state['referenced_files'] else 'ready_empty'}


def infer_candidate_mods(task: str) -> list[str]:
    cr = _cr()
    registry = library_registry().get('mods', {})
    haystack = task.lower()
    matches = []
    for mod_id, info in registry.items():
        aliases = [mod_id, *info.get('aliases', [])]
        if any(alias and alias in haystack for alias in aliases):
            matches.append(mod_id)
    if matches:
        return sorted(set(matches))
    for hint, mod_id in {
        'ux': 'ux',
        'ui': 'ux',
        'design': 'ux',
        'accessibility': 'accessibility',
        'a11y': 'accessibility',
        'architecture': 'architecture',
        'api': 'api',
        'testing': 'testing',
    }.items():
        if hint in haystack:
            bootstrap_mod(mod_id)
            matches.append(mod_id)
    return sorted(set(matches))


def retrieve_knowledge(task: str) -> dict[str, Any]:
    cr = _cr()

    cr.ensure_library_artifacts()
    candidate_mods = infer_candidate_mods(task)
    topics = topic_keywords(task, limit=6)
    selected_artifacts: list[str] = []
    artifact_rows: list[dict[str, Any]] = []
    for mod_id in candidate_mods[:3]:
        root = cr.mod_root(mod_id)
        topic_index = cr.read_json(root / 'indices' / 'topic_index.json', {})
        keyword_index = cr.read_json(root / 'indices' / 'keyword_index.json', {})
        for topic in topics:
            for path in topic_index.get(topic, [])[:2] + keyword_index.get(topic, [])[:1]:
                if path in selected_artifacts:
                    continue
                selected_artifacts.append(path)
                text = Path(path).read_text(encoding='utf-8', errors='ignore') if Path(path).exists() else ''
                artifact_rows.append({'path': path, 'summary': truncate_words(text.replace('\n', ' '), 28), 'estimated_tokens': cr.estimate_tokens(text)})
        if selected_artifacts:
            break
    status = cr.read_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, {})
    status.update({**compat_version_payload(), 'generated_at': date.today().isoformat(), 'mods_total': len(library_registry().get('mods', {})), 'retrieval_events': int(status.get('retrieval_events', 0) or 0) + 1, 'last_selected_artifacts': selected_artifacts[:6], 'supports_reference_ingestion': True, 'supports_remote_ingestion': True})
    cr.write_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return {'mods': candidate_mods[:3], 'topics': topics, 'selected_artifacts': selected_artifacts[:6], 'artifacts': artifact_rows[:6], 'strategy': 'topic_first_minimal_pack' if selected_artifacts else 'empty_fallback'}


def cli_library(args: argparse.Namespace) -> int:
    cr = _cr()

    command = getattr(args, 'command', 'status')
    try:
        if command == 'learn':
            payload = bootstrap_mod(args.mod_id, aliases=getattr(args, 'aliases', []) or [], create_reference_stub=True)
        elif command == 'process':
            payload = process_mod_documents(args.mod_id)
        elif command == 'add-source':
            payload = register_remote_source(args.mod_id, args.url, getattr(args, 'declared_type', 'auto'), getattr(args, 'tags', []) or [])
        elif command == 'fetch-sources':
            payload = fetch_remote_sources(args.mod_id, getattr(args, 'source_id', None), bool(getattr(args, 'force', False)))
        elif command == 'retrieve':
            payload = retrieve_knowledge(args.task)
        else:
            payload = {'state': cr.refresh_engine_state(), 'registry': library_registry(), 'telemetry': cr.read_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, {}), 'retrieval_status': cr.read_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, {})}
    except ValueError as exc:
        payload = {'error': str(exc), 'command': command}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return int(payload.get('exit_code', 0) or 0)
