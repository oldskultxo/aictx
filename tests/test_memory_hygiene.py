from __future__ import annotations

import json
from pathlib import Path

from aictx.continuity import DECISIONS_PATH, DEDUPE_REPORT_PATH, HANDOFF_PATH, SEMANTIC_REPO_PATH, maintain_continuity_hygiene
from aictx.failure_memory import FAILURE_PATTERNS_PATH
from aictx.scaffold import init_repo_scaffold
from aictx.state import read_jsonl


def test_memory_hygiene_dedupes_exact_decisions_only(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    decisions_path = repo / DECISIONS_PATH
    decisions_path.parent.mkdir(parents=True, exist_ok=True)
    exact = {
        "decision": "Use decisions.jsonl",
        "rationale": "Keep continuity inspectable.",
        "alternatives": ["inline json"],
        "constraints": ["deterministic"],
        "risks": [],
        "related_paths": [".aictx/continuity/decisions.jsonl"],
        "subsystem": "continuity_runtime",
    }
    distinct = dict(exact)
    distinct["rationale"] = "Different rationale should survive."
    decisions_path.write_text(
        "\n".join(json.dumps(item) for item in [exact, exact, distinct]) + "\n",
        encoding="utf-8",
    )

    result = maintain_continuity_hygiene(repo)
    rows = read_jsonl(decisions_path)

    assert len(rows) == 2
    assert rows[0]["rationale"] == "Keep continuity inspectable."
    assert rows[1]["rationale"] == "Different rationale should survive."
    assert result["report"]["decisions"]["duplicates_removed"] == 1


def test_memory_hygiene_merges_failures_only_by_same_signature(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    failure_path = repo / FAILURE_PATTERNS_PATH
    failure_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "failure_id": "failure::same-a",
            "signature": "same-signature",
            "failure_signature": "same-signature",
            "status": "open",
            "timestamp": "2026-04-24T00:00:00Z",
            "occurrences": 1,
            "symptoms": ["timeout"],
            "ineffective_commands": ["pytest tests/test_a.py"],
            "related_paths": ["src/a.py"],
        },
        {
            "failure_id": "failure::same-b",
            "signature": "same-signature",
            "failure_signature": "same-signature",
            "status": "open",
            "timestamp": "2026-04-24T00:01:00Z",
            "occurrences": 2,
            "symptoms": ["timeout"],
            "ineffective_commands": ["pytest tests/test_a.py", "pytest tests/test_b.py"],
            "related_paths": ["src/a.py", "src/b.py"],
        },
        {
            "failure_id": "failure::different",
            "signature": "different-signature",
            "failure_signature": "different-signature",
            "status": "open",
            "timestamp": "2026-04-24T00:02:00Z",
            "occurrences": 1,
            "symptoms": ["assertion"],
            "ineffective_commands": ["pytest tests/test_c.py"],
            "related_paths": ["src/c.py"],
        },
    ]
    failure_path.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")

    result = maintain_continuity_hygiene(repo)
    merged = read_jsonl(failure_path)

    assert len(merged) == 2
    same = next(row for row in merged if row.get("failure_signature") == "same-signature")
    assert same["occurrences"] == 3
    assert same["ineffective_commands"] == ["pytest tests/test_a.py", "pytest tests/test_b.py"]
    assert same["related_paths"] == ["src/a.py", "src/b.py"]
    assert result["report"]["failure_patterns"]["merged_groups"] == 1
    assert result["report"]["failure_patterns"]["duplicates_removed"] == 1


def test_memory_hygiene_dedupes_semantic_repo_strings_and_writes_report(tmp_path: Path):
    repo = tmp_path / "repo"
    init_repo_scaffold(repo, update_gitignore=False)
    (repo / HANDOFF_PATH).write_text(json.dumps({"summary": "latest canonical"}), encoding="utf-8")
    semantic_path = repo / SEMANTIC_REPO_PATH
    semantic_path.write_text(
        json.dumps({
            "repo_id": "repo",
            "subsystems": [{
                "name": "continuity_runtime",
                "description": "Continuity.",
                "key_paths": ["src/a.py", "src/a.py", "src/b.py"],
                "entry_points": ["load_continuity_context", "load_continuity_context"],
                "relevant_tests": ["tests/test_a.py", "tests/test_a.py"],
                "fragile_areas": ["startup", "startup"],
            }],
        }),
        encoding="utf-8",
    )

    result = maintain_continuity_hygiene(repo)
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    report = json.loads((repo / DEDUPE_REPORT_PATH).read_text(encoding="utf-8"))

    subsystem = semantic["subsystems"][0]
    assert subsystem["key_paths"] == ["src/a.py", "src/b.py"]
    assert subsystem["entry_points"] == ["load_continuity_context"]
    assert subsystem["relevant_tests"] == ["tests/test_a.py"]
    assert subsystem["fragile_areas"] == ["startup"]
    assert report == result["report"]
    assert report["handoff"]["canonical"] is True
    assert report["semantic_repo"]["strings_deduped"] == 4
