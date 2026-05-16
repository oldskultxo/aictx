from __future__ import annotations

from pathlib import Path

from aictx.doctor import build_doctor_report
from aictx.runner_integrations import (
    AICTX_END,
    AICTX_START,
    COPILOT_FINALIZE_PROMPT_PATH,
    COPILOT_PATH_INSTRUCTIONS_PATH,
    COPILOT_RESUME_PROMPT_PATH,
    install_repo_runner_integrations,
)


def test_install_repo_runner_integrations_creates_copilot_instructions(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    created = install_repo_runner_integrations(repo)

    copilot_path = repo / ".github" / "copilot-instructions.md"
    assert copilot_path in created
    assert copilot_path.exists()
    assert repo / COPILOT_PATH_INSTRUCTIONS_PATH in created
    assert repo / COPILOT_RESUME_PROMPT_PATH in created
    assert repo / COPILOT_FINALIZE_PROMPT_PATH in created
    assert (repo / COPILOT_PATH_INSTRUCTIONS_PATH).exists()
    assert (repo / COPILOT_RESUME_PROMPT_PATH).exists()
    assert (repo / COPILOT_FINALIZE_PROMPT_PATH).exists()


def test_copilot_instructions_include_expected_resume_and_finalize_commands(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    install_repo_runner_integrations(repo)

    text = (repo / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert 'aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json' in text
    assert 'aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json' in text
    assert "If command execution is unavailable" in text

    path_text = (repo / COPILOT_PATH_INSTRUCTIONS_PATH).read_text(encoding="utf-8")
    assert 'applyTo: "**/*"' in path_text
    assert 'aictx resume --repo . --task "<task goal>" --agent-id copilot --adapter-id copilot-vscode --json' in path_text
    assert 'aictx finalize --repo . --status success|failure --summary "<what happened>" --agent-id copilot --adapter-id copilot-vscode --json' in path_text


def test_install_repo_runner_integrations_is_idempotent_for_copilot_block(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    install_repo_runner_integrations(repo)
    install_repo_runner_integrations(repo)

    text = (repo / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert text.count(AICTX_START) == 1
    assert text.count(AICTX_END) == 1
    assert text.count("# AICTX GitHub Copilot integration") == 1
    path_text = (repo / COPILOT_PATH_INSTRUCTIONS_PATH).read_text(encoding="utf-8")
    assert path_text.count(AICTX_START) == 1
    assert path_text.count(AICTX_END) == 1
    assert path_text.count("applyTo:") == 1


def test_install_repo_runner_integrations_preserves_existing_copilot_user_content(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    copilot_path = repo / ".github" / "copilot-instructions.md"
    copilot_path.parent.mkdir(parents=True, exist_ok=True)
    copilot_path.write_text("# Team notes\n\nKeep terse answers.\n", encoding="utf-8")

    install_repo_runner_integrations(repo)

    text = copilot_path.read_text(encoding="utf-8")
    assert "# Team notes" in text
    assert "Keep terse answers." in text
    assert text.count(AICTX_START) == 1


def test_install_repo_runner_integrations_preserves_existing_path_specific_user_content(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    path = repo / COPILOT_PATH_INSTRUCTIONS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# Team path notes\n\nKeep focused.\n", encoding="utf-8")

    install_repo_runner_integrations(repo)

    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\napplyTo: \"**/*\"\n---")
    assert "# Team path notes" in text
    assert "Keep focused." in text
    assert text.count(AICTX_START) == 1


def test_doctor_reports_copilot_instruction_hardening(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    install_repo_runner_integrations(repo)

    report = build_doctor_report(repo)
    check = next(item for item in report["checks"] if item["name"] == "copilot_instruction_hardening")
    assert check["status"] == "ok"
    assert check["details"]["best_effort_instruction_based"] is True
    assert check["details"]["repo_instructions_block_within_code_review_limit"] is True


def test_install_repo_runner_integrations_still_creates_existing_claude_files(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    install_repo_runner_integrations(repo)

    assert (repo / "CLAUDE.md").exists()
    assert (repo / ".claude" / "settings.json").exists()
    assert (repo / ".claude" / "hooks" / "aictx_session_start.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_user_prompt_submit.py").exists()
    assert (repo / ".claude" / "hooks" / "aictx_pre_tool_use.py").exists()
