from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any


def _cr():
    from . import core_runtime as cr
    return cr


def compat_artifacts_manifest() -> dict[str, str]:
    return {
        'derived_boot_summary': 'derived_boot_summary.json',
        'user_preferences': 'user_preferences.json',
        'project_bootstrap': 'project_bootstrap.json',
    }


def ensure_repo_compat_readme(compat_dir: Path) -> None:
    readme = compat_dir / 'README.md'
    if not readme.exists():
        readme.write_text(
            '# .ai_context_engine/memory\n\n'
            'Generated compatibility bootstrap layer for repo-local agent startup.\n\n'
            '- Canonical runtime state lives under sibling subsystem directories.\n'
            '- This directory is intentionally minimal and bootstrap-focused.\n',
            encoding='utf-8',
        )


def sync_repo_compat_layers(*, project_rows: dict[str, list[dict[str, Any]]], global_rows: list[dict[str, Any]], defaults_payload: dict[str, Any], project_registry: dict[str, Any], boot_summary_payload: dict[str, Any], model_routing: dict[str, Any]) -> list[str]:
    cr = _cr()
    synced = []
    project_map = project_registry.get('projects', {})
    adapter_contract = cr.default_adapter_contract()
    for project, rows in project_rows.items():
        repo_root = cr.repo_root_for_project(project)
        if not repo_root:
            continue
        compat_dir = repo_root / cr.REPO_COMPAT_DIRNAME
        compat_dir.mkdir(parents=True, exist_ok=True)
        ensure_repo_compat_readme(compat_dir)
        project_info = project_map.get(project, {})
        project_bootstrap = {
            'version': 1,
            'generated_at': date.today().isoformat(),
            'project': project,
            'repo_root': repo_root.as_posix(),
            'engine_name': 'ai_context_engine',
            **adapter_contract,
            'summary': project_info.get('summary', ''),
            'lookup_order': project_registry.get('lookup_order', []),
            'subprojects': project_info.get('subprojects', {}),
            'canonical_memory_root': cr.BASE.as_posix(),
            'external_index': cr.ROOT_INDEX_PATH.as_posix(),
            'external_preferences': cr.ROOT_PREFS_PATH.as_posix(),
        }
        derived_boot_summary = {
            'version': 1,
            'generated_at': date.today().isoformat(),
            'project': project,
            'repo_root': repo_root.as_posix(),
            'engine_name': boot_summary_payload.get('engine_name', 'ai_context_engine'),
            'agent_adapter': boot_summary_payload.get('agent_adapter', cr.DEFAULT_AGENT_ADAPTER),
            'adapter_id': boot_summary_payload.get('adapter_id', cr.DEFAULT_ADAPTER_ID),
            'adapter_family': boot_summary_payload.get('adapter_family', cr.DEFAULT_ADAPTER_FAMILY),
            'provider_capabilities': boot_summary_payload.get('provider_capabilities', list(cr.DEFAULT_PROVIDER_CAPABILITIES)),
            'canonical_memory_root': cr.BASE.as_posix(),
            'bootstrap_required': True,
            'bootstrap_sequence': [
                f'load {cr.REPO_COMPAT_DIRNAME}/derived_boot_summary.json',
                f'load {cr.REPO_COMPAT_DIRNAME}/user_preferences.json',
                f'load {cr.REPO_COMPAT_DIRNAME}/project_bootstrap.json',
                'load smallest relevant project note from canonical ai_context_engine',
                'apply preferences as runtime defaults',
            ],
            'fallback_order': [cr.REPO_COMPAT_DIRNAME, 'ai_context_engine', 'normal_repo_analysis'],
            'preference_precedence': boot_summary_payload.get('preference_precedence', []),
            'default_behavior': boot_summary_payload.get('default_behavior', {}),
            'preferred_output_patterns': boot_summary_payload.get('preferred_output_patterns', []),
            'communication_policy': boot_summary_payload.get('communication_policy', {}),
            'communication_contract': boot_summary_payload.get('communication_contract', {}),
            'model_routing_profile': model_routing.get('profile', 'default'),
            'active_subprojects': sorted(project_info.get('subprojects', {}).keys()),
        }
        manifest = {
            'version': 2,
            'generated_at': date.today().isoformat(),
            'mode': 'bootstrap_compat_minimal',
            'canonical_runtime_roots': {
                'cost': '.ai_context_engine/cost',
                'task_memory': '.ai_context_engine/task_memory',
                'failure_memory': '.ai_context_engine/failure_memory',
                'memory_graph': '.ai_context_engine/memory_graph',
                'metrics': '.ai_context_engine/metrics',
            },
            'artifacts': compat_artifacts_manifest(),
        }
        cr.write_json(compat_dir / 'manifest.json', manifest)
        cr.write_json(compat_dir / 'derived_boot_summary.json', derived_boot_summary)
        cr.write_json(compat_dir / 'project_bootstrap.json', project_bootstrap)
        cr.write_json(compat_dir / 'user_preferences.json', defaults_payload)
        synced.append(repo_root.as_posix())
    return synced


def sync_repo_cost_status(project: str | None) -> None:
    return None


def sync_repo_task_memory_status(project: str | None) -> None:
    return None


def sync_repo_failure_memory_status(project: str | None) -> None:
    return None


def sync_repo_memory_graph_status(project: str | None) -> None:
    return None


def find_legacy_memory_dirs() -> list[str]:
    return []


def write_migration_report(import_map: list[dict[str, str]]) -> None:
    return None
