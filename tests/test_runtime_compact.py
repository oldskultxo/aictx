from __future__ import annotations

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aictx import cli, strategy_memory
from aictx.continuity import DECISIONS_PATH, HANDOFF_PATH, load_continuity_context
from aictx.report import build_real_usage_report
from aictx.runtime_compact import compact_repo_records
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_METRICS_DIR, REPO_MEMORY_DIR, REPO_STRATEGY_MEMORY_DIR, read_json, read_jsonl, write_json


def _ts(days_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + '\n')


def _gunzip_rows(path: Path) -> list[dict]:
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        return [json.loads(line) for line in handle.read().splitlines() if line.strip()]


def test_internal_compact_dry_run_does_not_mutate_live_files(tmp_path: Path):
    repo = tmp_path / 'repo'
    init_repo_scaffold(repo, update_gitignore=False)
    metrics_path = repo / REPO_METRICS_DIR / 'execution_logs.jsonl'
    strategies_path = repo / REPO_STRATEGY_MEMORY_DIR / 'strategies.jsonl'
    _append(metrics_path, {'task_id': 'old', 'timestamp': _ts(120), 'success': True})
    strategies_path.write_text('not-json\n', encoding='utf-8')

    before_metrics = metrics_path.read_text(encoding='utf-8')
    before_strategies = strategies_path.read_text(encoding='utf-8')

    payload = compact_repo_records(repo)

    assert payload['mode'] == 'dry_run'
    assert payload['summary']['rows_archived'] >= 1
    assert 'invalid_jsonl_lines:.aictx/strategy_memory/strategies.jsonl:1' in payload['warnings']
    assert metrics_path.read_text(encoding='utf-8') == before_metrics
    assert strategies_path.read_text(encoding='utf-8') == before_strategies
    assert not (repo / '.aictx' / 'archive').exists()


def test_internal_compact_cli_uses_provided_repo(tmp_path: Path, capsys):
    target_repo = tmp_path / 'target_repo'
    other_repo = tmp_path / 'other_repo'
    init_repo_scaffold(target_repo, update_gitignore=False)
    init_repo_scaffold(other_repo, update_gitignore=False)

    target_logs_path = target_repo / REPO_METRICS_DIR / 'execution_logs.jsonl'
    _append(target_logs_path, {'task_id': 'old-target', 'timestamp': _ts(120), 'success': True})

    parser = cli.build_parser()
    args = parser.parse_args([
        'internal',
        'compact',
        '--repo',
        str(target_repo),
        '--apply',
    ])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload['mode'] == 'apply'
    assert payload['summary']['rows_archived'] >= 1
    assert read_jsonl(target_logs_path) == []
    assert list((target_repo / '.aictx' / 'archive' / 'metrics').glob('execution_logs-*.jsonl.gz'))
    assert not (other_repo / '.aictx' / 'archive').exists()
    manifest_path = target_repo / payload['manifest_path']
    assert manifest_path.exists()


def test_internal_compact_keeps_old_decision_with_existing_related_path(tmp_path: Path):
    repo = tmp_path / 'repo'
    init_repo_scaffold(repo, update_gitignore=False)

    existing = repo / 'src' / 'aictx' / 'continuity.py'
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_text('def keep_me():\n    pass\n', encoding='utf-8')

    decisions_path = repo / DECISIONS_PATH
    _append(decisions_path, {
        'execution_id': 'exec-old-existing-path',
        'decision': 'old decision with existing path',
        'related_paths': ['src/aictx/continuity.py'],
        'timestamp': _ts(300),
    })
    _append(decisions_path, {
        'execution_id': 'exec-old-missing-path',
        'decision': 'old decision with missing path',
        'related_paths': ['missing/path.py'],
        'timestamp': _ts(300),
    })

    payload = compact_repo_records(repo, apply=True)

    live_decisions = read_jsonl(decisions_path)
    assert any(row.get('decision') == 'old decision with existing path' for row in live_decisions)
    assert not any(row.get('decision') == 'old decision with missing path' for row in live_decisions)
    archives = list((repo / '.aictx' / 'archive' / 'continuity').glob('decisions-*.jsonl.gz'))
    assert archives
    archived = _gunzip_rows(archives[0])
    assert any(row.get('decision') == 'old decision with missing path' for row in archived)
    assert payload['mode'] == 'apply'


def test_internal_compact_apply_archives_and_preserves_runtime_behaviors(tmp_path: Path):
    repo = tmp_path / 'repo'
    init_repo_scaffold(repo, update_gitignore=False)

    logs_path = repo / REPO_METRICS_DIR / 'execution_logs.jsonl'
    feedback_path = repo / REPO_METRICS_DIR / 'execution_feedback.jsonl'
    strategies_path = repo / REPO_STRATEGY_MEMORY_DIR / 'strategies.jsonl'
    failures_path = repo / '.aictx' / 'failure_memory' / 'failure_patterns.jsonl'
    decisions_path = repo / DECISIONS_PATH
    learnings_path = repo / REPO_MEMORY_DIR / 'workflow_learnings.jsonl'
    continuity_file = repo / 'src' / 'aictx' / 'continuity.py'
    continuity_file.parent.mkdir(parents=True, exist_ok=True)
    continuity_file.write_text('def banner():\n    pass\n', encoding='utf-8')

    for idx in range(2):
        _append(logs_path, {'task_id': f'old-log-{idx}', 'timestamp': _ts(120 + idx), 'success': True, 'files_opened': ['src/old.py']})
        _append(feedback_path, {'task_id': f'old-feedback-{idx}', 'timestamp': _ts(120 + idx), 'aictx_feedback': {'used_strategy': bool(idx % 2)}})
    _append(logs_path, {'task_id': 'recent-log', 'timestamp': _ts(1), 'success': True, 'files_opened': ['src/live.py']})
    _append(feedback_path, {'task_id': 'recent-feedback', 'timestamp': _ts(1), 'aictx_feedback': {'used_strategy': True}})

    for idx in range(25):
        _append(strategies_path, {
            'task_id': f'strategy-{idx}',
            'task_text': 'fix startup',
            'task_type': 'testing',
            'area_id': 'src/aictx/continuity',
            'entry_points': ['src/aictx/continuity.py'],
            'primary_entry_point': 'src/aictx/continuity.py',
            'files_used': ['src/aictx/continuity.py'],
            'files_edited': ['src/aictx/continuity.py'],
            'commands_executed': ['pytest -q tests/test_runtime_compact.py'],
            'tests_executed': ['tests/test_runtime_compact.py'],
            'notable_errors': [],
            'success': True,
            'is_failure': False,
            'timestamp': _ts(45 + idx),
        })
    duplicate = {
        'task_id': 'dup-task',
        'task_text': 'dup',
        'task_type': 'testing',
        'area_id': 'src/aictx/continuity',
        'entry_points': ['src/aictx/continuity.py'],
        'primary_entry_point': 'src/aictx/continuity.py',
        'files_used': ['src/aictx/continuity.py'],
        'files_edited': [],
        'commands_executed': [],
        'tests_executed': [],
        'notable_errors': [],
        'success': True,
        'is_failure': False,
        'timestamp': _ts(50),
    }
    _append(strategies_path, duplicate)
    _append(strategies_path, duplicate)
    with strategies_path.open('a', encoding='utf-8') as handle:
        handle.write('not-json\n')

    for idx in range(5):
        _append(failures_path, {
            'failure_id': f'failure::{idx}',
            'signature': 'startup-error',
            'failure_signature': 'startup-error',
            'task_type': 'bug_fixing',
            'area_id': 'src/aictx',
            'status': 'resolved',
            'timestamp': _ts(140 + idx),
        })
    _append(failures_path, {
        'failure_id': 'failure::open',
        'signature': 'startup-error-open',
        'failure_signature': 'startup-error-open',
        'task_type': 'bug_fixing',
        'area_id': 'src/aictx',
        'status': 'open',
        'timestamp': _ts(200),
    })

    _append(decisions_path, {
        'execution_id': 'exec-old-alpha',
        'decision': 'old alpha',
        'subsystem': 'alpha',
        'related_paths': ['missing.py'],
        'timestamp': _ts(300),
    })
    _append(decisions_path, {
        'execution_id': 'exec-new-alpha',
        'decision': 'new alpha',
        'subsystem': 'alpha',
        'related_paths': ['src/aictx/continuity.py'],
        'timestamp': _ts(10),
    })
    for idx in range(102):
        _append(decisions_path, {
            'execution_id': f'exec-{idx}',
            'decision': f'decision {idx}',
            'related_paths': ['src/aictx/continuity.py'],
            'timestamp': _ts(1),
        })

    for idx in range(102):
        _append(learnings_path, {
            'id': f'learning::{idx}',
            'summary': f'learning {idx}',
            'task_type': 'testing',
            'execution_mode': 'plain',
            'created_at': _ts(idx),
        })
    _append(learnings_path, {
        'id': 'learning::dup-a',
        'summary': 'duplicated learning',
        'task_type': 'testing',
        'execution_mode': 'plain',
        'created_at': _ts(1),
    })
    _append(learnings_path, {
        'id': 'learning::dup-b',
        'summary': 'duplicated learning',
        'task_type': 'testing',
        'execution_mode': 'plain',
        'created_at': _ts(2),
    })

    write_json(repo / HANDOFF_PATH, {'summary': 'resume', 'updated_at': _ts(1), 'recommended_starting_points': ['src/aictx/continuity.py']})
    write_json(repo / '.aictx' / 'repo_map' / 'config.json', {'enabled': True})
    write_json(repo / '.aictx' / 'repo_map' / 'status.json', {'available': False, 'last_refresh_status': 'never'})

    payload = compact_repo_records(repo, apply=True)

    assert payload['mode'] == 'apply'
    assert payload['manifest_path'].startswith('.aictx/archive/manifests/compact-')
    manifest_path = repo / payload['manifest_path']
    assert manifest_path.exists()
    manifest = read_json(manifest_path, {})
    assert manifest['mode'] == 'apply'

    assert [row['task_id'] for row in read_jsonl(logs_path)] == ['recent-log']
    assert [row['task_id'] for row in read_jsonl(feedback_path)] == ['recent-feedback']
    assert len(list((repo / '.aictx' / 'archive' / 'metrics').glob('execution_logs-*.jsonl.gz'))) >= 1
    assert len(list((repo / '.aictx' / 'archive' / 'metrics').glob('execution_feedback-*.jsonl.gz'))) >= 1

    live_strategies_text = strategies_path.read_text(encoding='utf-8')
    live_strategies = read_jsonl(strategies_path)
    assert 'not-json' in live_strategies_text
    assert len(live_strategies) == 20
    assert len([row for row in live_strategies if row['task_id'] == 'dup-task']) == 1
    assert any(row['task_id'] == 'strategy-24' for row in _gunzip_rows(next((repo / '.aictx' / 'archive' / 'strategy_memory').glob('strategies-*.jsonl.gz'))))

    live_failures = read_jsonl(failures_path)
    assert len([row for row in live_failures if row.get('status') == 'resolved']) == 3
    assert any(row['failure_id'] == 'failure::open' for row in live_failures)
    assert read_json(repo / '.aictx' / 'failure_memory' / 'failure_index.json', {})['failure_count'] == len(live_failures)

    live_decisions = read_jsonl(decisions_path)
    assert len(live_decisions) <= 100
    assert any(row.get('decision') == 'new alpha' for row in live_decisions)
    assert not any(row.get('decision') == 'old alpha' for row in live_decisions)

    live_learnings = read_jsonl(learnings_path)
    assert len(live_learnings) == 100
    assert len([row for row in live_learnings if row.get('summary') == 'duplicated learning']) == 1

    selected = strategy_memory.select_strategy(repo, 'testing', files=['src/aictx/continuity.py'], primary_entry_point='src/aictx/continuity.py', request_text='fix startup')
    assert selected is not None
    context = load_continuity_context(repo, task_type='testing', request_text='resume continuity reasoning', files=['src/aictx/continuity.py'])
    assert context['decisions']
    report = build_real_usage_report(repo)
    assert report['total_executions'] == 1
