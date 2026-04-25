from __future__ import annotations

import json
from pathlib import Path

from aictx import cli


def test_map_parser_includes_status_refresh_query():
    parser = cli.build_parser()
    status_args = parser.parse_args(["map", "status", "--repo", "."])
    refresh_args = parser.parse_args(["map", "refresh", "--repo", ".", "--full"])
    query_args = parser.parse_args(["map", "query", "--repo", ".", "startup banner"])

    assert status_args.command == "map"
    assert status_args.map_command == "status"
    assert status_args.func == cli.cmd_map_status

    assert refresh_args.command == "map"
    assert refresh_args.map_command == "refresh"
    assert refresh_args.func == cli.cmd_map_refresh

    assert query_args.command == "map"
    assert query_args.map_command == "query"
    assert query_args.func == cli.cmd_map_query


def test_map_status_works_when_no_map_exists(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()

    parser = cli.build_parser()
    args = parser.parse_args(["map", "status", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "enabled": False,
        "available": False,
        "provider": "tree_sitter",
        "files_indexed": 0,
        "symbols_indexed": 0,
        "last_refresh_status": "never",
    }


def test_map_query_no_index_returns_empty_list(tmp_path: Path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()

    parser = cli.build_parser()
    args = parser.parse_args(["map", "query", "--repo", str(repo), "startup banner", "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload == []


def test_map_refresh_json_output_is_valid(tmp_path: Path, capsys, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()

    monkeypatch.setattr(cli, "refresh_repo_map", lambda repo_root, mode="full": {"status": "ok", "mode": "full", "files_indexed": 2, "symbols_indexed": 5})

    parser = cli.build_parser()
    args = parser.parse_args(["map", "refresh", "--repo", str(repo), "--json"])
    assert args.func(args) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["requested_mode"] == "incremental"
    assert payload["executed_mode"] == "full"
    assert payload["status"] == "ok"
