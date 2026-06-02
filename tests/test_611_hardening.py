from __future__ import annotations

import subprocess
from pathlib import Path

from aictx.continuity import build_resume_capsule
from aictx.middleware import build_contract_adherence, capture_git_state, parse_git_porcelain
from aictx.scaffold import init_repo_scaffold
from aictx.steer_guard import build_steer_guard
from aictx.strategy_memory import build_strategy_entry
from aictx.work_state import compact_work_state_for_prepare, start_work_state, update_work_state


def test_discarded_hypotheses_normalize_and_brief_resume_capsule(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Fix release hardening")
    update_work_state(
        repo,
        {
            "discarded_hypotheses": [
                {"hypothesis": "Parser regression is caused by docs", "reason": "user corrected scope", "confidence": "high", "related_paths": ["docs/README.md"]},
                {"hypothesis": "Second dead end", "reason": "not relevant"},
            ],
            "next_action": "inspect runtime",
        },
    )

    compact = compact_work_state_for_prepare(update_work_state(repo, {"verified": ["state saved"]}))
    assert len(compact["discarded_hypotheses"]) == 2

    capsule = build_resume_capsule(repo, "continue hardening", brief=True)
    assert capsule["mode"] == "brief"
    assert len(capsule["discarded_hypotheses"]) == 1
    assert capsule["discarded_hypotheses"][0]["hypothesis"] == "Parser regression is caused by docs"


def test_steer_guard_correction_suggests_discarded_hypothesis(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    payload = build_steer_guard(repo, message="that's wrong, not that path src/aictx/cleanup.py")

    assert payload["classification"] == "agent_correction"
    discarded = payload["suggested_updates"]["discarded_hypothesis"]
    assert discarded["evidence"] == "user_correction"
    assert discarded["related_paths"] == ["src/aictx/cleanup.py"]


def test_strategy_entry_includes_rationale_and_evidence_quality() -> None:
    prepared = {
        "envelope": {"execution_id": "exec-1", "user_request": "harden release"},
        "effective_task_type": "implementation",
        "effective_area_id": "src/aictx",
        "continuity_context": {
            "active_work_state": {
                "discarded_hypotheses": [
                    {"hypothesis": "old hook plan", "reason": "too noisy", "confidence": "medium", "related_paths": ["src/aictx/runner_integrations.py"]}
                ]
            }
        },
    }
    log = {"files_edited": ["src/aictx/work_state.py"], "tests_executed": ["pytest tests/test_611_hardening.py"], "commands_executed": ["pytest tests/test_611_hardening.py"]}

    entry = build_strategy_entry(prepared, log, timestamp="2026-06-02T00:00:00Z", is_failure=False)

    assert entry["why_it_worked"].startswith("Validated by pytest")
    assert entry["reuse_when"] == "Reuse for implementation tasks in src/aictx."
    assert entry["avoid_when"]
    assert entry["evidence_quality"] == "high"
    assert entry["discarded_hypotheses"][0]["hypothesis"] == "old hook plan"


def test_git_state_parses_staged_unstaged_untracked_and_edited(tmp_path: Path) -> None:
    parsed = parse_git_porcelain(["M  staged.py", " M unstaged.py", "?? new.py", "R  old.py -> renamed.py", "MM both.py"])
    assert parsed["staged_files"] == ["staged.py", "renamed.py", "both.py"]
    assert parsed["unstaged_files"] == ["unstaged.py", "new.py", "both.py"]
    assert parsed["untracked_files"] == ["new.py"]

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    (repo / "tracked.py").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    (repo / "tracked.py").write_text("b\n", encoding="utf-8")
    (repo / "new.py").write_text("n\n", encoding="utf-8")

    state = capture_git_state(repo, files_edited=["tracked.py", "new.py"])

    assert state["dirty"] is True
    assert set(state["files_edited_uncommitted"]) == {"tracked.py", "new.py"}
    assert set(state["files_edited_unstaged"]) == {"tracked.py", "new.py"}


def test_contract_adherence_respects_validation_policy_and_analysis_task() -> None:
    prepared = {
        "resolved_task_type": "analysis",
        "resume_contract": {
            "generated_at": "2026-06-02T00:00:00Z",
            "execution_contract": {
                "task_goal": "inspect release",
                "contract_strength": "exploratory",
                "first_action": {"path": "src/aictx/cleanup.py"},
                "edit_scope": {"primary": ["src/aictx/cleanup.py"], "secondary_if_needed": []},
                "test_command": {"command": "pytest tests/test_expected.py"},
                "validation_policy": {"required": False},
            },
        },
    }
    log = {"files_opened": [], "files_edited": [], "commands_executed": [], "tests_executed": []}

    adherence = build_contract_adherence(prepared, log)

    assert adherence["first_action_enforced"] is False
    assert adherence["validation_required"] is False
    assert "missing_first_action_open" not in adherence["violations"]
    assert "canonical_test_not_observed" not in adherence["violations"]
