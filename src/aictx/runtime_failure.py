from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr

    return cr


def ensure_failure_memory_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    if not cr.FAILURE_MEMORY_STATUS_PATH.exists():
        cr.write_json(
            cr.FAILURE_MEMORY_STATUS_PATH,
            {
                'version': 1,
                'generated_at': date.today().isoformat(),
                'records_total': 0,
                'manual_records': 0,
                'derived_records': 0,
                'retrieval_events': 0,
                'write_events': 0,
                'last_packet_path': '',
                'last_recorded_failure_id': '',
            },
        )
    if not cr.FAILURE_MEMORY_INDEX_PATH.exists():
        cr.write_json(cr.FAILURE_MEMORY_INDEX_PATH, {'version': 1, 'generated_at': date.today().isoformat(), 'records': []})
    if not cr.FAILURE_MEMORY_SUMMARY_PATH.exists():
        cr.write_text(
            cr.FAILURE_MEMORY_SUMMARY_PATH,
            '# common failure patterns\n\n'
            '- No failure patterns recorded yet.\n',
        )


def extract_related_commands(text: str) -> list[str]:
    return sorted({match.strip() for match in re.findall(r'`([^`]+)`', text) if match.strip()})[:6]


def derive_failure_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cr = _cr()
    derived = []
    for row in rows:
        if row.get('type') not in {'failure_mode', 'debugging_pattern', 'validation_recipe'}:
            continue
        combined_text = '\n'.join(
            [
                str(row.get('title', '')),
                str(row.get('summary', '')),
                ' '.join(section.get('text', '') for section in row.get('sections', [])),
            ]
        )
        failure_id = f"derived_{cr.slugify(str(row.get('id', 'failure')))}"
        derived.append(
            {
                'id': failure_id,
                'category': cr.classify_failure_category(combined_text),
                'title': str(row.get('title', 'Known failure pattern')),
                'symptoms': [str(row.get('summary', ''))][:1] + [section.get('text', '') for section in row.get('sections', [])[:2] if section.get('text')],
                'root_cause': str(row.get('summary', '')),
                'solution': next((section.get('text', '') for section in row.get('sections', []) if 'validation' in str(section.get('section', '')).lower() or 'check' in str(section.get('section', '')).lower()), 'Inspect the referenced note and apply the documented fix path.'),
                'files_involved': list(row.get('files_involved', [])),
                'related_commands': extract_related_commands(combined_text),
                'reusability': 'high' if float(row.get('relevance_score', 0.6)) >= 0.7 else 'medium',
                'confidence': round(min(0.95, max(0.45, float(row.get('relevance_score', 0.6)))), 2),
                'first_seen_at': str(row.get('last_verified', date.today().isoformat())),
                'last_seen_at': date.today().isoformat(),
                'occurrences': max(1, sum(1 for section in row.get('sections', []) if section.get('text'))),
                'status': 'resolved',
                'notes': f"Derived from {row.get('path', '')}",
                'source': 'derived_from_record',
                'source_record_id': row.get('id'),
            }
        )
    return derived


def manual_failure_records() -> list[dict[str, Any]]:
    cr = _cr()
    ensure_failure_memory_artifacts()
    rows = []
    for path in sorted(cr.FAILURE_MEMORY_RECORDS_DIR.glob('*.json')):
        payload = cr.read_json(path, {})
        if payload.get('source') == 'derived_from_record':
            continue
        if payload:
            rows.append(payload)
    return rows


def build_failure_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cr = _cr()
    ensure_failure_memory_artifacts()
    manual_rows = manual_failure_records()
    derived_rows = derive_failure_records(rows)
    derived_ids = {row['id'] for row in derived_rows}
    for path in sorted(cr.FAILURE_MEMORY_RECORDS_DIR.glob('derived_*.json')):
        if path.stem not in derived_ids:
            path.unlink()
    for row in derived_rows:
        cr.write_json(cr.FAILURE_MEMORY_RECORDS_DIR / f"{row['id']}.json", row)
    combined = sorted(
        manual_rows + derived_rows,
        key=lambda row: (-int(row.get('occurrences', 1)), -float(row.get('confidence', 0.5)), str(row.get('id', ''))),
    )
    cr.write_json(
        cr.FAILURE_MEMORY_INDEX_PATH,
        {
            'version': 1,
            'generated_at': date.today().isoformat(),
            'records': [
                {
                    'id': row['id'],
                    'category': row.get('category', 'unknown'),
                    'title': row.get('title', ''),
                    'confidence': row.get('confidence', 0.5),
                    'occurrences': row.get('occurrences', 1),
                    'status': row.get('status', 'resolved'),
                    'source': row.get('source', 'manual'),
                }
                for row in combined
            ],
        },
    )
    summary_lines = ['# common failure patterns', '']
    if not combined:
        summary_lines.append('- No failure patterns recorded yet.')
    else:
        for row in combined[:12]:
            summary_lines.append(f"- `{row['category']}` | `{row['id']}` | occ {row.get('occurrences', 1)} | {row.get('title', '')}")
    cr.write_text(cr.FAILURE_MEMORY_SUMMARY_PATH, '\n'.join(summary_lines) + '\n')
    previous = cr.read_json(cr.FAILURE_MEMORY_STATUS_PATH, {})
    status = {
        **previous,
        'version': 1,
        'generated_at': date.today().isoformat(),
        'records_total': len(combined),
        'manual_records': len(manual_rows),
        'derived_records': len(derived_rows),
    }
    cr.write_json(cr.FAILURE_MEMORY_STATUS_PATH, status)
    return status


def record_failure(
    *,
    failure_id: str,
    category: str,
    title: str,
    symptoms: list[str],
    root_cause: str,
    solution: str,
    files_involved: list[str] | None = None,
    related_commands: list[str] | None = None,
    confidence: float = 0.75,
    notes: str = '',
) -> dict[str, Any]:
    cr = _cr()
    ensure_failure_memory_artifacts()
    path = cr.FAILURE_MEMORY_RECORDS_DIR / f"{cr.slugify(failure_id)}.json"
    existing = cr.read_json(path, {}) if path.exists() else {}
    today = date.today().isoformat()
    record = {
        'id': cr.slugify(failure_id),
        'category': category if category in cr.FAILURE_CATEGORIES else 'unknown',
        'title': title or existing.get('title', 'Known failure'),
        'symptoms': symptoms or existing.get('symptoms', []),
        'root_cause': root_cause or existing.get('root_cause', ''),
        'solution': solution or existing.get('solution', ''),
        'files_involved': files_involved or existing.get('files_involved', []),
        'related_commands': related_commands or existing.get('related_commands', []),
        'reusability': existing.get('reusability', 'high'),
        'confidence': round(float(confidence or existing.get('confidence', 0.75)), 2),
        'first_seen_at': existing.get('first_seen_at', today),
        'last_seen_at': today,
        'occurrences': int(existing.get('occurrences', 0) or 0) + 1,
        'status': 'resolved',
        'notes': notes or existing.get('notes', ''),
        'source': 'manual',
    }
    cr.write_json(path, record)
    status = build_failure_memory_artifacts([cr.normalize_record(row) for row in cr.load_records()])
    from .runtime_graph import build_memory_graph_artifacts

    build_memory_graph_artifacts([cr.normalize_record(row) for row in cr.load_records()])
    status['write_events'] = int(status.get('write_events', 0) or 0) + 1
    status['last_recorded_failure_id'] = record['id']
    cr.write_json(cr.FAILURE_MEMORY_STATUS_PATH, status)
    return record


def should_consult_failure_memory(task: str, task_type: str) -> bool:
    task_l = task.lower()
    if task_type in {'bug_fixing', 'testing', 'performance'}:
        return True
    return any(keyword in task_l for keyword in ['fail', 'error', 'regression', 'broken', 'flaky', 'trap', 'cannot', 'build', 'test'])


def rank_failure_records(task: str) -> list[dict[str, Any]]:
    cr = _cr()
    ensure_failure_memory_artifacts()
    index_rows = cr.read_json(cr.FAILURE_MEMORY_INDEX_PATH, {}).get('records', [])
    ranked = []
    for item in index_rows:
        full = cr.read_json(cr.FAILURE_MEMORY_RECORDS_DIR / f"{item['id']}.json", {})
        haystack = ' '.join(
            [
                full.get('title', ''),
                full.get('category', ''),
                ' '.join(full.get('symptoms', [])),
                full.get('root_cause', ''),
                full.get('solution', ''),
                ' '.join(full.get('files_involved', [])),
                ' '.join(full.get('related_commands', [])),
            ]
        )
        lexical = cr.score_match(task, haystack) / 100
        confidence = float(full.get('confidence', 0.5))
        occurrences = min(int(full.get('occurrences', 1)), 5) / 5
        total = round(lexical * 0.6 + confidence * 0.25 + occurrences * 0.15, 4)
        if total >= 0.18:
            ranked.append((total, full))
    ranked.sort(key=lambda item: (-item[0], -int(item[1].get('occurrences', 1)), item[1].get('id', '')))
    return [{'score': score, **row} for score, row in ranked[:3]]


def update_failure_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    cr = _cr()
    status = cr.read_json(cr.FAILURE_MEMORY_STATUS_PATH, {})
    updated = {
        **status,
        'version': 1,
        'generated_at': date.today().isoformat(),
        'retrieval_events': int(status.get('retrieval_events', 0) or 0) + (1 if packet.get('failure_memory', {}).get('failure_memory_used') else 0),
        'last_packet_path': packet_path.as_posix(),
    }
    cr.write_json(cr.FAILURE_MEMORY_STATUS_PATH, updated)
