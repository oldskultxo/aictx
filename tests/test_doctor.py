from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.doctor import build_doctor_report
from aictx.scaffold import init_repo_scaffold


def test_doctor_parser_and_json_output(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "Makefile").write_text(
        "smoke:\n\taictx resume --repo . --task \"goal\" --json\nci: test smoke wheel-install-check\n",
        encoding="utf-8",
    )
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text("steps:\n  - run: make ci\n", encoding="utf-8")

    parser = cli.build_parser()
    args = parser.parse_args(["doctor", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] in {"ok", "warning", "error"}
    assert payload["version"]
    assert {check["name"] for check in payload["checks"]} >= {
        "cli_version",
        "repo_initialized",
        "runner_files_present",
        "lifecycle_smoke_compatibility",
        "repomap_status",
        "capture_quality",
        "contract_compliance_health",
        "stale_duplicate_memory",
        "makefile_ci_compatibility",
    }


def test_doctor_is_read_only(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    before = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))

    report = build_doctor_report(repo)

    after = sorted(path.relative_to(repo).as_posix() for path in repo.rglob("*"))
    assert report["checks"]
    assert after == before


def test_doctor_flags_request_flag_in_smoke(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / "Makefile").write_text("smoke:\n\taictx resume --repo . --request \"goal\" --json\n", encoding="utf-8")

    report = build_doctor_report(repo)
    lifecycle = next(check for check in report["checks"] if check["name"] == "lifecycle_smoke_compatibility")

    assert lifecycle["status"] == "error"
    assert any("--task" in action for action in report["recommended_actions"])
