from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from .runtime_io import slugify, truncate_words


DEFAULT_COST_CONFIG = {
    'version': 1,
    'budget_target_tokens': 3000,
    'soft_limit_tokens': 2600,
    'hard_limit_tokens': 3200,
    'summary_max_words': 20,
    'mandatory_summary_max_words': 28,
    'max_items_per_section': {
        'user_preferences': 5,
        'constraints': 5,
        'architecture_rules': 5,
        'relevant_memory': 5,
        'relevant_patterns': 5,
        'validation_recipes': 5,
        'relevant_failures': 3,
        'relevant_graph_context': 4,
        'repo_scope': 8,
        'known_patterns': 10,
    },
}

SECTION_RULES = {
    'user_preferences': {'mandatory': True, 'priority': 4.0},
    'constraints': {'mandatory': True, 'priority': 3.8},
    'architecture_rules': {'mandatory': True, 'priority': 3.6},
    'architecture_decisions': {'mandatory': False, 'priority': 2.8, 'mirror_of': 'architecture_rules'},
    'relevant_memory': {'mandatory': False, 'priority': 3.2},
    'relevant_patterns': {'mandatory': False, 'priority': 2.4},
    'validation_recipes': {'mandatory': False, 'priority': 2.3},
    'relevant_failures': {'mandatory': False, 'priority': 3.0},
    'relevant_graph_context': {'mandatory': False, 'priority': 2.9},
    'knowledge_artifacts': {'mandatory': False, 'priority': 2.7},
    'repo_scope': {'mandatory': False, 'priority': 1.4},
    'relevant_paths': {'mandatory': False, 'priority': 1.4, 'mirror_of': 'repo_scope'},
    'known_patterns': {'mandatory': False, 'priority': 1.1},
}


def _cr():
    from . import core_runtime as cr

    return cr


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if value is None:
        return 'null'
    return str(value)


def render_simple_yaml(payload: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    prefix = ' ' * indent
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f'{prefix}{key}:')
            lines.append(render_simple_yaml(value, indent + 2).rstrip())
        else:
            lines.append(f'{prefix}{key}: {yaml_scalar(value)}')
    return '\n'.join(lines) + '\n'


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in path.read_text().splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        stripped = raw_line.strip()
        if ':' not in stripped:
            continue
        key, raw_value = stripped.split(':', 1)
        key = key.strip()
        value = raw_value.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]
        if value == '':
            child: dict[str, Any] = {}
            current[key] = child
            stack.append((indent, child))
            continue
        if value in {'true', 'false'}:
            parsed: Any = value == 'true'
        else:
            try:
                parsed = int(value)
            except ValueError:
                try:
                    parsed = float(value)
                except ValueError:
                    parsed = value
        current[key] = parsed
    return root


def ensure_cost_artifacts() -> None:
    cr = _cr()
    cr.ensure_dirs()
    if not cr.COST_CONFIG_PATH.exists():
        cr.write_text(cr.COST_CONFIG_PATH, render_simple_yaml(DEFAULT_COST_CONFIG))
    if not cr.COST_RULES_PATH.exists():
        cr.write_text(
            cr.COST_RULES_PATH,
            '# cost estimation rules\n\n'
            '- Estimation heuristic: `estimated_tokens ~= ceil(characters / 4) + structural_overhead`.\n'
            '- Lists add a small overhead per entry to stay stable across runs.\n'
            '- Duplicate entries are detected by `id`, `title`, or normalized summary text and collapsed deterministically.\n'
            '- Mandatory sections are preserved first: `user_preferences`, `constraints`, `architecture_rules`.\n'
            '- Optional sections are ranked by value-per-cost using existing deterministic scores plus section priority.\n'
            '- Compression keeps `id`, `title`, and a shortened summary before omission is considered.\n'
            '- Optimization status values: `within_budget`, `optimized`, `over_budget_after_optimization`.\n',
        )
    if not cr.COST_STATUS_PATH.exists():
        cr.write_json(
            cr.COST_STATUS_PATH,
            {
                'version': 1,
                'generated_at': date.today().isoformat(),
                'optimization_events': 0,
                'over_budget_events': 0,
                'average_estimated_reduction_tokens': 0,
                'average_kept_ratio': 1.0,
                'last_status': 'not_run',
                'last_task': '',
                'last_packet_path': '',
            },
        )
    if not cr.COST_LATEST_REPORT_PATH.exists():
        cr.write_text(
            cr.COST_LATEST_REPORT_PATH,
            '# latest optimization report\n\n'
            '- Status: not_run\n'
            '- The optimizer has not processed a task packet yet.\n',
        )
    if not cr.COST_HISTORY_PATH.exists():
        cr.write_text(cr.COST_HISTORY_PATH, '')


def cost_config() -> dict[str, Any]:
    cr = _cr()
    ensure_cost_artifacts()
    payload = parse_simple_yaml(cr.COST_CONFIG_PATH)
    merged = dict(DEFAULT_COST_CONFIG)
    for key, value in payload.items():
        if key == 'max_items_per_section' and isinstance(value, dict):
            merged[key] = {**DEFAULT_COST_CONFIG[key], **value}
        else:
            merged[key] = value
    return merged


def packet_item_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        parts = []
        for key in ['id', 'key', 'title', 'summary', 'path']:
            value = item.get(key)
            if value:
                parts.append(str(value))
        if 'value' in item:
            parts.append(json.dumps(item.get('value'), ensure_ascii=False, sort_keys=True))
        return ' | '.join(parts)
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def estimate_tokens_from_text(text: str, structural_overhead: int = 0) -> int:
    compact = re.sub(r'\s+', ' ', text).strip()
    if not compact:
        return max(1, structural_overhead)
    return max(1, (len(compact) + 3) // 4 + structural_overhead)


def estimate_packet_tokens(packet: dict[str, Any]) -> dict[str, Any]:
    sections: dict[str, int] = {}
    for key, value in packet.items():
        if key in {'context_budget', 'optimization_report'}:
            continue
        if isinstance(value, list):
            section_tokens = 2
            for item in value:
                section_tokens += estimate_tokens_from_text(packet_item_text(item), structural_overhead=4)
        elif isinstance(value, dict):
            section_tokens = estimate_tokens_from_text(json.dumps(value, ensure_ascii=False, sort_keys=True), structural_overhead=6)
        else:
            section_tokens = estimate_tokens_from_text(str(value), structural_overhead=2)
        sections[key] = section_tokens
    total = sum(sections.values())
    return {'estimated_total_tokens': total, 'sections': sections}


def item_identity(item: Any) -> str:
    if isinstance(item, dict):
        for key in ['id', 'key', 'title', 'path']:
            value = item.get(key)
            if value:
                return str(value)
        if item.get('summary'):
            return slugify(str(item['summary']))
    return slugify(str(item))


def item_value(item: Any, section_name: str) -> float:
    if isinstance(item, dict):
        base = float(item.get('score', item.get('relevance_score', 0.55)) or 0.55)
        success = float(item.get('success_rate', 0.75) or 0.75)
        cost_penalty = float(item.get('context_cost', 4) or 4) / 20
    else:
        base = 0.45
        success = 0.7
        cost_penalty = 0.05
    priority = SECTION_RULES.get(section_name, {}).get('priority', 1.0)
    return round(base * 0.65 + success * 0.15 + priority * 0.2 - cost_penalty, 4)


def item_cost(item: Any) -> int:
    if isinstance(item, dict) and item.get('context_cost') is not None:
        return max(1, int(item.get('context_cost', 1)))
    return estimate_tokens_from_text(packet_item_text(item), structural_overhead=2)


def compress_item(item: Any, max_words: int) -> Any:
    if isinstance(item, str):
        return truncate_words(item, max_words)
    if not isinstance(item, dict):
        return item
    compressed = dict(item)
    if compressed.get('summary'):
        compressed['summary'] = truncate_words(str(compressed['summary']), max_words)
    if compressed.get('title'):
        compressed['title'] = truncate_words(str(compressed['title']), min(max_words, 8))
    original_cost = item_cost(item)
    compressed['context_cost'] = max(1, min(original_cost, estimate_tokens_from_text(packet_item_text(compressed), structural_overhead=1)))
    compressed['compression'] = 'summary_truncated'
    return compressed


def dedupe_items(items: list[Any]) -> tuple[list[Any], list[dict[str, Any]]]:
    seen: dict[str, Any] = {}
    dropped: list[dict[str, Any]] = []
    for item in items:
        identity = item_identity(item)
        if identity in seen:
            dropped.append({'identity': identity, 'reason': 'duplicate'})
            continue
        seen[identity] = item
    ordered = sorted(seen.values(), key=lambda item: (item_cost(item), item_identity(item)))
    return ordered, dropped


def optimize_list_section(section_name: str, items: list[Any], config: dict[str, Any], available_tokens: int) -> tuple[list[Any], list[dict[str, Any]], int]:
    if not items:
        return [], [], available_tokens
    rules = SECTION_RULES.get(section_name, {'mandatory': False, 'priority': 1.0})
    mandatory = bool(rules.get('mandatory'))
    max_items = int(config.get('max_items_per_section', {}).get(section_name, len(items)) or len(items))
    deduped, dedupe_events = dedupe_items(items)
    events: list[dict[str, Any]] = [
        {'section': section_name, 'action': 'omitted', 'entry': event['identity'], 'reason': event['reason']}
        for event in dedupe_events
    ]
    ranked = sorted(
        deduped,
        key=lambda item: (
            -((item_value(item, section_name) + (0.3 if mandatory else 0.0)) / max(item_cost(item), 1)),
            -item_value(item, section_name),
            item_cost(item),
            item_identity(item),
        ),
    )
    selected: list[Any] = []
    used = 0
    limit_words = int(config.get('mandatory_summary_max_words' if mandatory else 'summary_max_words', 20))
    for index, item in enumerate(ranked):
        if len(selected) >= max_items:
            events.append({'section': section_name, 'action': 'omitted', 'entry': item_identity(item), 'reason': 'section_item_cap'})
            continue
        current_item = item
        current_cost = item_cost(current_item)
        needs_fit = used + current_cost > available_tokens
        if needs_fit:
            compressed = compress_item(item, limit_words)
            compressed_cost = item_cost(compressed)
            if compressed_cost < current_cost and used + compressed_cost <= available_tokens:
                current_item = compressed
                current_cost = compressed_cost
                events.append({'section': section_name, 'action': 'compressed', 'entry': item_identity(item), 'reason': 'fit_budget'})
            elif not mandatory and index > 0:
                events.append({'section': section_name, 'action': 'omitted', 'entry': item_identity(item), 'reason': 'low_value_for_budget'})
                continue
            elif mandatory and compressed_cost < current_cost:
                current_item = compressed
                current_cost = compressed_cost
                events.append({'section': section_name, 'action': 'compressed', 'entry': item_identity(item), 'reason': 'mandatory_section_trim'})
        selected.append(current_item)
        used += current_cost
        if not any(event.get('entry') == item_identity(item) and event.get('action') in {'compressed', 'omitted'} for event in events):
            events.append({'section': section_name, 'action': 'preserved', 'entry': item_identity(current_item), 'reason': 'selected'})
    return selected, events, max(0, available_tokens - used)


def sync_packet_mirrors(packet: dict[str, Any]) -> None:
    packet['architecture_decisions'] = list(packet.get('architecture_rules', []))
    packet['relevant_paths'] = list(packet.get('repo_scope', []))


def update_cost_status(report: dict[str, Any], packet_path: Path) -> None:
    cr = _cr()
    status = cr.read_json(cr.COST_STATUS_PATH, {})
    events = int(status.get('optimization_events', 0))
    new_events = events + 1
    reduction = int(report.get('estimated_tokens_before', 0)) - int(report.get('estimated_tokens_after', 0))
    kept = int(report.get('kept_entries', 0))
    total = max(int(report.get('candidate_entries', 0)), 1)
    previous_avg_reduction = float(status.get('average_estimated_reduction_tokens', 0) or 0)
    previous_avg_kept = float(status.get('average_kept_ratio', 1.0) or 1.0)
    updated = {
        'version': 1,
        'generated_at': date.today().isoformat(),
        'optimization_events': new_events,
        'over_budget_events': int(status.get('over_budget_events', 0)) + (1 if report.get('status') != 'within_budget' else 0),
        'average_estimated_reduction_tokens': round(((previous_avg_reduction * events) + reduction) / new_events, 2),
        'average_kept_ratio': round(((previous_avg_kept * events) + (kept / total)) / new_events, 4),
        'last_status': report.get('status'),
        'last_task': report.get('task'),
        'last_packet_path': packet_path.as_posix(),
        'last_budget': report.get('budget'),
        'last_estimated_tokens_before': report.get('estimated_tokens_before'),
        'last_estimated_tokens_after': report.get('estimated_tokens_after'),
    }
    cr.write_json(cr.COST_STATUS_PATH, updated)
    history_row = {
        'generated_at': date.today().isoformat(),
        'task': report.get('task'),
        'status': report.get('status'),
        'estimated_tokens_before': report.get('estimated_tokens_before'),
        'estimated_tokens_after': report.get('estimated_tokens_after'),
        'kept_entries': kept,
        'candidate_entries': total,
    }
    history = cr.read_jsonl(cr.COST_HISTORY_PATH)
    history.append(history_row)
    cr.write_jsonl(cr.COST_HISTORY_PATH, history[-50:])


def render_optimization_report(report: dict[str, Any]) -> str:
    lines = [
        '# latest optimization report',
        '',
        f"- Task: {report.get('task', '')}",
        f"- Status: {report.get('status', 'unknown')}",
        f"- Budget: target {report['budget']['budget_target_tokens']} / soft {report['budget']['soft_limit_tokens']} / hard {report['budget']['hard_limit_tokens']}",
        f"- Estimated tokens: {report.get('estimated_tokens_before', 0)} -> {report.get('estimated_tokens_after', 0)}",
        f"- Candidate entries: {report.get('candidate_entries', 0)}",
        f"- Kept entries: {report.get('kept_entries', 0)}",
        '',
        '## Actions',
        '',
    ]
    actions = report.get('actions', [])
    if not actions:
        lines.append('- No optimization actions were required.')
    else:
        for action in actions:
            lines.append(f"- `{action['section']}` | {action['action']} | `{action['entry']}` | {action['reason']}")
    lines.extend(['', '## Rationale', '', f"- {report.get('rationale', 'No rationale captured.')}"])
    return '\n'.join(lines) + '\n'


def optimize_packet(packet: dict[str, Any]) -> dict[str, Any]:
    cr = _cr()
    ensure_cost_artifacts()
    config = cost_config()
    before = estimate_packet_tokens(packet)
    optimized = dict(packet)
    actions: list[dict[str, Any]] = []
    candidate_entries = 0
    kept_entries = 0
    available_tokens = int(config.get('budget_target_tokens', 3000))
    for fixed_key in ['task', 'task_id', 'task_summary', 'task_type', 'project', 'model_suggestion', 'fallback_mode', 'knowledge_retrieval', 'telemetry_granularity']:
        available_tokens = max(0, available_tokens - before['sections'].get(fixed_key, 0))
    for section_name in [
        'user_preferences', 'constraints', 'architecture_rules', 'relevant_memory', 'relevant_patterns', 'validation_recipes',
        'relevant_failures', 'relevant_graph_context', 'knowledge_artifacts', 'repo_scope', 'known_patterns',
    ]:
        items = list(optimized.get(section_name, []))
        candidate_entries += len(items)
        selected, section_actions, available_tokens = optimize_list_section(section_name, items, config, available_tokens)
        optimized[section_name] = selected
        actions.extend(section_actions)
        kept_entries += len(selected)
    sync_packet_mirrors(optimized)
    if before['estimated_total_tokens'] <= int(config.get('soft_limit_tokens', 2600)):
        status = 'within_budget'
        rationale = 'Estimated packet cost stayed below the soft limit, so only deterministic deduplication and per-section caps were applied.'
    else:
        after_estimate = estimate_packet_tokens(optimized)
        status = 'optimized' if after_estimate['estimated_total_tokens'] <= int(config.get('hard_limit_tokens', 3200)) else 'over_budget_after_optimization'
        rationale = 'The optimizer preserved mandatory sections first, then ranked optional entries by value-per-cost, compressing verbose summaries before omitting low-value items.'
    after = estimate_packet_tokens(optimized)
    budget = {
        'budget_target_tokens': int(config.get('budget_target_tokens', 3000)),
        'soft_limit_tokens': int(config.get('soft_limit_tokens', 2600)),
        'hard_limit_tokens': int(config.get('hard_limit_tokens', 3200)),
        'estimated_tokens_before': before['estimated_total_tokens'],
        'estimated_tokens_after': after['estimated_total_tokens'],
        'status': status,
    }
    report = {
        'task': packet.get('task', ''),
        'status': status,
        'budget': budget,
        'estimated_tokens_before': before['estimated_total_tokens'],
        'estimated_tokens_after': after['estimated_total_tokens'],
        'candidate_entries': candidate_entries,
        'kept_entries': kept_entries,
        'actions': actions,
        'rationale': rationale,
    }
    optimized['context_budget'] = budget
    optimized['optimization_report'] = {
        'status': status,
        'actions_count': len(actions),
        'kept_entries': kept_entries,
        'candidate_entries': candidate_entries,
        'report_path': cr.COST_LATEST_REPORT_PATH.as_posix(),
    }
    return {'packet': optimized, 'report': report}
