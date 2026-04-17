from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from .runtime_io import clamp, days_since, iso_date_or_today, read_jsonl, slugify, write_jsonl


def preference_records() -> list[dict[str, Any]]:
    from . import core_runtime as cr

    prefs = cr.read_json(cr.ROOT_PREFS_PATH, {})
    updated_at = prefs.get('updated_at', date.today().isoformat())
    rows = []

    def walk(node: Any, prefix: str = '') -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == 'history':
                    continue
                next_prefix = f'{prefix}.{key}' if prefix else key
                walk(value, next_prefix)
            return
        rows.append(
            {
                'id': f'pref.{slugify(prefix)}',
                'type': 'user_preference',
                'scope': 'global',
                'project': None,
                'tags': [part for part in prefix.split('.') if part],
                'key': prefix,
                'value': node,
                'priority': 'high',
                'confidence': 'high',
                'last_verified': updated_at,
                'source': 'user_preferences.json',
                'override_rule': 'explicit_user_instruction_wins',
                'relevance_score': 0.95,
                'last_used_at': updated_at,
                'times_used': 0,
                'success_rate': 1.0,
                'context_cost': 1,
                'source_type': 'preference',
                'staleness_score': 0.05,
            }
        )

    walk(prefs)
    return rows


def load_records() -> list[dict[str, Any]]:
    from . import core_runtime as cr

    rows = read_jsonl(cr.STORE_GLOBAL_RECORDS_PATH)
    rows.extend(read_jsonl(cr.STORE_USER_PREFERENCES_PATH))
    if cr.PROJECT_RECORDS_DIR.exists():
        for path in sorted(cr.PROJECT_RECORDS_DIR.glob('*.jsonl')):
            rows.extend(read_jsonl(path))
    return rows


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    from . import core_runtime as cr

    normalized = dict(record)
    normalized['relevance_score'] = float(record.get('relevance_score', 0.6))
    normalized['last_used_at'] = iso_date_or_today(record.get('last_used_at') or record.get('last_verified'))
    normalized['times_used'] = int(record.get('times_used', 0))
    normalized['success_rate'] = float(record.get('success_rate', 0.75))
    normalized['context_cost'] = int(record.get('context_cost', max(1, min(12, len(str(record.get('summary', '')).split()) // 8 or 1))))
    normalized['source_type'] = str(record.get('source_type', 'record'))
    normalized['staleness_score'] = float(record.get('staleness_score', 0.2))
    normalized['task_type'] = cr.normalize_task_type(record.get('task_type'))
    normalized['files_involved'] = list(record.get('files_involved', [record.get('path')] if record.get('path') else []))
    return normalized


def rank_records(
    query: str,
    record_type: str | None = None,
    task_type: str | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    from . import core_runtime as cr

    rows = [normalize_record(row) for row in load_records()] + cr.manual_task_memory_records()
    ranked = []
    for row in rows:
        if record_type and row.get('type') != record_type:
            continue
        if task_type and cr.normalize_task_type(row.get('task_type')) != cr.normalize_task_type(task_type):
            continue
        if project and row.get('project') not in {None, project}:
            continue
        score = cr.deterministic_score(query, row)
        if score > 0:
            ranked.append((score, row))
    ranked.sort(key=lambda item: (-item[0], item[1].get('context_cost', 99), item[1].get('id', '')))
    return [{'score': score, **row} for score, row in ranked[:12]]


def summarize_query(query: str, mode: str = 'all') -> dict[str, Any]:
    from . import core_runtime as cr

    if mode == 'prefs':
        return {'query': query, 'preferences': rank_records(query or 'workflow', 'user_preference')}
    if mode == 'architecture':
        return {'query': query, 'matches': rank_records(query, 'architecture_decision')}
    if mode == 'symptom':
        symptom_map = cr.read_json(cr.INDEX_BY_SYMPTOM_PATH, {})
        ranked = []
        for symptom, paths in symptom_map.items():
            score = cr.score_match(query, symptom)
            if score > 0:
                ranked.append({'symptom': symptom, 'score': score, 'paths': paths})
        ranked.sort(key=lambda item: (-item['score'], item['symptom']))
        return {'query': query, 'symptoms': ranked[:12]}
    return {'query': query, 'matches': rank_records(query)}


def rebuild_memory_store() -> dict[str, Any]:
    from . import core_runtime as cr

    cr.ensure_dirs()
    cr.ensure_cost_artifacts()
    cr.ensure_task_memory_artifacts()
    cr.ensure_failure_memory_artifacts()
    cr.ensure_memory_graph_artifacts()
    note_infos = [cr.classify_note(path) for path in cr.note_paths()]
    project_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    global_rows: list[dict[str, Any]] = []
    import_map: list[dict[str, str]] = []

    for note in note_infos:
        record = cr.note_to_record(note)
        import_map.append({'source': note.rel_path, 'target_record_id': record['id']})
        if note.project:
            project_rows[note.project].append(record)
        else:
            global_rows.append(record)

    write_jsonl(cr.STORE_GLOBAL_RECORDS_PATH, global_rows)
    for project, rows in project_rows.items():
        write_jsonl(cr.PROJECT_RECORDS_DIR / f'{project}.jsonl', rows)

    user_rows = preference_records()
    write_jsonl(cr.STORE_USER_PREFERENCES_PATH, user_rows)

    index = cr.read_json(cr.ROOT_INDEX_PATH, {})
    project_registry = {
        'version': 1,
        'lookup_order': index.get('lookup_order', []),
        'projects': index.get('projects', {}),
        'generated_at': date.today().isoformat(),
    }
    cr.write_json(cr.BOOT_PROJECTS_PATH, project_registry)

    defaults_payload = cr.read_json(cr.ROOT_PREFS_PATH, {})
    normalized_defaults = {
        'version': 1,
        'updated_at': defaults_payload.get('updated_at', date.today().isoformat()),
        'preferred_language': defaults_payload.get('profile', {}).get('preferred_language', 'es'),
        'response': defaults_payload.get('response', {}),
        'interaction': defaults_payload.get('interaction', {}),
        'communication': cr.communication_policy_from_defaults(defaults_payload),
        'coding': defaults_payload.get('coding', {}),
        'workflow': defaults_payload.get('workflow', {}),
        'quality_gates': defaults_payload.get('quality_gates', {}),
    }
    cr.write_json(cr.BOOT_DEFAULTS_PATH, normalized_defaults)

    model_routing = cr.default_model_routing()
    cr.write_json(cr.BOOT_MODEL_ROUTING_PATH, model_routing)
    communication_policy = cr.communication_policy_from_defaults(defaults_payload)
    adapter_contract = cr.default_adapter_contract()
    boot_summary_payload = {
        'version': 1,
        'engine_name': 'ai_context_engine',
        **adapter_contract,
        'default_behavior': {
            'memory_first': True,
            'fallback_to_standard_repo_analysis': True,
            'explicit_user_override_wins': True,
            'bootstrap_required_every_session': True,
        },
        'preferred_output_patterns': [
            communication_policy.get('mode', 'caveman_full'),
            communication_policy.get('final_style', 'plain_direct_final_only'),
            defaults_payload.get('response', {}).get('verbosity', defaults_payload.get('workflow', {}).get('default_response_style', 'concise')),
            defaults_payload.get('profile', {}).get('preferred_language', 'es'),
        ],
        'communication_policy': communication_policy,
        'communication_contract': {
            'default_mode': communication_policy.get('mode', 'caveman_full'),
            'layer': communication_policy.get('layer', 'enabled'),
            'intermediate_output': communication_policy.get('intermediate_updates', 'suppressed'),
            'final_output': communication_policy.get('final_style', 'plain_direct_final_only'),
            'plain_direct': True,
            'single_final_answer_default': True,
            'explicit_user_override_wins': True,
        },
        'preference_precedence': [
            'explicit_user_instruction',
            'persisted_user_preferences',
            'assistant_default',
        ],
        'active_projects': sorted(project_rows.keys()),
        'model_routing_profile': model_routing.get('profile', 'default'),
        'provider_capabilities': list(adapter_contract['provider_capabilities']),
        'last_maintenance': date.today().isoformat(),
    }
    cr.write_json(cr.BOOT_SUMMARY_PATH, boot_summary_payload)

    all_rows = [normalize_record(row) for row in (global_rows + user_rows + [row for rows in project_rows.values() for row in rows])]
    write_jsonl(cr.STORE_GLOBAL_RECORDS_PATH, [normalize_record(row) for row in global_rows])
    for project, rows in project_rows.items():
        write_jsonl(cr.PROJECT_RECORDS_DIR / f'{project}.jsonl', [normalize_record(row) for row in rows])
    write_jsonl(cr.STORE_USER_PREFERENCES_PATH, [normalize_record(row) for row in user_rows])
    normalized_all_rows = [normalize_record(row) for row in all_rows]
    cr.write_indexes(normalized_all_rows)
    task_memory_counts = cr.build_task_memory_artifacts(normalized_all_rows)
    failure_memory_status = cr.build_failure_memory_artifacts(normalized_all_rows)
    memory_graph_status = cr.build_memory_graph_artifacts(normalized_all_rows)
    cr.ensure_context_metrics_artifacts()
    cr.ensure_library_artifacts()
    cr.write_json(
        cr.DELTA_SCHEMA_PATH,
        {
            'version': 7,
            'required': [
                'task_summary', 'task_id', 'task_type', 'task_type_resolution', 'repo_scope', 'user_preferences', 'constraints',
                'architecture_rules', 'relevant_memory', 'known_patterns', 'fallback_mode', 'task_memory', 'failure_memory',
                'memory_graph', 'telemetry_granularity', 'knowledge_retrieval', 'context_budget', 'optimization_report',
            ],
            'compatibility_fields': [
                'project', 'architecture_decisions', 'relevant_paths', 'relevant_patterns', 'validation_recipes', 'model_suggestion',
                'relevant_failures', 'relevant_graph_context', 'knowledge_artifacts',
            ],
        },
    )
    append_if_missing(
        cr.LOGS_MAINTENANCE_PATH,
        f"- {date.today().isoformat()} | rebuilt store/indexes/boot artifacts from current ai_context_engine notes and preferences.\n",
    )
    cr.write_json(
        cr.ROOT_COMPACTION_REPORT_PATH,
        {
            'generated_at': date.today().isoformat(),
            'dry_run': True,
            'stores_scanned': 2 + len(project_rows),
            'duplicates_detected': 0,
            'near_duplicates_detected': 0,
            'stale_records_detected': 0,
            'verbose_records_detected': 0,
            'fragmented_groups_detected': 0,
            'actions': [],
        },
    )
    cr.write_json(
        cr.COST_STATUS_PATH,
        {
            **cr.read_json(cr.COST_STATUS_PATH, {}),
            'version': 1,
            'generated_at': date.today().isoformat(),
        },
    )
    engine_state = cr.refresh_engine_state()
    return {
        'notes_scanned': len(note_infos),
        'global_records': len(global_rows),
        'project_records': {project: len(rows) for project, rows in project_rows.items()},
        'user_preferences': len(user_rows),
        'task_memory': task_memory_counts,
        'failure_memory': failure_memory_status,
        'memory_graph': memory_graph_status,
        'boot_summary_path': cr.BOOT_SUMMARY_PATH.as_posix(),
        'engine_state': engine_state,
    }
