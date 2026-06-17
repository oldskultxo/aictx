from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import aictx.repo_map.tree_sitter_provider as tree_sitter_provider


def test_tree_sitter_provider_missing_returns_unavailable(monkeypatch):
    def missing():
        raise ImportError("missing")

    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", missing)

    assert tree_sitter_provider.check_tree_sitter_available() == {
        "available": False,
        "provider": "tree_sitter",
        "version": "",
        "languages_count": 0,
        "error": "missing_dependency",
    }


def test_large_file_returns_metadata_only_without_provider_import(tmp_path: Path, monkeypatch):
    source = tmp_path / "large.py"
    source.write_text("x" * 20, encoding="utf-8")

    def should_not_import():
        raise AssertionError("provider should not be imported for oversized files")

    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", should_not_import)

    record = tree_sitter_provider.extract_file_structure(source, tmp_path, max_parse_file_bytes=5)
    assert record["metadata_only"] is True
    assert record["reason"] == "file_too_large"
    assert record["path"] == "large.py"
    assert record["symbols"] == []


def test_binary_file_returns_metadata_only_without_provider_import(tmp_path: Path, monkeypatch):
    source = tmp_path / "binary.py"
    source.write_bytes(b"\x00\x01\x02")

    def should_not_import():
        raise AssertionError("provider should not be imported for binary-looking files")

    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", should_not_import)

    record = tree_sitter_provider.extract_file_structure(source, tmp_path, max_parse_file_bytes=100)
    assert record["metadata_only"] is True
    assert record["reason"] == "binary_file"
    assert record["path"] == "binary.py"


def test_fake_provider_process_output_is_normalized(tmp_path: Path, monkeypatch):
    source = tmp_path / "sample.py"
    source.write_text("class Thing:\n    def run(self):\n        pass\n", encoding="utf-8")

    fake_module = SimpleNamespace(
        __version__="1.2.3",
        available_languages=lambda: ["python", "javascript"],
        detect_language=lambda path: "python",
        process=lambda path: {
            "functions": [{"name": "run", "line": 2, "end_line": 3}],
            "classes": [{"name": "Thing", "line": 1, "end_line": 3}],
            "imports": [{"module": "os", "symbol": "path", "alias": "osp"}],
        },
    )
    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", lambda: fake_module)

    availability = tree_sitter_provider.check_tree_sitter_available()
    assert availability == {
        "available": True,
        "provider": "tree_sitter",
        "version": "1.2.3",
        "languages_count": 2,
        "error": "",
    }

    record = tree_sitter_provider.extract_file_structure(source, tmp_path, max_parse_file_bytes=10_000)
    assert record["metadata_only"] is False
    assert record["provider"] == "tree_sitter"
    assert record["language"] == "python"
    assert record["path"] == "sample.py"
    assert record["imports"] == [{"module": "os", "symbol": "path", "alias": "osp"}]
    assert {symbol["name"]: symbol["kind"] for symbol in record["symbols"]} == {
        "run": "function",
        "Thing": "class",
    }


def test_python_static_metadata_adds_imports_constants_and_module_pseudosymbol(tmp_path: Path, monkeypatch):
    source = tmp_path / "config.py"
    source.write_text("import os\nfrom pathlib import Path\nMAX_SIZE = 10\nvalue = 1\n", encoding="utf-8")
    fake_module = SimpleNamespace(__version__="x", available_languages=lambda: ["python"], detect_language=lambda path: "python")
    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", lambda: fake_module)

    record = tree_sitter_provider.extract_file_structure(source, tmp_path, max_parse_file_bytes=10_000)

    assert record["metadata_only"] is False
    assert record["reason"] == ""
    symbols = {symbol["name"]: symbol["kind"] for symbol in record["symbols"]}
    assert symbols["os"] == "import"
    assert symbols["pathlib.Path"] == "import"
    assert symbols["MAX_SIZE"] == "constant"
    assert "value" not in symbols


def test_python_without_static_signals_gets_module_or_entrypoint_pseudosymbol(tmp_path: Path, monkeypatch):
    module_file = tmp_path / "__main__.py"
    module_file.write_text("\"\"\"entrypoint only\"\"\"\n", encoding="utf-8")
    fake_module = SimpleNamespace(__version__="x", available_languages=lambda: ["python"], detect_language=lambda path: "python")
    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", lambda: fake_module)

    record = tree_sitter_provider.extract_file_structure(module_file, tmp_path, max_parse_file_bytes=10_000)

    assert record["metadata_only"] is False
    assert record["symbols"] == [{"name": "__main__", "kind": "entrypoint", "line": 1, "end_line": 1, "language": "python"}]


def test_markdown_config_makefile_and_shebang_use_explicit_low_noise_kinds(tmp_path: Path, monkeypatch):
    fake_module = SimpleNamespace(__version__="x", available_languages=lambda: ["python"], detect_language=lambda path: "")
    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", lambda: fake_module)
    readme = tmp_path / "README.md"
    readme.write_text("# Title\n\n## Setup\n\n#### ignored deep heading\n", encoding="utf-8")
    config = tmp_path / "settings.json"
    config.write_text('{"alpha": 1, "beta": 2}', encoding="utf-8")
    makefile = tmp_path / "Makefile"
    makefile.write_text("test:\n\tpytest\n", encoding="utf-8")
    script = tmp_path / "ctx-tool"
    script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")
    legacy_script = tmp_path / "legacy.py"
    legacy_script.write_text("#!/usr/bin/env bash\necho ok\n", encoding="utf-8")

    assert {symbol["kind"] for symbol in tree_sitter_provider.extract_file_structure(readme, tmp_path, 10_000)["symbols"]} == {"heading"}
    assert {symbol["name"]: symbol["kind"] for symbol in tree_sitter_provider.extract_file_structure(config, tmp_path, 10_000)["symbols"]} == {"alpha": "config_key", "beta": "config_key"}
    assert tree_sitter_provider.extract_file_structure(makefile, tmp_path, 10_000)["symbols"][0]["kind"] == "entrypoint"
    assert tree_sitter_provider.extract_file_structure(script, tmp_path, 10_000)["symbols"][0]["kind"] == "entrypoint"
    legacy_record = tree_sitter_provider.extract_file_structure(legacy_script, tmp_path, 10_000)
    assert legacy_record["language"] == "bash"
    assert legacy_record["symbols"][0]["kind"] == "entrypoint"


def test_ruby_suffix_special_filenames_and_symbols_are_indexed(tmp_path: Path, monkeypatch):
    class FakeName:
        text = b""

        def __init__(self, text: bytes):
            self.text = text

    class FakeNode:
        def __init__(self, node_type, name=b"", row=0, end_row=None, children=None):
            self.type = node_type
            self._name = FakeName(name) if name else None
            self.start_point = SimpleNamespace(row=row)
            self.end_point = SimpleNamespace(row=row if end_row is None else end_row)
            self.children = children or []

        def child_by_field_name(self, field):
            return self._name if field == "name" else None

    class FakeParser:
        def parse(self, source):
            return SimpleNamespace(
                root_node=FakeNode(
                    "program",
                    children=[
                        FakeNode("module", b"ScheduledCaptures", row=0, end_row=5),
                        FakeNode("class", b"OperationalSnapshot", row=1, end_row=4),
                        FakeNode("singleton_method", b"call", row=2),
                        FakeNode("method", b"run", row=3),
                    ],
                )
            )

    fake_module = SimpleNamespace(
        __version__="x",
        get_parser=lambda language: FakeParser(),
    )
    monkeypatch.setattr(tree_sitter_provider, "_import_language_pack", lambda: fake_module)

    ruby_file = tmp_path / "operational_snapshot.rb"
    ruby_file.write_text("module ScheduledCaptures\nend\n", encoding="utf-8")
    gemfile = tmp_path / "Gemfile"
    gemfile.write_text("source 'https://rubygems.org'\n", encoding="utf-8")

    ruby_record = tree_sitter_provider.extract_file_structure(ruby_file, tmp_path, max_parse_file_bytes=10_000)
    assert ruby_record["metadata_only"] is False
    assert ruby_record["reason"] == ""
    assert ruby_record["language"] == "ruby"
    assert {symbol["name"]: symbol["kind"] for symbol in ruby_record["symbols"]} == {
        "ScheduledCaptures": "module",
        "OperationalSnapshot": "class",
        "call": "function",
        "run": "function",
    }
    assert ruby_record["symbols"][0]["line"] == 1

    assert tree_sitter_provider.extract_file_structure(gemfile, tmp_path, 10_000)["language"] == "ruby"


def test_extended_language_suffixes_are_detected_without_provider_detection():
    fake_module = SimpleNamespace(__version__="x")

    assert tree_sitter_provider._detect_language(fake_module, Path("lib/task.rake")) == "ruby"
    assert tree_sitter_provider._detect_language(fake_module, Path("main.rs")) == "rust"
    assert tree_sitter_provider._detect_language(fake_module, Path("main.tf")) == "terraform"
    assert tree_sitter_provider._detect_language(fake_module, Path("component.vue")) == "vue"
