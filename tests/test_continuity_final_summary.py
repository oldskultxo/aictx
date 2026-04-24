from __future__ import annotations

from pathlib import Path

from aictx.middleware import finalize_execution, prepare_execution
from aictx.scaffold import init_repo_scaffold


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
    assert text.startswith("AICTX\n\nContinuity:")
    assert "- strategy: previous_successful_execution" in text
    assert "- handoff" in text
    assert "- decisions" in text
    assert "Stored:\n- handoff: yes\n- decision: yes\n- failure_pattern: no" in text
    assert "Avoided:\n- none observed" in text
    assert "Next session:\n- src/aictx/middleware.py" in text
    assert "- Reused strategy: yes" in text
    assert finalized["agent_summary"]["handoff_stored"] is True
    assert finalized["agent_summary"]["decision_stored"] is True


def test_final_summary_without_reuse_is_honest_and_compatible(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    prepared = prepare_execution(_payload(repo, "exec-summary-no-reuse"))

    finalized = finalize_execution(
        prepared,
        {"success": True, "result_summary": "", "validated_learning": False},
    )

    text = finalized["agent_summary_text"]
    assert "Continuity:\n- No prior continuity context was reused" in text
    assert "Stored:\n- handoff: no\n- decision: no\n- failure_pattern: no" in text
    assert "Avoided:\n- none observed" in text
    assert "Next session:\n- No specific handoff guidance stored" in text
    assert "- Reused strategy: no" in text
