from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error

from .runtime_io import file_md5, file_mtime, mtime_changed, now_iso, relative_posix, slugify, truncate_words, write_text


def bootstrap_mod(
    mod_id: str,
    *,
    aliases: list[str] | None = None,
    title: str | None = None,
    create_reference_stub: bool = False,
) -> dict[str, Any]:
    from . import core_runtime as cr

    cr.ensure_library_artifacts()
    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    for name in ['inbox', 'sources', 'processed', 'notes', 'summaries', 'indices', 'manifests', 'remote_sources', 'remote_sources/raw', 'remote_sources/snapshots', 'remote_sources/extracted']:
        (root / name).mkdir(parents=True, exist_ok=True)
    cr.ensure_remote_manifest(root)
    manifest = cr.load_mod_manifest(root)
    created_at = manifest.get('created_at') or now_iso()
    existing_aliases = set(manifest.get('aliases', []))
    manifest.update({'id': normalized, 'title': title or manifest.get('title') or normalized.replace('_', ' ').title(), 'aliases': sorted({normalized, *(slugify(alias) for alias in (aliases or [])), *existing_aliases}), 'created_at': created_at, 'status': 'ready', 'last_processed': manifest.get('last_processed'), 'inbox_count': int(manifest.get('inbox_count', 0) or 0), 'referenced_count': int(manifest.get('referenced_count', 0) or 0), 'remote_sources_count': int(manifest.get('remote_sources_count', 0) or 0)})
    cr.save_mod_manifest(root, manifest)
    if create_reference_stub:
        references_path = root / 'inbox' / 'references.md'
        if not references_path.exists():
            write_text(references_path, cr.references_stub_text(normalized))
    registry = cr.library_registry()
    registry.setdefault('mods', {})[normalized] = {'title': manifest['title'], 'aliases': manifest['aliases'], 'manifest_path': (root / 'mod.json').as_posix(), 'library_root': root.as_posix(), 'updated_at': manifest['updated_at']}
    registry['generated_at'] = date.today().isoformat()
    cr.write_json(cr.LIBRARY_REGISTRY_PATH, registry)
    status = cr.read_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, {})
    status.update({'installed_iteration': cr.current_engine_iteration(), 'mods_total': len(registry.get('mods', {})), 'supports_reference_ingestion': True, 'supports_remote_ingestion': True})
    cr.write_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return manifest


def register_remote_source(mod_id: str, url: str, declared_type: str = 'auto', tags: list[str] | None = None) -> dict[str, Any]:
    from . import core_runtime as cr

    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    if not (root / 'mod.json').exists():
        raise ValueError(f'Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.')
    if declared_type not in cr.REMOTE_DECLARED_TYPES:
        raise ValueError(f'Unsupported source type `{declared_type}`.')
    parsed = cr.urllib_parse.urlsplit(url.strip())
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('URL must use http or https and include a host.')
    manifest = cr.load_remote_sources_manifest(root)
    canonical_url = cr.canonicalize_url(url)
    if any(row.get('canonical_url') == canonical_url for row in manifest.get('sources', [])):
        raise ValueError(f'Source already registered for `{canonical_url}`.')
    source_id = cr.build_source_id(canonical_url, manifest.get('sources', []))
    row = {'id': source_id, 'url': url.strip(), 'canonical_url': canonical_url, 'declared_type': declared_type, 'detected_type': None, 'tags': sorted(set(tags or [])), 'status': 'pending', 'created_at': now_iso(), 'updated_at': now_iso(), 'last_fetched_at': None, 'last_successful_snapshot_id': None, 'last_error': None}
    manifest.setdefault('sources', []).append(row)
    cr.save_remote_sources_manifest(root, manifest)
    mod_manifest = cr.load_mod_manifest(root)
    mod_manifest['remote_sources_count'] = len(manifest.get('sources', []))
    cr.save_mod_manifest(root, mod_manifest)
    return {'mod_id': normalized, 'source': row, 'manifest_path': cr.remote_manifest_path(root).as_posix(), 'events': [f'registered:{source_id}']}


def fetch_remote_sources(mod_id: str, source_id: str | None = None, force: bool = False) -> dict[str, Any]:
    from . import core_runtime as cr

    normalized = slugify(mod_id)
    root = cr.mod_root(normalized)
    if not (root / 'mod.json').exists():
        raise ValueError(f'Mod `{normalized}` does not exist. Run `ctx-library learn {normalized}` first.')
    manifest = cr.load_remote_sources_manifest(root)
    sources = manifest.get('sources', [])
    selected = [row for row in sources if source_id in {None, row.get('id')}]
    if source_id and not selected:
        raise ValueError(f'Unknown source id `{source_id}` for mod `{normalized}`.')
    events: list[str] = []
    results: list[dict[str, Any]] = []
    success_count = 0
    for row in selected:
        try:
            raw_bytes, status_code, response_headers = cr.fetch_remote_payload_bytes(row['url'])
            content_type_header = response_headers.get('Content-Type', '')
            etag = response_headers.get('ETag')
            last_modified = response_headers.get('Last-Modified')
            if int(status_code) < 200 or int(status_code) >= 300:
                raise RuntimeError(f'HTTP status {status_code}')
            detected_type = cr.detect_remote_type(row['canonical_url'], row.get('declared_type', 'auto'), content_type_header, raw_bytes)
            if detected_type not in cr.REMOTE_TYPE_EXTENSIONS:
                raise RuntimeError(f'Unsupported detected type `{detected_type}`')
            checksum = cr.hashlib.sha256(raw_bytes).hexdigest()
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
            extracted_text, extracted_title, extraction_notes = cr.extract_remote_payload(raw_path, detected_type)
            cleaned_text = cr.normalize_knowledge_text(extracted_text)
            if not cleaned_text:
                raise RuntimeError('Extraction produced empty content')
            title = extracted_title or cr.title_from_text(cleaned_text, row['id'].replace('_', ' ').title())
            extracted_path = root / 'remote_sources' / 'extracted' / f'{snapshot_id}.md'
            write_text(extracted_path, cleaned_text + '\n')
            inbox_path = root / 'inbox' / f"remote_{row['id']}.md"
            canonical_doc = ('---\n' f"source_kind: remote_url\nsource_id: {row['id']}\nsnapshot_id: {snapshot_id}\nsource_url: {row['url']}\ncanonical_url: {row['canonical_url']}\ndetected_type: {detected_type}\nfetched_at: {now_iso()}\ntitle: {title}\n{cr.remote_frontmatter(row.get('tags', []))}\n---\n\n" f"# {title}\n\n{cleaned_text}\n")
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
    cr.save_remote_sources_manifest(root, manifest)
    mod_manifest = cr.load_mod_manifest(root)
    mod_manifest['remote_sources_count'] = len(manifest.get('sources', []))
    cr.save_mod_manifest(root, mod_manifest)
    all_failed = bool(selected) and success_count == 0 and all(result.get('status') == 'failed' for result in results)
    return {'mod_id': normalized, 'selected_sources': [row.get('id') for row in selected], 'results': results, 'events': events, 'exit_code': 1 if all_failed else 0}


def process_mod_documents(mod_id: str) -> dict[str, Any]:
    from . import core_runtime as cr

    manifest = bootstrap_mod(mod_id)
    root = cr.mod_root(mod_id)
    state = cr.load_mod_state(root)
    warnings: list[str] = []
    pending: list[dict[str, Any]] = []
    seen_sources: list[str] = []
    for source_path in sorted((root / 'inbox').glob('*')):
        if not cr.should_process_inbox_file(source_path):
            continue
        source_key = source_path.name
        seen_sources.append(source_key)
        current_hash = file_md5(source_path)
        current_mtime = file_mtime(source_path)
        previous = state['processed_docs'].get(source_key, {})
        if previous.get('hash') != current_hash or mtime_changed(previous.get('mtime'), current_mtime):
            cr.invalidate_source_artifacts(root, previous)
            pending.append({'kind': 'inbox', 'path': source_path, 'key': source_key, 'title': source_path.stem, 'hash': current_hash, 'mtime': current_mtime, 'previous': previous})
    references = cr.parse_references_file(root / 'inbox' / 'references.md')
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
            cr.invalidate_source_artifacts(root, previous)
            pending.append({'kind': 'reference', 'path': reference_path, 'key': reference_key, 'title': reference.get('label') or reference_path.stem, 'label': reference.get('label'), 'mtime': current_mtime, 'previous': previous})
    for item in pending:
        processed = cr.process_knowledge_source(root, source_path=item['path'], source_kind=item['kind'], source_key=item['key'], title=item['title'], label=item.get('label'), previous=item.get('previous'))
        processed['mtime'] = item['mtime']
        if item['kind'] == 'inbox':
            processed['hash'] = item['hash']
            state['processed_docs'][item['key']] = processed
        else:
            state['referenced_files'][item['key']] = processed
    index_files = cr.rebuild_mod_indices(root, state)
    for bucket_name in ['processed_docs', 'referenced_files']:
        for entry in state.get(bucket_name, {}).values():
            entry['index_files'] = sorted({path for paths in index_files.values() for path in paths})
    state['last_processed'] = now_iso()
    cr.save_mod_state(root, state)
    manifest = bootstrap_mod(mod_id, aliases=manifest.get('aliases', []), title=manifest.get('title'))
    manifest['last_processed'] = state['last_processed']
    manifest['inbox_count'] = len(seen_sources)
    manifest['referenced_count'] = len(references)
    manifest['remote_sources_count'] = len(cr.load_remote_sources_manifest(root).get('sources', []))
    cr.save_mod_manifest(root, manifest)
    return {'mod_id': slugify(mod_id), 'sources_seen': seen_sources, 'pending_count': len(pending), 'notes_generated': sum(len(entry.get('note_files', [])) for entry in state['processed_docs'].values()) + sum(len(entry.get('note_files', [])) for entry in state['referenced_files'].values()), 'summaries_generated': sum(len(entry.get('summary_files', [])) for entry in state['processed_docs'].values()) + sum(len(entry.get('summary_files', [])) for entry in state['referenced_files'].values()), 'referenced_count': len(references), 'warnings': warnings, 'status': 'processed' if state['processed_docs'] or state['referenced_files'] else 'ready_empty'}


def retrieve_knowledge(task: str) -> dict[str, Any]:
    from . import core_runtime as cr

    cr.ensure_library_artifacts()
    candidate_mods = cr.infer_candidate_mods(task)
    topics = cr.topic_keywords(task, limit=6)
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
    status.update({'generated_at': date.today().isoformat(), 'installed_iteration': cr.current_engine_iteration(), 'mods_total': len(cr.library_registry().get('mods', {})), 'retrieval_events': int(status.get('retrieval_events', 0) or 0) + 1, 'last_selected_artifacts': selected_artifacts[:6], 'supports_reference_ingestion': True, 'supports_remote_ingestion': True})
    cr.write_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, status)
    return {'mods': candidate_mods[:3], 'topics': topics, 'selected_artifacts': selected_artifacts[:6], 'artifacts': artifact_rows[:6], 'strategy': 'topic_first_minimal_pack' if selected_artifacts else 'empty_fallback'}


def cli_library(args: argparse.Namespace) -> int:
    from . import core_runtime as cr

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
            payload = {'state': cr.refresh_engine_state(), 'registry': cr.library_registry(), 'telemetry': cr.read_json(cr.CONTEXT_WEEKLY_SUMMARY_PATH, {}), 'retrieval_status': cr.read_json(cr.LIBRARY_RETRIEVAL_STATUS_PATH, {})}
    except ValueError as exc:
        payload = {'error': str(exc), 'command': command}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return int(payload.get('exit_code', 0) or 0)
