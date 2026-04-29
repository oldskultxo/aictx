from __future__ import annotations

import gzip
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .continuity import DECISIONS_PATH, STALENESS_PATH, _decision_ref, refresh_staleness
from .failure_memory import FAILURE_PATTERNS_PATH, write_failure_index
from .report import build_repo_map_report
from .runtime_io import now_iso
from .state import REPO_MEMORY_DIR, REPO_METRICS_DIR, REPO_STRATEGY_MEMORY_DIR, read_json, write_json
from .strategy_memory import STRATEGIES_PATH, _area_subsystem

ARCHIVE_ROOT = Path('.aictx') / 'archive'
MANIFESTS_DIR = ARCHIVE_ROOT / 'manifests'
MAINTENANCE_STATUS_PATH = REPO_METRICS_DIR / 'maintenance_status.json'
EXECUTION_LOGS_PATH = REPO_METRICS_DIR / 'execution_logs.jsonl'
EXECUTION_FEEDBACK_PATH = REPO_METRICS_DIR / 'execution_feedback.jsonl'
WORKFLOW_LEARNINGS_PATH = REPO_MEMORY_DIR / 'workflow_learnings.jsonl'
MAINTENANCE_WARNING_THRESHOLD_BYTES = 100 * 1024 * 1024
MAINTENANCE_STRONG_THRESHOLD_BYTES = 250 * 1024 * 1024
MAINTENANCE_WARNING_COOLDOWN_DAYS = 3
MAINTENANCE_STRONG_COOLDOWN_DAYS = 7


@dataclass
class JsonlEntry:
    line_no: int
    raw: str
    valid: bool
    row: dict[str, Any] | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _stamp(value: datetime) -> str:
    return value.strftime('%Y%m%dT%H%M%SZ')


def _month_stamp(value: datetime) -> str:
    return value.strftime('%Y-%m')


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or '').strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _path_str(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()


def _file_bytes(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _repo_dir_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for child in path.rglob('*'):
        if child.is_file():
            total += _file_bytes(child)
    return total


def _repo_live_dir_bytes(path: Path, *, exclude: Path) -> int:
    if not path.exists():
        return 0
    exclude = exclude.resolve()
    total = 0
    for child in path.rglob('*'):
        if not child.is_file():
            continue
        try:
            child.relative_to(exclude)
            continue
        except ValueError:
            pass
        total += _file_bytes(child)
    return total


def _format_megabytes(total_bytes: int) -> str:
    if total_bytes <= 0:
        return '0 MB'
    value = max(1, round(total_bytes / (1024 * 1024)))
    return f'{value} MB'


def _cooldown_days_for_severity(severity: str) -> int:
    return MAINTENANCE_STRONG_COOLDOWN_DAYS if severity == 'strong' else MAINTENANCE_WARNING_COOLDOWN_DAYS


def evaluate_maintenance_notice(repo_root: Path, *, now: datetime | None = None, update_status: bool = True) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    current = now or _now()
    aictx_root = repo_root / '.aictx'
    archive_root = repo_root / ARCHIVE_ROOT
    live_bytes = _repo_live_dir_bytes(aictx_root, exclude=archive_root)
    archive_bytes = _repo_dir_bytes(archive_root)
    total_bytes = live_bytes + archive_bytes
    severity = ''
    if live_bytes >= MAINTENANCE_STRONG_THRESHOLD_BYTES:
        severity = 'strong'
    elif live_bytes >= MAINTENANCE_WARNING_THRESHOLD_BYTES:
        severity = 'warning'

    status_path = repo_root / MAINTENANCE_STATUS_PATH
    status = read_json(status_path, {})
    last_warning_at = _parse_iso(status.get('last_warning_at'))
    last_warning_severity = str(status.get('last_warning_severity') or '')
    cooldown_days = _cooldown_days_for_severity(severity or last_warning_severity or 'warning')
    cooldown_until = ''
    if last_warning_at is not None:
        cooldown_until = (last_warning_at + timedelta(days=cooldown_days)).isoformat().replace('+00:00', 'Z')
    should_warn = False
    if severity:
        if last_warning_at is None:
            should_warn = True
        else:
            should_warn = current >= last_warning_at + timedelta(days=cooldown_days)

    message = ''
    if should_warn:
        message = f"Maintenance: .aictx live history high ({_format_megabytes(live_bytes)}). Recommend: aictx internal compact --repo ."

    payload = {
        'active': bool(message),
        'severity': severity or 'none',
        'reason': 'aictx_size_high' if severity else 'none',
        'live_bytes': live_bytes,
        'archive_bytes': archive_bytes,
        'total_bytes': total_bytes,
        'live_size_display': _format_megabytes(live_bytes),
        'archive_size_display': _format_megabytes(archive_bytes),
        'total_size_display': _format_megabytes(total_bytes),
        'command': 'aictx internal compact --repo .',
        'message': message,
        'cooldown_days': cooldown_days,
        'cooldown_until': cooldown_until,
    }
    if update_status:
        next_status = {
            'last_checked_at': current.isoformat().replace('+00:00', 'Z'),
            'last_total_bytes': total_bytes,
        }
        if should_warn:
            next_status.update({
                'last_warning_at': current.isoformat().replace('+00:00', 'Z'),
                'last_warning_reason': 'aictx_size_high',
                'last_warning_severity': severity,
                'cooldown_until': (current + timedelta(days=cooldown_days)).isoformat().replace('+00:00', 'Z'),
            })
        else:
            if last_warning_at is not None:
                next_status['last_warning_at'] = last_warning_at.isoformat().replace('+00:00', 'Z')
            if status.get('last_warning_reason'):
                next_status['last_warning_reason'] = str(status.get('last_warning_reason'))
            if last_warning_severity:
                next_status['last_warning_severity'] = last_warning_severity
            if cooldown_until:
                next_status['cooldown_until'] = cooldown_until
        write_json(status_path, next_status)
    return payload


def _load_jsonl_entries(path: Path, repo_root: Path, warnings: list[str]) -> list[JsonlEntry]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError:
        warnings.append(f'unreadable:{_path_str(path, repo_root)}')
        return []
    entries: list[JsonlEntry] = []
    invalid_lines = 0
    for index, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if not stripped:
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            invalid_lines += 1
            entries.append(JsonlEntry(index, raw, False, None))
            continue
        if not isinstance(payload, dict):
            invalid_lines += 1
            entries.append(JsonlEntry(index, raw, False, None))
            continue
        entries.append(JsonlEntry(index, raw, True, payload))
    if invalid_lines:
        warnings.append(f'invalid_jsonl_lines:{_path_str(path, repo_root)}:{invalid_lines}')
    return entries


def _rows_to_text(entries: list[JsonlEntry]) -> str:
    lines = [entry.raw if not entry.valid else json.dumps(entry.row, ensure_ascii=False) for entry in entries]
    return ('\n'.join(lines) + '\n') if lines else ''


def _row_timestamp(row: dict[str, Any], *keys: str) -> datetime | None:
    for key in keys:
        parsed = _parse_iso(row.get(key))
        if parsed is not None:
            return parsed
    return None


def _row_has_existing_paths(repo_root: Path, row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    if not isinstance(value, list):
        return False
    for raw in value:
        path = str(raw or '').strip()
        if not path:
            continue
        if (repo_root / path).exists():
            return True
    return False


def _append_gzip_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, 'at', encoding='utf-8') as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def _rewrite_jsonl(path: Path, entries: list[JsonlEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_rows_to_text(entries), encoding='utf-8')


def _manifest_base(repo_root: Path, mode: str, timestamp: datetime) -> dict[str, Any]:
    return {
        'generated_at': timestamp.isoformat().replace('+00:00', 'Z'),
        'mode': mode,
        'repo_root': repo_root.as_posix(),
        'rules': {
            'metrics_days': 60,
            'strategies_recent_days': 30,
            'strategies_per_task_type': 20,
            'strategies_per_subsystem': 10,
            'failures_resolved_days': 90,
            'failures_resolved_per_signature': 3,
            'decisions_recent_days': 180,
            'decisions_live_cap': 100,
            'workflow_learnings_live_cap': 100,
        },
        'artifacts': [],
        'archive_paths': [],
        'warnings': [],
    }


def _metrics_plan(repo_root: Path, path: Path, now: datetime, warnings: list[str]) -> dict[str, Any]:
    live_path = repo_root / path
    entries = _load_jsonl_entries(live_path, repo_root, warnings)
    cutoff = now - timedelta(days=60)
    kept_entries: list[JsonlEntry] = []
    archived_by_month: dict[str, list[dict[str, Any]]] = defaultdict(list)
    archived_valid = 0
    skipped = 0
    for entry in entries:
        if not entry.valid or entry.row is None:
            kept_entries.append(entry)
            skipped += 1
            continue
        parsed = _row_timestamp(entry.row, 'timestamp', 'recorded_at')
        if parsed is None or parsed >= cutoff:
            kept_entries.append(entry)
            if parsed is None:
                skipped += 1
            continue
        archived_by_month[_month_stamp(parsed)].append(entry.row)
        archived_valid += 1
    after_entries = [entry for entry in kept_entries]
    before_bytes = _file_bytes(live_path)
    after_bytes = len(_rows_to_text(after_entries).encode('utf-8'))
    archive_paths = {
        month: repo_root / ARCHIVE_ROOT / 'metrics' / f'{path.stem}-{month}.jsonl.gz'
        for month in archived_by_month
    }
    return {
        'path': path.as_posix(),
        'kind': 'metrics',
        'entries': entries,
        'kept_entries': after_entries,
        'archived_by_month': archived_by_month,
        'archive_paths': archive_paths,
        'before_rows': len(entries),
        'after_rows': len(after_entries),
        'kept_rows': sum(1 for entry in after_entries if entry.valid),
        'archived_rows': archived_valid,
        'deduped_rows': 0,
        'skipped_rows': skipped,
        'before_bytes': before_bytes,
        'after_bytes': after_bytes,
    }


def _strategies_plan(repo_root: Path, now: datetime, warnings: list[str]) -> dict[str, Any]:
    path = repo_root / STRATEGIES_PATH
    entries = _load_jsonl_entries(path, repo_root, warnings)
    cutoff = now - timedelta(days=30)
    valid_entries = [entry for entry in entries if entry.valid and entry.row is not None]
    recent_keep: set[int] = set()
    per_task: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    per_subsystem: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    seen_fingerprints: set[tuple[str, str, str, str]] = set()
    deduped_indexes: set[int] = set()
    for index, entry in enumerate(valid_entries):
        row = entry.row or {}
        fingerprint = (
            str(row.get('task_id') or '').strip(),
            str(row.get('task_type') or '').strip(),
            str(row.get('primary_entry_point') or '').strip(),
            str(row.get('timestamp') or '').strip(),
        )
        if fingerprint in seen_fingerprints:
            deduped_indexes.add(index)
            continue
        seen_fingerprints.add(fingerprint)
        parsed = _row_timestamp(row, 'timestamp')
        if parsed is None or parsed >= cutoff:
            recent_keep.add(index)
            continue
        key = str(row.get('task_type') or 'unknown')
        per_task[key].append((parsed, index))
        subsystem = _area_subsystem(str(row.get('area_id') or ''))
        if subsystem:
            per_subsystem[subsystem].append((parsed, index))
    keep_indexes = set(recent_keep)
    for values in per_task.values():
        for _parsed, index in sorted(values, key=lambda item: item[0], reverse=True)[:20]:
            if index not in deduped_indexes:
                keep_indexes.add(index)
    for values in per_subsystem.values():
        for _parsed, index in sorted(values, key=lambda item: item[0], reverse=True)[:10]:
            if index not in deduped_indexes:
                keep_indexes.add(index)
    kept_entries: list[JsonlEntry] = []
    archive_rows: list[dict[str, Any]] = []
    archived_rows = 0
    deduped_rows = 0
    skipped = 0
    valid_position = 0
    for entry in entries:
        if not entry.valid or entry.row is None:
            kept_entries.append(entry)
            skipped += 1
            continue
        if valid_position in deduped_indexes:
            deduped_rows += 1
        elif valid_position in keep_indexes:
            kept_entries.append(entry)
        else:
            archive_rows.append(entry.row)
            archived_rows += 1
        valid_position += 1
    before_bytes = _file_bytes(path)
    after_bytes = len(_rows_to_text(kept_entries).encode('utf-8'))
    archive_path = repo_root / ARCHIVE_ROOT / 'strategy_memory' / f'strategies-{_stamp(now)}.jsonl.gz'
    return {
        'path': STRATEGIES_PATH.as_posix(),
        'kind': 'strategy_memory',
        'entries': entries,
        'kept_entries': kept_entries,
        'archive_rows': archive_rows,
        'archive_path': archive_path,
        'before_rows': len(entries),
        'after_rows': len(kept_entries),
        'kept_rows': sum(1 for entry in kept_entries if entry.valid),
        'archived_rows': archived_rows,
        'deduped_rows': deduped_rows,
        'skipped_rows': skipped,
        'before_bytes': before_bytes,
        'after_bytes': after_bytes,
    }


def _failures_plan(repo_root: Path, now: datetime, warnings: list[str]) -> dict[str, Any]:
    path = repo_root / FAILURE_PATTERNS_PATH
    entries = _load_jsonl_entries(path, repo_root, warnings)
    cutoff = now - timedelta(days=90)
    resolved_by_signature: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    valid_entries = [entry for entry in entries if entry.valid and entry.row is not None]
    always_keep: set[int] = set()
    for index, entry in enumerate(valid_entries):
        row = entry.row or {}
        status = str(row.get('status') or '').strip()
        if status != 'resolved':
            always_keep.add(index)
            continue
        parsed = _row_timestamp(row, 'timestamp', 'updated_at')
        if parsed is None or parsed >= cutoff:
            always_keep.add(index)
            continue
        signature = str(row.get('signature') or row.get('failure_signature') or 'unknown').strip() or 'unknown'
        resolved_by_signature[signature].append((parsed, index))
    keep_indexes = set(always_keep)
    for values in resolved_by_signature.values():
        for _parsed, index in sorted(values, key=lambda item: item[0], reverse=True)[:3]:
            keep_indexes.add(index)
    kept_entries: list[JsonlEntry] = []
    archive_rows: list[dict[str, Any]] = []
    archived_rows = 0
    skipped = 0
    valid_position = 0
    for entry in entries:
        if not entry.valid or entry.row is None:
            kept_entries.append(entry)
            skipped += 1
            continue
        if valid_position in keep_indexes:
            kept_entries.append(entry)
        else:
            archive_rows.append(entry.row)
            archived_rows += 1
        valid_position += 1
    before_bytes = _file_bytes(path)
    after_bytes = len(_rows_to_text(kept_entries).encode('utf-8'))
    archive_path = repo_root / ARCHIVE_ROOT / 'failure_memory' / f'failure_patterns-{_stamp(now)}.jsonl.gz'
    return {
        'path': FAILURE_PATTERNS_PATH.as_posix(),
        'kind': 'failure_memory',
        'entries': entries,
        'kept_entries': kept_entries,
        'archive_rows': archive_rows,
        'archive_path': archive_path,
        'before_rows': len(entries),
        'after_rows': len(kept_entries),
        'kept_rows': sum(1 for entry in kept_entries if entry.valid),
        'archived_rows': archived_rows,
        'deduped_rows': 0,
        'skipped_rows': skipped,
        'before_bytes': before_bytes,
        'after_bytes': after_bytes,
    }


def _decisions_plan(repo_root: Path, now: datetime, warnings: list[str]) -> dict[str, Any]:
    path = repo_root / DECISIONS_PATH
    staleness = refresh_staleness(repo_root, now=now, persist=False)['staleness']
    stale_refs = {str(item.get('ref') or '') for item in staleness.get('decisions', []) if isinstance(item, dict)}
    entries = _load_jsonl_entries(path, repo_root, warnings)
    cutoff = now - timedelta(days=180)
    valid_entries = [entry for entry in entries if entry.valid and entry.row is not None]
    latest_by_subsystem: dict[str, int] = {}
    for index, entry in enumerate(valid_entries):
        subsystem = str((entry.row or {}).get('subsystem') or '').strip()
        if subsystem:
            latest_by_subsystem[subsystem] = index
    keep_indexes: set[int] = set()
    anchor_indexes: set[int] = set()
    for index, entry in enumerate(valid_entries):
        row = entry.row or {}
        ref = _decision_ref(row, index)
        subsystem = str(row.get('subsystem') or '').strip()
        is_latest_subsystem = bool(subsystem) and latest_by_subsystem.get(subsystem) == index
        if is_latest_subsystem:
            anchor_indexes.add(index)
            keep_indexes.add(index)
            continue
        if ref in stale_refs:
            continue
        parsed = _row_timestamp(row, 'timestamp', 'updated_at')
        is_recent = parsed is None or parsed >= cutoff
        has_existing_paths = _row_has_existing_paths(repo_root, row, 'related_paths')
        if is_recent or has_existing_paths:
            keep_indexes.add(index)
    if len(keep_indexes) > 100:
        remaining_budget = max(0, 100 - len(anchor_indexes))
        ranked_non_anchor = sorted(
            [idx for idx in keep_indexes if idx not in anchor_indexes],
            key=lambda idx: _row_timestamp(valid_entries[idx].row or {}, 'timestamp', 'updated_at') or datetime.max.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        keep_indexes = set(anchor_indexes).union(ranked_non_anchor[:remaining_budget])
    kept_entries: list[JsonlEntry] = []
    archive_rows: list[dict[str, Any]] = []
    archived_rows = 0
    skipped = 0
    valid_position = 0
    for entry in entries:
        if not entry.valid or entry.row is None:
            kept_entries.append(entry)
            skipped += 1
            continue
        if valid_position in keep_indexes:
            kept_entries.append(entry)
        else:
            archive_rows.append(entry.row)
            archived_rows += 1
        valid_position += 1
    before_bytes = _file_bytes(path)
    after_bytes = len(_rows_to_text(kept_entries).encode('utf-8'))
    archive_path = repo_root / ARCHIVE_ROOT / 'continuity' / f'decisions-{_stamp(now)}.jsonl.gz'
    return {
        'path': DECISIONS_PATH.as_posix(),
        'kind': 'decisions',
        'entries': entries,
        'kept_entries': kept_entries,
        'archive_rows': archive_rows,
        'archive_path': archive_path,
        'staleness': staleness,
        'before_rows': len(entries),
        'after_rows': len(kept_entries),
        'kept_rows': sum(1 for entry in kept_entries if entry.valid),
        'archived_rows': archived_rows,
        'deduped_rows': 0,
        'skipped_rows': skipped,
        'before_bytes': before_bytes,
        'after_bytes': after_bytes,
    }


def _workflow_learnings_plan(repo_root: Path, now: datetime, warnings: list[str]) -> dict[str, Any]:
    path = repo_root / WORKFLOW_LEARNINGS_PATH
    entries = _load_jsonl_entries(path, repo_root, warnings)
    valid_entries = [entry for entry in entries if entry.valid and entry.row is not None]
    deduped_indexes: set[int] = set()
    seen: set[tuple[str, str, str]] = set()
    for index, entry in enumerate(valid_entries):
        row = entry.row or {}
        key = (
            str(row.get('summary') or '').strip(),
            str(row.get('task_type') or '').strip(),
            str(row.get('execution_mode') or '').strip(),
        )
        if key in seen:
            deduped_indexes.add(index)
            continue
        seen.add(key)
    kept_candidates = [
        (index, _row_timestamp(entry.row or {}, 'created_at', 'timestamp') or datetime.min.replace(tzinfo=timezone.utc))
        for index, entry in enumerate(valid_entries)
        if index not in deduped_indexes
    ]
    keep_indexes = {index for index, _parsed in sorted(kept_candidates, key=lambda item: item[1], reverse=True)[:100]}
    kept_entries: list[JsonlEntry] = []
    archive_rows: list[dict[str, Any]] = []
    archived_rows = 0
    deduped_rows = 0
    skipped = 0
    valid_position = 0
    for entry in entries:
        if not entry.valid or entry.row is None:
            kept_entries.append(entry)
            skipped += 1
            continue
        if valid_position in deduped_indexes:
            deduped_rows += 1
        elif valid_position in keep_indexes:
            kept_entries.append(entry)
        else:
            archive_rows.append(entry.row)
            archived_rows += 1
        valid_position += 1
    before_bytes = _file_bytes(path)
    after_bytes = len(_rows_to_text(kept_entries).encode('utf-8'))
    archive_path = repo_root / ARCHIVE_ROOT / 'memory' / f'workflow_learnings-{_stamp(now)}.jsonl.gz'
    return {
        'path': WORKFLOW_LEARNINGS_PATH.as_posix(),
        'kind': 'workflow_learnings',
        'entries': entries,
        'kept_entries': kept_entries,
        'archive_rows': archive_rows,
        'archive_path': archive_path,
        'before_rows': len(entries),
        'after_rows': len(kept_entries),
        'kept_rows': sum(1 for entry in kept_entries if entry.valid),
        'archived_rows': archived_rows,
        'deduped_rows': deduped_rows,
        'skipped_rows': skipped,
        'before_bytes': before_bytes,
        'after_bytes': after_bytes,
    }


def _artifact_summary(plan: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    archive_paths: list[str] = []
    if 'archive_paths' in plan:
        archive_paths = [_path_str(path, repo_root) for path in plan['archive_paths'].values()]
    elif plan.get('archive_rows'):
        archive_paths = [_path_str(plan['archive_path'], repo_root)]
    return {
        'path': plan['path'],
        'kind': plan['kind'],
        'before_rows': plan['before_rows'],
        'after_rows': plan['after_rows'],
        'kept_rows': plan['kept_rows'],
        'archived_rows': plan['archived_rows'],
        'deduped_rows': plan['deduped_rows'],
        'skipped_rows': plan['skipped_rows'],
        'before_bytes': plan['before_bytes'],
        'after_bytes': plan['after_bytes'],
        'archive_paths': archive_paths,
    }


def compact_repo_records(repo_root: Path, *, apply: bool = False) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    now = _now()
    warnings: list[str] = []
    mode = 'apply' if apply else 'dry_run'
    report = _manifest_base(repo_root, mode, now)

    plans = [
        _metrics_plan(repo_root, EXECUTION_LOGS_PATH, now, warnings),
        _metrics_plan(repo_root, EXECUTION_FEEDBACK_PATH, now, warnings),
        _strategies_plan(repo_root, now, warnings),
        _failures_plan(repo_root, now, warnings),
        _decisions_plan(repo_root, now, warnings),
        _workflow_learnings_plan(repo_root, now, warnings),
    ]
    report['artifacts'] = [_artifact_summary(plan, repo_root) for plan in plans]
    report['warnings'] = warnings
    report['repo_map'] = {
        **build_repo_map_report(repo_root),
        'bytes': _repo_dir_bytes(repo_root / '.aictx' / 'repo_map'),
    }

    archive_paths: list[Path] = []
    if apply:
        for plan in plans:
            if 'archived_by_month' in plan:
                for month, rows in plan['archived_by_month'].items():
                    archive_path = plan['archive_paths'][month]
                    _append_gzip_jsonl(archive_path, rows)
                    archive_paths.append(archive_path)
            elif plan.get('archive_rows'):
                archive_path = plan['archive_path']
                _append_gzip_jsonl(archive_path, plan['archive_rows'])
                if plan['archive_rows']:
                    archive_paths.append(archive_path)
            live_path = repo_root / Path(plan['path'])
            _rewrite_jsonl(live_path, plan['kept_entries'])
            if plan['kind'] == 'failure_memory':
                write_failure_index(repo_root, [entry.row for entry in plan['kept_entries'] if entry.valid and entry.row is not None])
        staleness_payload = refresh_staleness(repo_root, now=now)['staleness']
        report['staleness'] = staleness_payload
        manifest_path = repo_root / MANIFESTS_DIR / f'compact-{_stamp(now)}.json'
        report['archive_paths'] = sorted({_path_str(path, repo_root) for path in archive_paths})
        report['manifest_path'] = _path_str(manifest_path, repo_root)
        write_json(manifest_path, report)
    else:
        report['archive_paths'] = sorted({path for artifact in report['artifacts'] for path in artifact['archive_paths']})
        report['manifest_path'] = ''
        decision_plan = next((plan for plan in plans if plan['kind'] == 'decisions'), None)
        report['staleness'] = dict(decision_plan.get('staleness', {})) if isinstance(decision_plan, dict) else read_json(repo_root / STALENESS_PATH, {})

    summary = {
        'artifacts_scanned': len(plans),
        'rows_before': sum(int(plan['before_rows']) for plan in plans),
        'rows_after': sum(int(plan['after_rows']) for plan in plans),
        'rows_archived': sum(int(plan['archived_rows']) for plan in plans),
        'rows_deduped': sum(int(plan['deduped_rows']) for plan in plans),
        'rows_skipped': sum(int(plan['skipped_rows']) for plan in plans),
        'bytes_before': sum(int(plan['before_bytes']) for plan in plans),
        'bytes_after': sum(int(plan['after_bytes']) for plan in plans),
    }
    report['summary'] = summary
    return report
