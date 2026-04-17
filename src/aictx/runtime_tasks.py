from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from .runtime_io import days_since, slugify


def apply_packet_compat_fields(packet: dict[str, Any]) -> dict[str, Any]:
    compatible = dict(packet)
    compatible['architecture_decisions'] = list(compatible.get('architecture_rules', []))
    compatible['relevant_paths'] = list(compatible.get('repo_scope', []))
    return compatible


def route_task(task: str) -> dict[str, Any]:
    task_l = task.lower()
    files_hint = 1
    if any(word in task_l for word in ['cross-system', 'migration', 'architecture', 'redesign', 'protocol']):
        level = 'heavy'
        files_hint = 10
    elif any(word in task_l for word in ['add', 'implement', 'fix', 'debug', 'test', 'refactor']):
        level = 'medium'
        files_hint = 4
    else:
        level = 'light'
        files_hint = 1
    return {
        'task': task,
        'model_suggestion': level,
        'signals': {
            'estimated_files': files_hint,
            'ambiguity': 'medium' if level != 'light' else 'low',
            'cross_system': level == 'heavy',
        },
    }


def resolve_task_type(
    task: str,
    *,
    explicit_task_type: str | None = None,
    packet_metadata: dict[str, Any] | None = None,
    touched_files: list[str] | None = None,
) -> dict[str, Any]:
    from . import core_runtime as cr

    task_signals = cr.infer_task_signals(task, touched_files=touched_files)
    normalized_explicit = cr.normalize_task_type(explicit_task_type)
    if explicit_task_type and normalized_explicit in cr.TASK_TYPES:
        return {
            'task_type': normalized_explicit,
            'source': 'explicit_task_type',
            'fallback': normalized_explicit == 'unknown',
            'confidence': 0.95,
            'signals': [f'explicit:{normalized_explicit}'],
        }
    metadata_task_type = cr.normalize_task_type((packet_metadata or {}).get('task_type'))
    if packet_metadata and packet_metadata.get('task_type') and metadata_task_type in cr.TASK_TYPES:
        return {
            'task_type': metadata_task_type,
            'source': 'packet_metadata',
            'fallback': metadata_task_type == 'unknown',
            'confidence': 0.9,
            'signals': [f'metadata:{metadata_task_type}'],
        }
    inferred = cr.classify_task_type_from_text('\n'.join([task, ' '.join(touched_files or [])]), tags=[], record_type=None)
    if inferred != 'unknown':
        return {
            'task_type': inferred,
            'source': 'heuristic_inference',
            'fallback': False,
            'confidence': cr.task_type_confidence(task, inferred, touched_files=touched_files),
            'signals': task_signals,
        }
    return {
        'task_type': 'unknown',
        'source': 'unknown_fallback',
        'fallback': True,
        'confidence': 0.35,
        'signals': task_signals,
    }


def packet_for_task(task: str, project: str | None = None, task_type: str | None = None) -> dict[str, Any]:
    from . import core_runtime as cr
    from .runtime_knowledge import retrieve_knowledge
    from .runtime_memory import load_records, normalize_record, rank_records, summarize_query
    from .runtime_task_memory import category_summary_path

    cr.ensure_cost_artifacts()
    cr.ensure_task_memory_artifacts()
    cr.ensure_failure_memory_artifacts()
    cr.ensure_memory_graph_artifacts()
    cr.ensure_context_metrics_artifacts()
    cr.ensure_library_artifacts()
    cr.refresh_engine_state()
    initial_matches = rank_records(task)
    project_name = cr.infer_project_name(task, initial_matches, explicit_project=project)
    touched_files = [str(row.get('path')) for row in initial_matches[:6] if row.get('path')]
    resolved_task = resolve_task_type(task, explicit_task_type=task_type, touched_files=touched_files)
    task_specific_matches = []
    queried_task_categories = [resolved_task['task_type']]
    if resolved_task['task_type'] != 'unknown':
        task_specific_matches = [
            row for row in rank_records(task, task_type=resolved_task['task_type'], project=project_name)
            if row.get('type') != 'user_preference'
        ]
    fallback_task_matches = [
        row for row in rank_records(task, task_type='unknown', project=project_name)
        if row.get('type') != 'user_preference'
    ]
    if 'unknown' not in queried_task_categories:
        queried_task_categories.append('unknown')
    general_matches = [
        row for row in rank_records(task, project=project_name)
        if row.get('type') != 'user_preference'
    ]
    merged_memory: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for row in task_specific_matches + fallback_task_matches + general_matches:
        row_id = str(row.get('id', ''))
        if row_id in seen_ids:
            continue
        seen_ids.add(row_id)
        merged_memory.append(row)
    memory_matches = merged_memory
    if not memory_matches and project_name:
        memory_matches = [
            row for row in rank_records(project_name, task_type=resolved_task['task_type'], project=project_name)
            if row.get('type') != 'user_preference' and row.get('project') == project_name
        ]
    if not memory_matches:
        memory_matches = [row for row in initial_matches if row.get('type') != 'user_preference']
    prefs = summarize_query(task, mode='prefs').get('preferences', [])[:5]
    architecture = [row for row in memory_matches if row.get('type') == 'architecture_decision'][:5]
    constraints = [row for row in memory_matches if row.get('type') == 'constraint'][:5]
    patterns = [row for row in memory_matches if row.get('type') in {'debugging_pattern', 'failure_mode', 'task_pattern'}][:5]
    validation = [row for row in memory_matches if row.get('type') == 'validation_recipe'][:5]
    relevant_paths = []
    for row in memory_matches[:8]:
        path = row.get('path')
        if path and path not in relevant_paths:
            relevant_paths.append(path)
    route = route_task(task)
    relevant_failures = cr.rank_failure_records(task) if cr.should_consult_failure_memory(task, resolved_task['task_type']) else []
    knowledge_pack = retrieve_knowledge(task)
    graph_seed_ids = [cr.graph_node_id('task_type', resolved_task['task_type'])]
    graph_seed_ids.extend(cr.graph_node_id(cr.graph_node_type_for_record(row), str(row.get('id', ''))) for row in memory_matches[:4] if row.get('id'))
    graph_seed_ids.extend(cr.graph_node_id('failure_pattern', str(row.get('id', ''))) for row in relevant_failures[:2] if row.get('id'))
    if project_name:
        graph_seed_ids.append(cr.graph_node_id('repository_area', project_name))
    expansion_depth = 2 if resolved_task['task_type'] in {'architecture', 'bug_fixing'} and (memory_matches or relevant_failures) else 1
    graph_expansion = cr.graph_expand(
        sorted(set(graph_seed_ids)),
        depth=expansion_depth,
        node_budget=10,
        edge_budget=14,
        task_type=resolved_task['task_type'],
        repository_area=project_name,
    )
    graph_connected_ids = set(graph_expansion.get('connected_record_ids', []))
    graph_context = []
    for node in graph_expansion.get('nodes', []):
        if node.get('type') == 'task_type':
            continue
        graph_context.append({'id': node.get('id'), 'title': node.get('label'), 'summary': f"{node.get('type')} from {node.get('source')}", 'score': round(float(node.get('confidence', 0.5)), 2), 'context_cost': 2, 'source_type': 'memory_graph'})
    if graph_connected_ids:
        connected_rows = {row.get('id'): row for row in ([normalize_record(row) for row in load_records()] + cr.manual_task_memory_records()) if row.get('id') in graph_connected_ids}
        for record_id in sorted(graph_connected_ids):
            row = connected_rows.get(record_id)
            if not row or any(existing.get('id') == record_id for existing in memory_matches):
                continue
            memory_matches.append({**row, 'score': round(float(row.get('relevance_score', 0.65)) * 0.9, 4)})
    relevant_memory = []
    known_patterns = []
    for row in memory_matches[:5]:
        relevant_memory.append({'id': row.get('id'), 'title': row.get('title'), 'summary': row.get('summary'), 'score': row.get('score'), 'source_type': row.get('source_type', 'legacy'), 'context_cost': row.get('context_cost', 5)})
        for tag in row.get('tags', []):
            if tag not in known_patterns:
                known_patterns.append(tag)
    task_id = f"{date.today().isoformat()}_{slugify(task)[:40]}"
    packet = {
        'task_id': task_id,
        'task': task,
        'task_summary': task,
        'task_type': resolved_task['task_type'],
        'task_type_resolution': resolved_task,
        'project': project_name,
        'repo_scope': relevant_paths,
        'user_preferences': prefs,
        'constraints': constraints,
        'architecture_rules': architecture,
        'relevant_memory': relevant_memory,
        'known_patterns': known_patterns,
        'relevant_patterns': patterns,
        'validation_recipes': validation,
        'relevant_failures': relevant_failures,
        'relevant_graph_context': graph_context[:5],
        'knowledge_artifacts': knowledge_pack.get('artifacts', []),
        'knowledge_retrieval': knowledge_pack,
        'model_suggestion': route['model_suggestion'],
        'fallback_mode': 'normal_repo_analysis',
        'task_memory': {
            'resolved_task_type': resolved_task['task_type'], 'task_type_source': resolved_task['source'], 'task_type_confidence': resolved_task.get('confidence', 0.35), 'task_type_signals': resolved_task.get('signals', []),
            'task_specific_memory_used': bool(task_specific_matches), 'task_specific_records_retrieved': len(task_specific_matches[:5]), 'unknown_records_retrieved': len(fallback_task_matches[:5]), 'general_records_retrieved': len(general_matches[:5]), 'queried_categories': queried_task_categories,
            'category_summary_paths': [category_summary_path(category).as_posix() for category in queried_task_categories if category_summary_path(category).exists()],
            'fallback_to_general': resolved_task['task_type'] == 'unknown' or not task_specific_matches, 'task_memory_written': False, 'learning_channel': 'scripts/task_memory.py',
        },
        'failure_memory': {'failure_memory_used': bool(relevant_failures), 'records_retrieved': len(relevant_failures), 'index_path': cr.FAILURE_MEMORY_INDEX_PATH.as_posix(), 'summary_path': cr.FAILURE_MEMORY_SUMMARY_PATH.as_posix()},
        'memory_graph': {'graph_used': bool(graph_context), 'seed_count': len(sorted(set(graph_seed_ids))), 'expansion_depth_used': graph_expansion.get('depth_used', 0), 'graph_hits': len(graph_expansion.get('nodes', [])), 'connected_record_hits': len(graph_connected_ids), 'nodes_total': int(cr.read_json(cr.MEMORY_GRAPH_STATUS_PATH, {}).get('nodes_total', 0) or 0), 'edges_total': int(cr.read_json(cr.MEMORY_GRAPH_STATUS_PATH, {}).get('edges_total', 0) or 0), 'status_path': cr.MEMORY_GRAPH_STATUS_PATH.as_posix(), 'snapshot_path': cr.MEMORY_GRAPH_SNAPSHOT_PATH.as_posix()},
        'telemetry_granularity': {
            'supported': True, 'task_id': task_id, 'level': 'task', 'phase_count': 4,
            'phases': [
                {'phase_name': 'memory_retrieval', 'estimated_tokens': cr.estimate_tokens(relevant_memory) + cr.estimate_tokens(knowledge_pack.get('artifacts', [])), 'notes': 'memory, failures, graph seeds, and knowledge artifacts'},
                {'phase_name': 'graph_expansion', 'estimated_tokens': cr.estimate_tokens(graph_context), 'notes': 'bounded memory-graph expansion'},
                {'phase_name': 'packet_optimization', 'estimated_tokens': cr.estimate_tokens({'constraints': constraints, 'architecture': architecture, 'patterns': patterns}), 'notes': 'budget-aware packet optimization'},
                {'phase_name': 'packet_persistence', 'estimated_tokens': cr.estimate_tokens({'packet': task_id, 'writes': 5}), 'notes': 'packet and status persistence'},
            ],
        },
    }
    optimized = cr.optimize_packet(packet)
    final_packet = apply_packet_compat_fields(optimized['packet'])
    packet_name = f"{date.today().isoformat()}_{slugify(task)[:60]}.json"
    packet_path = cr.LAST_PACKETS_DIR / packet_name
    cr.write_json(packet_path, final_packet)
    cr.write_text(cr.COST_LATEST_REPORT_PATH, cr.render_optimization_report(optimized['report']))
    cr.update_cost_status(optimized['report'], packet_path)
    cr.update_task_memory_status(final_packet, packet_path)
    cr.update_failure_memory_status(final_packet, packet_path)
    cr.update_memory_graph_status(final_packet, packet_path)
    weekly_summary = cr.record_granular_telemetry(final_packet, packet_path, optimized['report'])
    final_packet.setdefault('telemetry_granularity', {})
    final_packet['telemetry_granularity']['weekly_summary_path'] = cr.CONTEXT_WEEKLY_SUMMARY_PATH.as_posix()
    final_packet['telemetry_granularity']['phase_events_sampled'] = int(weekly_summary.get('phase_events_sampled', 0) or 0)
    return final_packet


def detect_stale_records() -> dict[str, Any]:
    from . import core_runtime as cr
    from .runtime_memory import load_records, normalize_record

    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicate_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    missing_paths = []
    today = date.today().isoformat()
    for row in rows:
        verified = str(row.get('last_verified', ''))
        if verified and verified < '2026-01-01':
            stale.append({'id': row['id'], 'last_verified': verified})
        duplicate_groups[(str(row.get('type')), str(row.get('title', row.get('key', ''))))].append(row['id'])
        rel_path = row.get('path')
        if rel_path and not (cr.BASE / rel_path).exists():
            missing_paths.append({'id': row['id'], 'path': rel_path})
    duplicates = [{'type': group[0], 'title': group[1], 'record_ids': ids} for group, ids in duplicate_groups.items() if len(ids) > 1]
    report = {'generated_at': today, 'stale': stale, 'duplicates': duplicates, 'missing_paths': missing_paths}
    cr.write_json(cr.BASE / 'staleness_report.json', report)
    return report


def compact_records(apply: bool = False) -> dict[str, Any]:
    from . import core_runtime as cr
    from .runtime_memory import load_records, normalize_record

    rows = [normalize_record(row) for row in load_records()]
    stale = []
    duplicates = []
    verbose = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get('type') == 'user_preference':
            signature = f"pref:{row.get('key', row.get('id', ''))}"
        elif row.get('path'):
            signature = f"path:{row.get('path')}"
        elif row.get('title') or row.get('summary'):
            signature_text = f"{row.get('title', '')} {row.get('summary', '')}"
            signature = f"text:{slugify(signature_text)}"
        else:
            signature = f"id:{row.get('id', '')}"
        key = (str(row.get('type', '')), signature)
        grouped[key].append(row)
        if len(str(row.get('summary', ''))) > 320:
            verbose.append(row['id'])
        if days_since(row.get('last_used_at')) > 180 and float(row.get('relevance_score', 0.6)) < 0.5:
            stale.append(row['id'])
    for key, group in grouped.items():
        if len(group) > 1:
            duplicates.append({'type': key[0], 'signature': key[1], 'record_ids': [row['id'] for row in group], 'kept_id': sorted(group, key=lambda row: (-float(row.get('success_rate', 0.75)), row['context_cost'], row['id']))[0]['id']})
    report = {
        'generated_at': date.today().isoformat(), 'dry_run': not apply, 'stores_scanned': len(list(cr.PROJECT_RECORDS_DIR.glob('*.jsonl'))) + 2,
        'duplicates_detected': len(duplicates), 'near_duplicates_detected': 0, 'stale_records_detected': len(stale), 'verbose_records_detected': len(verbose), 'fragmented_groups_detected': 0,
        'actions': [
            *[{'type': 'duplicate', 'record_ids': item['record_ids'], 'kept_id': item['kept_id'], 'recommendation': 'merge_or_prune'} for item in duplicates],
            *[{'type': 'stale_low_value', 'record_id': record_id, 'recommendation': 'review'} for record_id in stale],
            *[{'type': 'verbose', 'record_id': record_id, 'recommendation': 'tighten_summary'} for record_id in verbose],
        ],
    }
    cr.write_json(cr.ROOT_COMPACTION_REPORT_PATH, report)
    return report
