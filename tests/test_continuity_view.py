from __future__ import annotations

import json
import base64
import zlib
from pathlib import Path

import aictx.cli as cli
from aictx.continuity import append_handoff_history, build_resume_capsule
from aictx.continuity_view import (
    CONTINUITY_MAP_PATH,
    CONTINUITY_VIEW_PATH,
    build_continuity_view_model,
    mermaid_live_url,
    render_continuity_markdown,
    render_continuity_mermaid,
)
from aictx.failures import FAILURE_PATTERNS_PATH
from aictx.repo_map.config import write_repomap_config, write_repomap_index
from aictx.scaffold import init_repo_scaffold
from aictx.state import REPO_METRICS_DIR
from aictx.strategy_memory import STRATEGIES_PATH
from aictx.work_state import close_work_state, start_work_state


def _parser():
    return cli.build_parser()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def test_empty_continuity_view_is_deterministic_and_has_required_sections(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    first = render_continuity_mermaid(build_continuity_view_model(repo))
    second = render_continuity_mermaid(build_continuity_view_model(repo))
    markdown = render_continuity_markdown(build_continuity_view_model(repo))

    assert first == second
    assert first.startswith("flowchart TD\n")
    assert 'Repo["Repo: repo | unknown @ unknown"]' in first
    assert 'Empty["No active continuity signals found"]' in first
    for heading in (
        "## Overview",
        "## Continuity Map",
        "## Working Tree Changes",
        "## Active Work State",
        "## Open Handoffs",
        "## Relevant Failures",
        "## Strategy Memory",
        "## Execution Contracts",
        "## Execution Summaries",
        "## RepoMap Hints",
        "## Portable Continuity",
        "## Notes for the Next Agent",
    ):
        assert heading in markdown


def test_full_continuity_view_model_and_mermaid_order(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(
        repo,
        "SEO docs update",
        initial={"next_action": "verify deployed title", "risks": ["Google still showing old snippet"], "active_files": ["docs/index.html"]},
        source="test",
    )
    append_handoff_history(
        repo,
        {"summary": "Request Google recrawl", "next_steps": ["submit sitemap"], "updated_at": "2026-05-17T00:00:00Z"},
    )
    _write_jsonl(
        repo / FAILURE_PATTERNS_PATH,
        [
            {
                "failure_id": "failure-1",
                "signature": "sitemap not submitted",
                "error_text": "Sitemap not submitted",
                "status": "open",
                "area_id": "docs",
                "timestamp": "2026-05-17T00:00:00Z",
            }
        ],
    )
    _write_jsonl(
        repo / STRATEGIES_PATH,
        [
            {
                "id": "strategy-1",
                "summary": "Reuse docs verification path",
                "task_type": "feature_work",
                "success": True,
                "entry_points": ["docs/index.html"],
                "timestamp": "2026-05-17T00:00:00Z",
            }
        ],
    )
    _write_jsonl(
        repo / REPO_METRICS_DIR / "execution_feedback.jsonl",
        [
            {
                "execution_id": "exec-1",
                "timestamp": "2026-05-17T00:00:00Z",
                "agent_summary": {"handoff_payload": {"summary": "Docs updated"}},
            }
        ],
    )
    write_repomap_config(repo, {"enabled": True})
    write_repomap_index(
        repo,
        {
            "version": 1,
            "files": [
                {"path": "docs/index.html", "language": "html", "symbols": [{"name": "title", "kind": "heading"}]},
                {"path": "docs/sitemap.xml", "language": "xml", "symbols": []},
            ],
        },
    )
    build_resume_capsule(repo, "Verify docs and sitemap")

    model = build_continuity_view_model(repo)
    mermaid = render_continuity_mermaid(model)

    assert model["summary"]["active_work_state"] is True
    assert model["summary"]["open_handoffs"] == 1
    assert model["summary"]["relevant_failures"] == 1
    assert model["summary"]["execution_contracts"] == 1
    assert model["summary"]["execution_summaries"] == 1
    assert model["summary"]["repomap_hints"] == 2
    assert mermaid.index("WS[") < mermaid.index("EC[") < mermaid.index("ES1[") < mermaid.index("HF1[") < mermaid.index("FM1[")
    assert "SM1[" in mermaid
    assert "RM1[" in mermaid
    assert "PC[" in mermaid


def test_recent_inactive_work_state_is_not_overview_active_task(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    start_work_state(repo, "Old blocked task", initial={"next_action": "wait for CI"})
    close_work_state(repo, status="blocked", patch={"risks": ["CI unavailable"]})

    model = build_continuity_view_model(repo)
    markdown = render_continuity_markdown(model)
    mermaid = render_continuity_mermaid(model)

    assert model["work_state"]["exists"] is True
    assert model["work_state"]["source"] == "recent"
    assert model["summary"]["active_work_state"] is False
    assert "- Active task: None" in markdown
    assert "Blocked Work: Old blocked task" in mermaid


def test_mermaid_label_sanitization_and_truncation():
    model = {
        "work_state": {"exists": True, "title": 'Bad "label" [x] <tag> with a very long suffix that should be truncated for mermaid safety'},
        "execution_contract": {"exists": False},
        "execution_summaries": [],
        "open_handoffs": [],
        "relevant_failures": [],
        "strategies": [],
        "area_memory": [],
        "repomap_hints": [],
        "portable_continuity": {"status": "local-only"},
    }

    mermaid = render_continuity_mermaid(model)

    assert "Bad 'label' x tag" in mermaid
    assert "[x]" not in mermaid
    assert "<tag>" not in mermaid


def test_handoff_and_failure_mermaid_nodes_keep_weighted_details():
    model = {
        "repository": {"name": "repo", "branch": "main", "commit": "abc123", "dirty": False},
        "work_state": {"exists": False},
        "execution_contract": {"exists": False},
        "execution_summaries": [],
        "open_handoffs": [
            {
                "id": "handoff-1",
                "title": "Finish deterministic continuity summary rendering",
                "status": "open",
                "next_steps": ["validate mermaid live link in final summary", "preserve compact markdown link labels"],
                "open_items": ["confirm Copilot instructions include continuity_view_online"],
            }
        ],
        "relevant_failures": [
            {
                "id": "failure-1",
                "title": "Mermaid live link rendered as placeholder instead of real payload URL",
                "status": "open",
                "severity": "error",
                "area_id": "src/aictx/continuity_view.py",
                "related_paths": ["src/aictx/middleware/__init__.py", "tests/test_continuity_view.py"],
            }
        ],
        "strategies": [],
        "area_memory": [],
        "repomap_hints": [],
        "portable_continuity": {"status": "local-only"},
    }

    mermaid = render_continuity_mermaid(model)

    assert "HF1[" in mermaid
    assert "open: Finish deterministic continuity summary rendering" in mermaid
    assert "next: validate mermaid live link in final summary" in mermaid
    assert "open: confirm Copilot instructions include continuity_view_online" in mermaid
    assert "<br/>" in mermaid
    assert "FM1[" in mermaid
    assert "open error: Mermaid live link rendered as placeholder instead of real payload URL" in mermaid
    assert "area: src/aictx/continuity_view.py" in mermaid
    assert "path: src/aictx/middleware/__init__.py" in mermaid


def test_mermaid_live_url_encodes_diagram_for_online_view():
    mermaid = "flowchart TD\n  A[Start] --> B[End]\n"
    url = mermaid_live_url(mermaid)
    encoded = url.split("#pako:", 1)[1]
    padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
    payload = json.loads(zlib.decompress(base64.urlsafe_b64decode(padded)).decode("utf-8"))
    mermaid_config = json.loads(payload["mermaid"])

    assert url.startswith("https://mermaid.live/view#pako:")
    assert "=" not in encoded
    assert "+" not in encoded
    assert "/" not in encoded
    assert payload["code"] == mermaid
    assert mermaid_config["theme"] == "default"
    assert isinstance(payload["mermaid"], str)
    assert payload["rough"] is False
    assert payload["updateDiagram"] is True
    assert payload["editorMode"] == "code"
    assert "autoSync" not in payload


def test_view_cli_creates_files_mermaid_stdout_json_and_custom_output(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["view", "--repo", str(repo)])
    assert args.func(args) == 0
    output = capsys.readouterr().out
    assert "AICTX Continuity View generated." in output
    assert (repo / CONTINUITY_VIEW_PATH).exists()
    assert (repo / CONTINUITY_MAP_PATH).exists()

    args = _parser().parse_args(["view", "--repo", str(repo), "--mermaid"])
    assert args.func(args) == 0
    mermaid = capsys.readouterr().out
    assert mermaid.startswith("flowchart TD\n")
    assert "```" not in mermaid

    args = _parser().parse_args(["view", "--repo", str(repo), "--output", "custom-view.md", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["view"]["markdown_path"] == "custom-view.md"
    assert (repo / "custom-view.md").exists()


def test_finalize_include_view_and_resume_json_integration(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)

    args = _parser().parse_args(["finalize", "--repo", str(repo), "--status", "success", "--summary", "done"])
    assert args.func(args) == 0
    assert "Continuity View:" not in capsys.readouterr().out

    args = _parser().parse_args(["finalize", "--repo", str(repo), "--status", "success", "--summary", "done", "--include-view", "--json"])
    assert args.func(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["continuity_view"]["markdown_path"] == ".aictx/reports/continuity-view.md"
    assert (repo / CONTINUITY_VIEW_PATH).exists()
    assert (repo / CONTINUITY_MAP_PATH).exists()
    assert "Continuity view file: [continuity-map.mmd](.aictx/reports/continuity-map.mmd)" in payload["agent_summary_text"]
    assert "View continuity online: [mermaid.live view](https://mermaid.live/view#pako:" in payload["agent_summary_text"]
    encoded = payload["agent_summary_text"].split("https://mermaid.live/view#pako:", 1)[1].split(")", 1)[0]
    padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
    decoded = json.loads(zlib.decompress(base64.urlsafe_b64decode(padded)).decode("utf-8"))
    assert decoded["code"].startswith("flowchart TD")

    args = _parser().parse_args(["resume", "--repo", str(repo), "--task", "continue", "--json"])
    assert args.func(args) == 0
    resume_payload = json.loads(capsys.readouterr().out)
    assert resume_payload["continuity_view"]["exists"] is True
    assert resume_payload["continuity_view"]["markdown_path"] == ".aictx/reports/continuity-view.md"
    assert resume_payload["continuity_view"]["mermaid_path"] == ".aictx/reports/continuity-map.mmd"
