from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from aictx.continuity import AICTX_TEXT_SEPARATOR
from aictx.middleware import finalize_execution, prepare_execution
from aictx import runtime_compact
from aictx.scaffold import init_repo_scaffold
from aictx.work_state import start_work_state


def _payload(repo: Path, execution_id: str) -> dict:
    return {
        "repo_root": str(repo),
        "user_request": "summarize continuity outcome",
        "agent_id": "codex",
        "adapter_id": "codex",
        "execution_id": execution_id,
        "timestamp": "2026-04-24T14:30:00Z",
        "files_opened": ["src/aictx/middleware.py"],
    }


def test_final_summary_with_reuse_reports_continuity_and_stored_artifacts(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution({**_payload(repo, "exec-summary-reuse"), "files_edited": ["src/aictx/middleware.py"]})
    prepared["execution_hint"] = {
        "selection_reason": "previous_successful_execution",
        "entry_points": ["src/aictx/middleware.py"],
    }
    prepared["continuity_context"]["loaded"]["handoff"] = True
    prepared["continuity_context"]["loaded"]["decisions"] = True
    prepared["repo_map_status"] = {
        "enabled": True,
        "available": True,
        "used": True,
        "refresh_mode": "quick",
        "refresh_status": "ok",
    }

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Updated continuity final summary.",
            "validated_learning": False,
            "decisions": [
                {
                    "decision": "Use continuity-first final summaries.",
                    "rationale": "Agents need compact evidence of reused and stored continuity.",
                }
            ],
        },
    )

    text = finalized["agent_summary_text"]
    assert text.startswith(f"{AICTX_TEXT_SEPARATOR}\nAICTX summary\n")
    assert text.count(AICTX_TEXT_SEPARATOR) == 1
    assert "; aictx" not in text.lower()
    assert "because" not in text.lower()
    assert "unknown" not in text.lower()
    assert "Context: reused previous strategy based on src/aictx/middleware.py + loaded handoff/decisions/preferences." in text
    assert "Map: RepoMap quick ok." in text
    assert "Saved: updated handoff and updated decision memory." in text
    assert "Entry point: src/aictx/middleware.py." in text
    assert "0 tests" not in text
    assert text.endswith("Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)")
    assert finalized["agent_summary"]["handoff_stored"] is True
    assert finalized["agent_summary"]["decision_stored"] is True
    policy = finalized["agent_summary_policy"]
    assert policy["render_in_user_language"] is True
    assert policy["allow_language_adaptation"] is True
    assert policy["allow_semantic_localization"] is True
    assert policy["localize_from_structured_fields"] is True
    assert policy["allow_fact_enrichment"] is False
    assert policy["preserve_facts"] is True
    assert policy["preserve_canonical_payload"] is True
    assert policy["render_payload_field"] == "agent_summary_render_payload"
    assert policy["do_not_invent"] is True
    assert finalized["agent_summary_render_payload"]["sections"][0]["kind"] == "context"
    detailed_path = repo / ".aictx" / "continuity" / "last_execution_summary.md"
    assert detailed_path.exists()
    detailed = detailed_path.read_text(encoding="utf-8")
    assert "# AICTX Execution Summary" in detailed
    assert "- Reused strategy: yes" in detailed
    assert "- Strategy entry points: src/aictx/middleware.py" in detailed
    assert "- Handoff stored: yes" in detailed
    assert "- AICTX value sources: handoff, decisions, preferences" in detailed
    assert "- RepoMap: enabled=yes, used=yes, status=ok" in detailed
    assert "- Files observed: 1" in detailed
    assert "Tests observed" not in detailed
    assert "Commands observed: 0" not in detailed
    assert "Reopened files: 0" not in detailed


def test_final_summary_without_reuse_is_honest_and_compatible(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-summary-no-reuse"))

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "", "validated_learning": False},
    )

    text = finalized["agent_summary_text"]
    assert text == (
        f"{AICTX_TEXT_SEPARATOR}\n"
        "AICTX summary\n\n"
        "Context: loaded preferences.\n"
        "Contract: not evaluated — no matching resume contract.\n"
        "Details: [last_execution_summary.md](.aictx/continuity/last_execution_summary.md)"
    )


def test_final_summary_mentions_work_state_update_when_present(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix login token refresh")
    prepared = prepare_execution({**_payload(repo, "exec-summary-work-state"), "commands_executed": ["pytest -q tests/test_auth.py"]})

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "Updated work state.", "validated_learning": False},
    )

    text = finalized["agent_summary_text"]
    assert "Saved: updated handoff and updated Work State." in text
    detailed = (repo / ".aictx" / "continuity" / "last_execution_summary.md").read_text(encoding="utf-8")
    assert "- Work state updated: fix-login-token-refresh" in detailed


def test_final_summary_uses_next_only_for_real_pending_work(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-summary-next"))

    finalized = finalize_execution(
        prepared,
        {
            "success": True,
            "result_summary": "Updated docs.",
            "validated_learning": False,
            "handoff": {
                "summary": "Updated docs.",
                "next_steps": ["update docs examples for summary output"],
                "recommended_starting_points": ["docs/EXECUTION_SUMMARY.md"],
            },
        },
    )

    text = finalized["agent_summary_text"]
    assert "Next: update docs examples for summary output." in text
    assert "Entry point:" not in text


def test_final_summary_omits_map_when_not_used(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-summary-no-map"))
    prepared["repo_map_status"] = {"enabled": False, "available": False, "used": False}

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "Done.", "validated_learning": False},
    )

    assert "Map:" not in finalized["agent_summary_text"]


def test_final_summary_uses_live_bytes_for_maintenance_warning_and_payload(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    monkeypatch.setattr(runtime_compact, "_now", lambda: datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc))
    baseline_notice = runtime_compact.evaluate_maintenance_notice(repo, update_status=False)
    baseline_live_bytes = int(baseline_notice["live_bytes"])
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_WARNING_THRESHOLD_BYTES", baseline_live_bytes + 64 * 1024)
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_STRONG_THRESHOLD_BYTES", baseline_live_bytes + 128 * 1024)

    (repo / ".aictx" / "archive" / "big.bin").parent.mkdir(parents=True, exist_ok=True)
    (repo / ".aictx" / "archive" / "big.bin").write_bytes(b"x" * (128 * 1024))
    archive_only = finalize_execution(
        prepare_execution(_payload(repo, "exec-summary-maintenance-archive-only")),
        {"success": True, "result_summary": "Done.", "validated_learning": False},
    )
    assert "Maintenance:" not in archive_only["agent_summary_text"]
    archive_notice = archive_only["agent_summary"]["maintenance_notice"]
    assert archive_notice["live_bytes"] < runtime_compact.MAINTENANCE_WARNING_THRESHOLD_BYTES
    assert archive_notice["archive_bytes"] >= 128 * 1024
    assert archive_notice["total_bytes"] == archive_notice["live_bytes"] + archive_notice["archive_bytes"]

    (repo / ".aictx" / "big-live.bin").write_bytes(b"x" * (96 * 1024))
    monkeypatch.setattr(runtime_compact, "_now", lambda: datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc))
    prepared = prepare_execution(_payload(repo, "exec-summary-maintenance-live"))
    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "Done.", "validated_learning": False},
    )

    text = finalized["agent_summary_text"]
    assert "Maintenance: .aictx live history high (" in text
    assert "Recommend: aictx internal compact --repo ." in text
    assert any(section["kind"] == "maintenance" for section in finalized["agent_summary_render_payload"]["sections"])
    notice = finalized["agent_summary"]["maintenance_notice"]
    assert notice["live_bytes"] >= baseline_live_bytes + 64 * 1024
    assert notice["archive_bytes"] >= 128 * 1024
    assert notice["total_bytes"] == notice["live_bytes"] + notice["archive_bytes"]
    assert notice["live_size_display"].endswith("MB")
    assert notice["archive_size_display"].endswith("MB")
    status = json.loads((repo / ".aictx" / "metrics" / "maintenance_status.json").read_text(encoding="utf-8"))
    assert status["last_warning_reason"] == "aictx_size_high"


def test_final_summary_omits_maintenance_warning_below_threshold_and_during_cooldown(tmp_path: Path, monkeypatch):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / ".aictx" / "blob.bin").write_bytes(b"x" * 2048)
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_WARNING_THRESHOLD_BYTES", 1024)
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_STRONG_THRESHOLD_BYTES", 4096)

    first_now = datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime_compact, "_now", lambda: first_now)
    first = finalize_execution(
        prepare_execution(_payload(repo, "exec-summary-maintenance-first")),
        {"success": True, "result_summary": "Done.", "validated_learning": False},
    )
    assert "Maintenance: .aictx live history high (" in first["agent_summary_text"]

    second_now = datetime(2026, 4, 30, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(runtime_compact, "_now", lambda: second_now)
    second = finalize_execution(
        prepare_execution(_payload(repo, "exec-summary-maintenance-second")),
        {"success": True, "result_summary": "Done again.", "validated_learning": False},
    )
    assert "Maintenance:" not in second["agent_summary_text"]

    small_repo = tmp_path / "small-repo"
    init_repo_scaffold(small_repo, update_gitignore=False)
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_WARNING_THRESHOLD_BYTES", 10 * 1024 * 1024)
    monkeypatch.setattr(runtime_compact, "MAINTENANCE_STRONG_THRESHOLD_BYTES", 20 * 1024 * 1024)
    third = finalize_execution(
        prepare_execution(_payload(small_repo, "exec-summary-maintenance-small")),
        {"success": True, "result_summary": "Small.", "validated_learning": False},
    )
    assert "Maintenance:" not in third["agent_summary_text"]
