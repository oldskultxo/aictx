from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr
    return cr


def canonical_task_types() -> list[str]:
    return list(_cr().TASK_TYPES)


def resolve_task_type_alias(value: str | None) -> str:
    cr = _cr()
    return cr.LEGACY_TASK_TYPE_ALIASES.get(str(value or '').strip().lower(), str(value or '').strip().lower())


def ensure_task_memory_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    cr.write_json(
        cr.TASK_MEMORY_TAXONOMY_PATH,
        {
            'version': 3,
            'installed_iteration': 8,
            'generated_at': date.today().isoformat(),
            'task_types': canonical_task_types(),
            'aliases': dict(cr.LEGACY_TASK_TYPE_ALIASES),
            'canonical_only_storage': True,
        },
    )
    cr.write_text(
        cr.TASK_MEMORY_RULES_PATH,
        '# task resolution rules\n\n'
        '- Resolution order: explicit task type -> packet/runtime metadata -> heuristic task inference -> `unknown`.\n'
        '- Stable canonical task types: `bug_fixing`, `refactoring`, `testing`, `performance`, `architecture`, `feature_work`, `unknown`.\n'
        '- Alias task types remain supported in read/normalization only and are not written as standalone derived buckets.\n'
        '- Existing markdown notes remain canonical; `.ai_context_engine/task_memory/` is derived from them.\n'
        '- Retrieval prefers the resolved task bucket first, then `unknown`, then deterministic fallback matches only when needed.\n'
        '- Ambiguous notes stay in `unknown` rather than being force-migrated.\n',
    )
    if not cr.TASK_MEMORY_STATUS_PATH.exists():
        cr.write_json(
            cr.TASK_MEMORY_STATUS_PATH,
            {
                'version': 3,
                'installed_iteration': 8,
                'task_taxonomy_version': 3,
                'generated_at': date.today().isoformat(),
                'task_types': canonical_task_types(),
                'records_by_task_type': {task_type: 0 for task_type in canonical_task_types()},
                'resolved_task_packets': 0,
                'fallback_to_general_events': 0,
                'task_memory_write_count': 0,
                'manual_records': 0,
                'last_resolved_task_type': 'unknown',
                'last_packet_path': '',
                'legacy_alias_writes_enabled': False,
            },
        )
    if not cr.TASK_MEMORY_HISTORY_PATH.exists():
        cr.write_text(cr.TASK_MEMORY_HISTORY_PATH, '')


def category_summary_path(category: str) -> Path:
    cr = _cr()
    canonical = resolve_task_type_alias(category)
    return cr.TASK_MEMORY_DIR / canonical / 'summary.json'


def build_task_memory_artifacts(rows: list[dict[str, Any]]) -> dict[str, int]:
    cr = _cr()
    ensure_task_memory_artifacts()
    records_by_task_type = {task_type: 0 for task_type in canonical_task_types()}
    for task_type in canonical_task_types():
        derived_rows = [
            row for row in rows
            if row.get('type') != 'user_preference' and cr.normalize_task_type(row.get('task_type')) == task_type
        ]
        task_rows = derived_rows + cr.manual_task_memory_records(task_type)
        task_rows.sort(key=lambda row: (row.get('project') or '', row.get('path') or '', row.get('id') or ''))
        records_by_task_type[task_type] = len(task_rows)
        cr.write_jsonl(cr.TASK_MEMORY_DIR / task_type / 'records.jsonl', task_rows)
        summary = cr.summarize_task_memory_rows(task_type, task_rows)
        cr.write_json(
            cr.TASK_MEMORY_DIR / task_type / 'summary.json',
            {
                'task_type': task_type,
                'records': len(task_rows),
                'derived_records': len(derived_rows),
                'manual_records': max(0, len(task_rows) - len(derived_rows)),
                'projects': sorted({str(row.get('project')) for row in task_rows if row.get('project')}),
                'updated_at': date.today().isoformat(),
                'aliases_read_only': sorted(alias for alias, canonical in cr.LEGACY_TASK_TYPE_ALIASES.items() if canonical == task_type),
                **summary,
            },
        )
        cr.write_text(
            cr.TASK_MEMORY_DIR / task_type / 'summary.md',
            '\n'.join(
                [
                    f'# {task_type} task memory',
                    '',
                    f'- Records: {len(task_rows)}',
                    f'- Derived records: {len(derived_rows)}',
                    f'- Manual records: {max(0, len(task_rows) - len(derived_rows))}',
                    f"- Common locations: {', '.join(summary['common_locations']) if summary['common_locations'] else 'none'}",
                    f"- Patterns: {', '.join(summary['patterns']) if summary['patterns'] else 'none'}",
                    f"- Preferred validation: {'; '.join(summary['preferred_validation']) if summary['preferred_validation'] else 'none'}",
                ]
            ) + '\n',
        )
    previous_status = cr.read_json(cr.TASK_MEMORY_STATUS_PATH, {})
    cr.write_json(
        cr.TASK_MEMORY_STATUS_PATH,
        {
            **previous_status,
            'version': 3,
            'installed_iteration': 8,
            'task_taxonomy_version': 3,
            'generated_at': date.today().isoformat(),
            'task_types': canonical_task_types(),
            'records_by_task_type': records_by_task_type,
            'task_memory_write_count': sum(records_by_task_type.values()),
            'manual_records': sum(len(cr.manual_task_memory_records(task_type)) for task_type in canonical_task_types()),
            'legacy_alias_writes_enabled': False,
        },
    )
    return records_by_task_type


def update_task_memory_status(packet: dict[str, Any], packet_path: Path) -> None:
    cr = _cr()
    status = cr.read_json(cr.TASK_MEMORY_STATUS_PATH, {})
    packets = int(status.get('resolved_task_packets', 0) or 0) + 1
    fallback_event = 1 if packet.get('task_memory', {}).get('fallback_to_general') else 0
    updated = {
        **status,
        'version': 3,
        'installed_iteration': 8,
        'task_taxonomy_version': 3,
        'generated_at': date.today().isoformat(),
        'resolved_task_packets': packets,
        'fallback_to_general_events': int(status.get('fallback_to_general_events', 0) or 0) + fallback_event,
        'last_resolved_task_type': packet.get('task_type', 'unknown'),
        'last_packet_path': packet_path.as_posix(),
        'last_queried_categories': packet.get('task_memory', {}).get('queried_categories', []),
    }
    cr.write_json(cr.TASK_MEMORY_STATUS_PATH, updated)
    history = cr.read_jsonl(cr.TASK_MEMORY_HISTORY_PATH)
    history.append(
        {
            'generated_at': date.today().isoformat(),
            'task': packet.get('task'),
            'task_type': packet.get('task_type', 'unknown'),
            'task_memory_used': bool(packet.get('task_memory', {}).get('task_specific_memory_used')),
            'fallback_to_general': bool(packet.get('task_memory', {}).get('fallback_to_general')),
            'queried_categories': packet.get('task_memory', {}).get('queried_categories', []),
        }
    )
    cr.write_jsonl(cr.TASK_MEMORY_HISTORY_PATH, history[-50:])
