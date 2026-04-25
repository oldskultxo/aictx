from __future__ import annotations

import argparse
import tomllib
from pathlib import Path

import aictx.cli as cli
from aictx.repo_map.setup import REPO_MAP_PACKAGE_SPEC


ROOT = Path(__file__).resolve().parents[1]


def _install_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    payload = {
        "workspace_id": "default",
        "workspace_root": None,
        "cross_project_mode": "workspace",
        "install_codex_global": False,
        "with_repomap": False,
        "dry_run": False,
        "yes": True,
    }
    payload.update(overrides)
    return argparse.Namespace(**payload)


def test_repomap_optional_dependency_matches_runtime_install_spec():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["project"]["optional-dependencies"]["repomap"] == [REPO_MAP_PACKAGE_SPEC]
    assert REPO_MAP_PACKAGE_SPEC == "tree-sitter-language-pack>=0.13.0,<1.0.0"


def test_interactive_install_asks_whether_to_enable_repomap(tmp_path: Path, monkeypatch, capsys):
    prompts: list[tuple[str, bool]] = []

    monkeypatch.setattr(cli, "ask_text", lambda _prompt, default="": default)
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")

    def fake_ask_yes_no(prompt: str, default: bool = True) -> bool:
        prompts.append((prompt, default))
        if prompt == "Enable RepoMap support using Tree-sitter?":
            return False
        return False

    monkeypatch.setattr(cli, "ask_yes_no", fake_ask_yes_no)

    assert cli.cmd_install(_install_args(tmp_path, yes=False)) == 0
    assert ("Enable RepoMap support using Tree-sitter?", False) in prompts
    assert "RepoMap support: disabled." in capsys.readouterr().out


def test_install_interactive_no_does_not_request_or_install_repomap(tmp_path: Path, monkeypatch):
    writes: list[tuple[Path, dict]] = []
    install_attempted = {"value": False}

    monkeypatch.setattr(cli, "ask_text", lambda _prompt, default="": default)
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    monkeypatch.setattr(cli, "ask_yes_no", lambda prompt, default=True: False)
    monkeypatch.setattr(cli, "repomap_dependency_available", lambda: False)

    def fake_install_repomap_dependency():
        install_attempted["value"] = True
        raise AssertionError("should not attempt RepoMap dependency install")

    monkeypatch.setattr(cli, "install_repomap_dependency", fake_install_repomap_dependency)
    monkeypatch.setattr(cli, "write_json", lambda path, payload: writes.append((path, payload)))

    assert cli.cmd_install(_install_args(tmp_path, yes=False)) == 0
    config_payload = next(payload for path, payload in writes if path.name == "config.json")
    assert "repomap" not in config_payload
    assert install_attempted["value"] is False


def test_install_interactive_yes_requests_repomap_and_attempts_dependency_flow(tmp_path: Path, monkeypatch, capsys):
    writes: list[tuple[Path, dict]] = []
    install_attempted = {"value": False}
    prompts: list[str] = []
    availability = iter([False, True])

    monkeypatch.setattr(cli, "ask_text", lambda _prompt, default="": default)
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")

    def fake_ask_yes_no(prompt: str, default: bool = True) -> bool:
        prompts.append(prompt)
        if prompt == "Enable RepoMap support using Tree-sitter?":
            return True
        if prompt == "RepoMap needs the optional Tree-sitter dependency. Install it now?":
            return True
        return False

    monkeypatch.setattr(cli, "ask_yes_no", fake_ask_yes_no)
    monkeypatch.setattr(cli, "repomap_dependency_available", lambda: next(availability))

    class Result:
        returncode = 0

    def fake_install_repomap_dependency():
        install_attempted["value"] = True
        return Result()

    monkeypatch.setattr(cli, "install_repomap_dependency", fake_install_repomap_dependency)
    monkeypatch.setattr(cli, "write_json", lambda path, payload: writes.append((path, payload)))

    assert cli.cmd_install(_install_args(tmp_path, yes=False)) == 0
    config_payload = next(payload for path, payload in writes if path.name == "config.json")
    assert config_payload["repomap"] == {"requested": True, "provider": "tree_sitter", "available": True}
    assert install_attempted["value"] is True
    assert "RepoMap support: enabled" in capsys.readouterr().out
    assert "RepoMap needs the optional Tree-sitter dependency. Install it now?" in prompts


def test_install_yes_without_with_repomap_keeps_safe_default(tmp_path: Path, monkeypatch):
    writes: list[tuple[Path, dict]] = []
    install_attempted = {"value": False}

    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    monkeypatch.setattr(cli, "write_json", lambda path, payload: writes.append((path, payload)))
    monkeypatch.setattr(cli, "repomap_dependency_available", lambda: False)

    def fake_install_repomap_dependency():
        install_attempted["value"] = True
        raise AssertionError("should not install RepoMap without --with-repomap")

    monkeypatch.setattr(cli, "install_repomap_dependency", fake_install_repomap_dependency)

    assert cli.cmd_install(_install_args(tmp_path, yes=True, with_repomap=False)) == 0
    config_payload = next(payload for path, payload in writes if path.name == "config.json")
    assert "repomap" not in config_payload
    assert install_attempted["value"] is False


def test_install_with_repomap_yes_handles_missing_dependency_gracefully(tmp_path: Path, monkeypatch, capsys):
    writes: list[tuple[Path, dict]] = []
    install_attempted = {"value": False}

    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")
    monkeypatch.setattr(cli, "write_json", lambda path, payload: writes.append((path, payload)))
    monkeypatch.setattr(cli, "repomap_dependency_available", lambda: False)

    class Result:
        returncode = 1

    def fake_install_repomap_dependency():
        install_attempted["value"] = True
        return Result()

    monkeypatch.setattr(cli, "install_repomap_dependency", fake_install_repomap_dependency)

    assert cli.cmd_install(_install_args(tmp_path, yes=True, with_repomap=True)) == 0
    config_payload = next(payload for path, payload in writes if path.name == "config.json")
    assert config_payload["repomap"] == {"requested": True, "provider": "tree_sitter", "available": False}
    assert install_attempted["value"] is True
    out = capsys.readouterr().out
    assert "RepoMap unavailable." in out
    assert "RepoMap support: requested but unavailable." in out


def test_existing_install_behavior_still_passes_with_repomap_disabled(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "ensure_global_home", lambda: None)
    monkeypatch.setattr(cli, "install_global_agent_runtime", lambda _write_json: [])
    monkeypatch.setattr(cli, "install_global_adapters", lambda: [])
    monkeypatch.setattr(cli, "write_json", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "read_json", lambda _path, default: default)
    monkeypatch.setattr(cli, "workspace_path", lambda wid: tmp_path / f"{wid}.json")

    assert cli.cmd_install(_install_args(tmp_path, yes=True, with_repomap=False)) == 0
    out = capsys.readouterr().out
    assert "Skipped global Codex integration" in out
    assert "RepoMap support: disabled." in out
    assert "Install complete. Next: run `aictx init` inside a repository." in out
