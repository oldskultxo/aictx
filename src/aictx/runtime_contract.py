from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

REPO_ENGINE_DIR = Path('.aictx')
REPO_MEMORY_DIR = REPO_ENGINE_DIR / 'memory'
REPO_STATE_PATH = REPO_ENGINE_DIR / 'state.json'
DEFAULT_GLOBAL_PREFERENCES_PATH = Path(__file__).resolve().parents[2] / '.aictx' / 'memory' / 'user_preferences.json'

VALID_COMMUNICATION_MODES = {'caveman_lite', 'caveman_full', 'caveman_ultra'}
VALID_COMMUNICATION_LAYERS = {'enabled', 'disabled'}
NATIVE_RUNTIME_REQUIRED_PATHS = [
    Path('CLAUDE.md'),
    Path('.claude/settings.json'),
    Path('.claude/hooks/aictx_session_start.py'),
    Path('.claude/hooks/aictx_user_prompt_submit.py'),
    Path('.claude/hooks/aictx_pre_tool_use.py'),
]


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def normalize_communication_mode(value: Any, default: str = 'caveman_full') -> str:
    normalized = str(value or '').strip().lower()
    if normalized in VALID_COMMUNICATION_MODES:
        return normalized
    return default


def normalize_communication_layer(value: Any, default: str = 'disabled') -> str:
    normalized = str(value or '').strip().lower()
    if normalized in VALID_COMMUNICATION_LAYERS:
        return normalized
    return default


def communication_policy_from_defaults(defaults_payload: dict[str, Any]) -> dict[str, Any]:
    communication = defaults_payload.get('communication', {}) if isinstance(defaults_payload.get('communication'), dict) else {}
    layer = normalize_communication_layer(communication.get('layer'), 'disabled')
    mode = normalize_communication_mode(communication.get('mode'), 'caveman_full')
    intermediate_updates = str(communication.get('intermediate_updates', 'suppressed')).strip().lower() or 'suppressed'
    final_style = str(communication.get('final_style', 'plain_direct_final_only')).strip() or 'plain_direct_final_only'
    return {
        'layer': layer,
        'mode': mode,
        'intermediate_updates': intermediate_updates,
        'final_style': final_style,
        'user_override_wins': True,
        'long_form_on_request': True,
        'step_by_step_on_request': True,
        'applies_to': [
            'implementation_summaries',
            'debugging_reports',
            'patch_explanations',
            'execution_loop_diagnostics',
            'final_execution_results',
        ],
        'does_not_apply_to': [
            'source_code_comments',
            'repository_documentation',
            'marketing_copy',
            'narrative_content',
            'normal_style_user_requested_prose',
        ],
        'preferred_patterns': [
            'found -> cause -> fix',
            'done -> files -> tests',
            'blocked -> reason -> need',
            'next -> verify -> continue',
            'changed A, updated B, left C',
        ],
    }


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _normalized_language(payload: dict[str, Any]) -> str:
    if not isinstance(payload, dict):
        return ''
    return str(
        payload.get('preferred_language')
        or (payload.get('profile', {}) if isinstance(payload.get('profile'), dict) else {}).get('preferred_language')
        or ''
    ).strip()


def _resolve_field(repo_payload: dict[str, Any], global_payload: dict[str, Any], field: str, default: str) -> tuple[str, str]:
    repo_communication = repo_payload.get('communication', {}) if isinstance(repo_payload.get('communication'), dict) else {}
    global_communication = global_payload.get('communication', {}) if isinstance(global_payload.get('communication'), dict) else {}
    repo_value = str(repo_communication.get(field, '') or '').strip()
    if repo_value:
        return repo_value, 'repo_preferences'
    global_value = str(global_communication.get(field, '') or '').strip()
    if global_value:
        return global_value, 'global_defaults'
    return default, 'hardcoded_fallback'


def load_global_preferences(global_defaults_path: Path | None = None) -> dict[str, Any]:
    target = global_defaults_path or DEFAULT_GLOBAL_PREFERENCES_PATH
    return read_json(target, {})


def load_repo_preferences(repo_root: Path | None) -> dict[str, Any]:
    if repo_root is None:
        return {}
    return read_json(repo_root / REPO_MEMORY_DIR / 'user_preferences.json', {})


def resolve_effective_preferences(
    repo_root: Path | None = None,
    *,
    global_defaults_path: Path | None = None,
    explicit_overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    global_payload = load_global_preferences(global_defaults_path)
    repo_payload = load_repo_preferences(repo_root)
    merged = _deep_merge(global_payload, repo_payload)
    if explicit_overrides:
        merged = _deep_merge(merged, explicit_overrides)

    layer, layer_source = _resolve_field(repo_payload, global_payload, 'layer', 'disabled')
    mode, mode_source = _resolve_field(repo_payload, global_payload, 'mode', 'caveman_full')
    intermediate_updates, intermediate_source = _resolve_field(repo_payload, global_payload, 'intermediate_updates', 'suppressed')
    final_style, final_style_source = _resolve_field(repo_payload, global_payload, 'final_style', 'plain_direct_final_only')
    if explicit_overrides and isinstance(explicit_overrides.get('communication'), dict):
        overrides = explicit_overrides['communication']
        if str(overrides.get('layer', '') or '').strip():
            layer, layer_source = str(overrides['layer']).strip(), 'explicit_override'
        if str(overrides.get('mode', '') or '').strip():
            mode, mode_source = str(overrides['mode']).strip(), 'explicit_override'
        if str(overrides.get('intermediate_updates', '') or '').strip():
            intermediate_updates, intermediate_source = str(overrides['intermediate_updates']).strip(), 'explicit_override'
        if str(overrides.get('final_style', '') or '').strip():
            final_style, final_style_source = str(overrides['final_style']).strip(), 'explicit_override'

    merged['communication'] = communication_policy_from_defaults(
        {
            'communication': {
                'layer': layer,
                'mode': mode,
                'intermediate_updates': intermediate_updates,
                'final_style': final_style,
            }
        }
    )

    preferred_language = _normalized_language(repo_payload)
    language_source = 'repo_preferences' if preferred_language else 'unknown'
    if not preferred_language:
        preferred_language = _normalized_language(global_payload)
        language_source = 'global_defaults' if preferred_language else 'hardcoded_fallback'
    if not preferred_language:
        preferred_language = 'unknown'
    merged['preferred_language'] = preferred_language

    return {
        'effective_preferences': merged,
        'sources': {
            'preferred_language': language_source,
            'communication': {
                'layer': layer_source,
                'mode': mode_source,
                'intermediate_updates': intermediate_source,
                'final_style': final_style_source,
            },
        },
        'repo_preferences': repo_payload,
        'global_preferences': global_payload,
        'repo_preferences_path': str((repo_root / REPO_MEMORY_DIR / 'user_preferences.json') if repo_root else ''),
        'global_defaults_path': str(global_defaults_path or DEFAULT_GLOBAL_PREFERENCES_PATH),
    }


def runtime_consistency_report(repo_root: Path | None = None, *, global_defaults_path: Path | None = None) -> dict[str, Any]:
    resolved = resolve_effective_preferences(repo_root, global_defaults_path=global_defaults_path)
    effective_communication = dict(resolved['effective_preferences'].get('communication', {}))
    state_path = (repo_root / REPO_STATE_PATH) if repo_root else None
    prefs_path = (repo_root / REPO_MEMORY_DIR / 'user_preferences.json') if repo_root else None
    state = read_json(state_path, {}) if state_path else {}
    issues: list[dict[str, Any]] = []
    status = 'not_initialized'
    runner_status = str(state.get('runner_integration_status', '') or '').strip()
    missing_runtime_files = [
        str(path)
        for path in NATIVE_RUNTIME_REQUIRED_PATHS
        if repo_root and not (repo_root / path).exists()
    ]

    if repo_root and prefs_path and prefs_path.exists() and state_path and state_path.exists():
        status = 'ok'
        state_layer = str(state.get('communication_layer', '') or '').strip()
        state_mode = str(state.get('communication_mode', '') or '').strip()
        if state_layer and state_layer != effective_communication.get('layer'):
            issues.append(
                {
                    'check': 'communication_layer_mismatch',
                    'expected': effective_communication.get('layer'),
                    'actual': state_layer,
                    'source_of_truth': 'repo_preferences',
                }
            )
        if state_mode and state_mode != effective_communication.get('mode'):
            issues.append(
                {
                    'check': 'communication_mode_mismatch',
                    'expected': effective_communication.get('mode'),
                    'actual': state_mode,
                    'source_of_truth': 'repo_preferences',
                }
            )
        if missing_runtime_files:
            issues.append(
                {
                    'check': 'native_runtime_contract_incomplete',
                    'expected': 'repo-native runtime integration files present',
                    'actual': missing_runtime_files,
                    'source_of_truth': 'repo_runtime_contract',
                }
            )
            if runner_status == 'native_ready':
                issues.append(
                    {
                        'check': 'runner_integration_status_incorrect',
                        'expected': 'runner_integration_status matches on-disk runtime files',
                        'actual': runner_status,
                        'source_of_truth': 'repo_runtime_contract',
                    }
                )
        if issues:
            status = 'warning'
    elif repo_root and ((prefs_path and prefs_path.exists()) or (state_path and state_path.exists())):
        status = 'not_initialized'
        if state_path and state_path.exists() and missing_runtime_files:
            issues.append(
                {
                    'check': 'native_runtime_contract_incomplete',
                    'expected': 'repo-native runtime integration files present',
                    'actual': missing_runtime_files,
                    'source_of_truth': 'repo_runtime_contract',
                }
            )
            if runner_status == 'native_ready':
                issues.append(
                    {
                        'check': 'runner_integration_status_incorrect',
                        'expected': 'runner_integration_status matches on-disk runtime files',
                        'actual': runner_status,
                        'source_of_truth': 'repo_runtime_contract',
                    }
                )
            status = 'warning'

    return {
        'status': status,
        'checked_files': {
            'repo_preferences': str(prefs_path) if prefs_path else '',
            'repo_state': str(state_path) if state_path else '',
            'global_defaults': resolved['global_defaults_path'],
        },
        'effective_communication_policy': effective_communication,
        'sources': resolved['sources'].get('communication', {}),
        'issues': issues,
        'repair_hint': 'Run `aictx internal migrate` to restore missing AICTX repo runtime files.' if any(issue.get('check') == 'native_runtime_contract_incomplete' for issue in issues) else '',
    }
