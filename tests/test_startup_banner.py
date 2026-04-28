from __future__ import annotations

from pathlib import Path

from aictx.continuity import AICTX_TEXT_SEPARATOR, append_aictx_text_separator, render_startup_banner


def test_append_aictx_text_separator_is_idempotent() -> None:
    first = append_aictx_text_separator("hello")
    second = append_aictx_text_separator(first)

    assert first == second
    assert first == f"hello\n\n{AICTX_TEXT_SEPARATOR}\n\n"


def test_append_aictx_text_separator_empty_input() -> None:
    assert append_aictx_text_separator("") == ""


def test_render_startup_banner_appends_separator_block(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    banner = render_startup_banner({"session": {"agent_label": "codex@repo", "session_count": 2}}, repo)

    assert banner.rstrip().endswith(AICTX_TEXT_SEPARATOR)
    assert banner.count(AICTX_TEXT_SEPARATOR) == 1
    assert f"\n\n{AICTX_TEXT_SEPARATOR}\n\n" in banner
