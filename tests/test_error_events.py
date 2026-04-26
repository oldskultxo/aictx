from __future__ import annotations

import json
from pathlib import Path

from aictx import cli
from aictx.failure_memory import load_failures, lookup_failures
from aictx.middleware import build_agent_summary, finalize_execution, prepare_execution
from aictx.report import build_real_usage_report
from aictx.runtime_capture import build_capture, error_events_from_output, notable_errors_from_events
from aictx.scaffold import init_repo_scaffold


def test_error_events_parse_broad_toolchains() -> None:
    samples = [
        ("python", "pytest", "AssertionError: expected 1"),
        ("pyright", "pyright", "src/app.py:10:5 - error: Type mismatch (reportAssignmentType)"),
        ("mypy", "mypy", "src/app.py:10: error: Incompatible types [assignment]"),
        ("ruff", "ruff", "src/app.py:10:5: F401 unused import"),
        ("typescript", "npx tsc", "src/app.ts(4,7): error TS2322: Type 'string' is not assignable to type 'number'."),
        ("eslint", "npx eslint", "src/app.ts:4:7: Unexpected any no-explicit-any"),
        ("go", "go test ./...", "main.go:12:3: undefined: thing"),
        ("rust", "cargo test", "error[E0425]: cannot find value `x` in this scope"),
        ("java", "javac Main.java", "src/Main.java:7: error: cannot find symbol"),
        ("java", "mvn test", "[ERROR] src/Main.java:[7,13] cannot find symbol"),
        ("dotnet", "dotnet build", "Program.cs(10,5): error CS1002: ; expected"),
        ("c_cpp", "gcc main.c", "main.c:3:5: error: use of undeclared identifier 'x'"),
        ("ruby", "ruby app.rb", "app.rb:4: undefined method `x' for nil:NilClass"),
        ("php", "php index.php", "PHP Fatal error: Call to undefined function foo() in index.php on line 9"),
    ]

    for expected_toolchain, command, output in samples:
        events = error_events_from_output(1, "", output, command)
        assert events, expected_toolchain
        assert events[0]["toolchain"] == expected_toolchain
        assert events[0]["fingerprint"]


def test_error_events_fallback_and_notable_errors() -> None:
    events = error_events_from_output(2, "", "mystery exploded badly", "custom-build")

    assert events[0]["toolchain"] == "unknown"
    assert events[0]["phase"] == "build"
    assert "mystery exploded badly" in notable_errors_from_events(events)[0]


def test_error_events_deduplicate_specific_and_generic_matches() -> None:
    events = error_events_from_output(1, "", "src/app.ts(4,7): error TS2322: Type mismatch", "npx tsc --noEmit")

    assert len(events) == 1
    assert events[0]["toolchain"] == "typescript"
    assert events[0]["code"] == "TS2322"


def test_build_capture_derives_notable_errors_from_explicit_error_events(tmp_path: Path) -> None:
    event = {
        "toolchain": "typescript",
        "phase": "typecheck",
        "message": "Type mismatch",
        "code": "TS2322",
        "file": "src/app.ts",
        "line": "4",
    }

    capture = build_capture({"error_events": [event]})

    assert capture["error_events"][0]["toolchain"] == "typescript"
    assert capture["notable_errors"] == ["typescript:typecheck: TS2322 src/app.ts:4 Type mismatch"]
    assert capture["provenance"]["notable_errors"] == "derived_from_error_events"


def test_finalize_persists_structured_failure_and_prepare_reuses_it(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    event = {
        "toolchain": "typescript",
        "phase": "typecheck",
        "message": "Type mismatch",
        "code": "TS2322",
        "file": "src/app.ts",
        "line": "4",
        "fingerprint": "typescript_typecheck_ts2322_src_app_ts_type_mismatch",
    }
    prepared = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix TS2322 type mismatch",
            "agent_id": "codex",
            "execution_id": "event-failure",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/app.ts"],
            "commands_executed": ["npx tsc --noEmit"],
            "error_events": [event],
        }
    )

    finalized = finalize_execution(prepared, {"success": False, "result_summary": "tsc failed", "validated_learning": False})

    rows = load_failures(repo)
    assert finalized["failure_persisted"]["failure_id"]
    assert rows[-1]["error_events"][0]["code"] == "TS2322"
    assert rows[-1]["toolchains"] == ["typescript"]
    assert rows[-1]["phases"] == ["typecheck"]
    assert "aprendió un patrón de fallo" in finalized["agent_summary_text"]
    assert lookup_failures(repo, task_type="bug_fixing", text="TS2322 type mismatch", files=["src/app.ts"], area_id="src")

    reused = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix TS2322 type mismatch",
            "agent_id": "codex",
            "execution_id": "event-reuse",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/app.ts"],
        }
    )
    assert reused["related_failures"]


def test_repeated_failure_summary_recognizes_existing_pattern(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    event = {
        "toolchain": "typescript",
        "phase": "typecheck",
        "message": "Type mismatch",
        "code": "TS2322",
        "file": "src/app.ts",
        "fingerprint": "typescript_typecheck_ts2322_src_app_ts_type_mismatch",
    }
    for execution_id in ("event-first", "event-second"):
        prepared = prepare_execution(
            {
                "repo_root": str(repo),
                "user_request": "fix TS2322 type mismatch",
                "agent_id": "codex",
                "execution_id": execution_id,
                "declared_task_type": "bug_fixing",
                "files_opened": ["src/app.ts"],
                "commands_executed": ["npx tsc --noEmit"],
                "error_events": [event],
            }
        )
        finalized = finalize_execution(prepared, {"success": False, "result_summary": "tsc failed", "validated_learning": False})

    assert finalized["failure_persisted"]["existing"] is True
    assert finalized["failure_persisted"]["occurrences"] == 2
    assert "reconoció un patrón de fallo existente" in finalized["agent_summary_text"]


def test_success_summary_reports_prior_failure_resolved_without_overclaiming(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    event = {
        "toolchain": "typescript",
        "phase": "typecheck",
        "message": "Type mismatch",
        "code": "TS2322",
        "file": "src/app.ts",
        "fingerprint": "typescript_typecheck_ts2322_src_app_ts_type_mismatch",
    }
    failed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix TS2322 type mismatch",
            "agent_id": "codex",
            "execution_id": "event-before-fix",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/app.ts"],
            "error_events": [event],
        }
    )
    finalize_execution(failed, {"success": False, "result_summary": "tsc failed", "validated_learning": False})
    fixed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix TS2322 type mismatch",
            "agent_id": "codex",
            "execution_id": "event-after-fix",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/app.ts"],
        }
    )

    finalized = finalize_execution(fixed, {"success": True, "result_summary": "fixed", "validated_learning": False})

    assert finalized["resolved_failures"]
    assert "typescript typecheck TS2322" in finalized["agent_summary"]["avoided"][0]
    assert "typescript typecheck TS2322" in finalized["agent_summary_text"]


def test_success_with_prior_failure_context_uses_descriptor_not_only_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    event = {
        "toolchain": "typescript",
        "phase": "typecheck",
        "message": "Type mismatch",
        "code": "TS2322",
        "file": "src/app.ts",
        "fingerprint": "typescript_typecheck_ts2322_src_app_ts_type_mismatch",
    }
    failed = prepare_execution(
        {
            "repo_root": str(repo),
            "user_request": "fix TS2322 type mismatch",
            "agent_id": "codex",
            "execution_id": "event-context-before",
            "declared_task_type": "bug_fixing",
            "files_opened": ["src/app.ts"],
            "error_events": [event],
        }
    )
    finalize_execution(failed, {"success": False, "result_summary": "tsc failed", "validated_learning": False})
    prepared = {
        "execution_hint": {},
        "continuity_context": {
            "loaded": {"failures": True},
            "failures": load_failures(repo),
            "continuity_brief": {},
        },
        "envelope": {"repo_root": str(repo), "user_request": "fix TS2322 type mismatch"},
        "last_execution_log": {
            "success": True,
            "files_opened": ["src/app.ts"],
            "files_edited": [],
            "files_reopened": [],
            "commands_executed": [],
            "tests_executed": [],
            "error_events": [],
            "area_id": "src",
            "task_type": "bug_fixing",
        },
    }

    summary = build_agent_summary(
        prepared,
        learning=None,
        strategy=None,
        failure=None,
        handoff=None,
        decisions=[],
        resolved_failures=[],
    )["structured"]

    assert "usó contexto de fallo previo sin repetirlo" in summary["avoided"][0]
    assert "typescript typecheck TS2322" in summary["avoided"][0]


def test_run_execution_json_captures_error_events_and_report_metrics(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    cli.prepare_repo_runtime(repo)
    parser = cli.build_parser()

    args = parser.parse_args(
        [
            "internal",
            "run-execution",
            "--repo",
            str(repo),
            "--request",
            "run failing tsc",
            "--agent-id",
            "codex",
            "--execution-id",
            "exec-tsc-fail",
            "--json",
            "--",
            "python3",
            "-c",
            "import sys; print('src/app.ts(4,7): error TS2322: Type mismatch', file=sys.stderr); sys.exit(1)",
        ]
    )

    assert args.func(args) == 1
    payload = json.loads(capsys.readouterr().out)
    log = payload["prepared"]["execution_observation"]
    assert log["error_events"][0]["toolchain"] == "typescript"
    assert payload["finalized"]["failure_persisted"]["failure_id"]

    report = build_real_usage_report(repo)
    assert report["error_capture"]["error_event_count"] >= 1
    assert "typescript" in report["error_capture"]["toolchains_seen"]
    assert report["error_capture"]["failure_patterns_with_error_events"] >= 1
