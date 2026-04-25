from __future__ import annotations

import ast
import importlib
import json
import re
from pathlib import Path
from types import ModuleType
from typing import Any, Iterable, Mapping

from .models import normalize_repomap_file_record, normalize_repomap_import, normalize_repomap_symbol
from .setup import REPO_MAP_IMPORT_NAME, REPO_MAP_PROVIDER

COMMON_LANGUAGE_BY_SUFFIX = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
}

SYMBOL_NODE_KINDS = {
    "class_declaration": "class",
    "class_definition": "class",
    "function_declaration": "function",
    "function_definition": "function",
    "method_definition": "function",
}


def _import_language_pack() -> ModuleType:
    return importlib.import_module(REPO_MAP_IMPORT_NAME)


def check_tree_sitter_available() -> dict[str, Any]:
    try:
        module = _import_language_pack()
    except ImportError:
        return {
            "available": False,
            "provider": REPO_MAP_PROVIDER,
            "version": "",
            "languages_count": 0,
            "error": "missing_dependency",
        }

    languages_count = 0
    if hasattr(module, "available_languages"):
        try:
            languages = module.available_languages()
            languages_count = len(languages) if hasattr(languages, "__len__") else 0
        except Exception:
            languages_count = 0
    return {
        "available": True,
        "provider": REPO_MAP_PROVIDER,
        "version": str(getattr(module, "__version__", "") or "unknown"),
        "languages_count": int(languages_count),
        "error": "",
    }


def extract_file_structure(path: Path, repo_root: Path, max_parse_file_bytes: int) -> dict[str, Any]:
    path = Path(path)
    repo_root = Path(repo_root)
    relative_path = _relative_path(path, repo_root)
    try:
        size_bytes = path.stat().st_size
    except OSError:
        return _metadata_only(relative_path, reason="read_error")

    if size_bytes > max_parse_file_bytes:
        return _metadata_only(relative_path, reason="file_too_large", size_bytes=size_bytes)

    try:
        source = path.read_bytes()
    except OSError:
        return _metadata_only(relative_path, reason="read_error", size_bytes=size_bytes)

    if _looks_binary(source):
        return _metadata_only(relative_path, reason="binary_file", size_bytes=size_bytes)

    availability = check_tree_sitter_available()
    if not availability.get("available"):
        return _metadata_only(relative_path, reason="provider_unavailable", size_bytes=size_bytes)

    try:
        module = _import_language_pack()
    except ImportError:
        return _metadata_only(relative_path, reason="provider_unavailable", size_bytes=size_bytes)

    language = _detect_special_language(path, source) or _detect_language(module, path)
    if not language:
        return _metadata_only(relative_path, reason="unsupported_language", size_bytes=size_bytes)

    metadata = _extract_lightweight_metadata(relative_path, language, source, size_bytes=size_bytes)
    if metadata is not None:
        return metadata

    processed = _try_process(module, path, source, language)
    if processed:
        return _normalize_processed(relative_path, language, processed, size_bytes=size_bytes)

    parsed = _try_tree_sitter_traversal(module, source, language)
    if parsed:
        return _normalize_processed(relative_path, language, parsed, size_bytes=size_bytes)

    if language == "python":
        static_python = _extract_python_static_metadata(relative_path, source, size_bytes=size_bytes)
        if static_python is not None:
            return static_python

    return _metadata_only(relative_path, language=language, reason="unsupported_extraction", size_bytes=size_bytes)


def _relative_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _metadata_only(path: str, *, language: str = "", reason: str, size_bytes: int = 0) -> dict[str, Any]:
    return normalize_repomap_file_record(
        {
            "path": path,
            "language": language,
            "symbols": [],
            "imports": [],
            "metadata_only": True,
            "provider": REPO_MAP_PROVIDER,
            "reason": reason,
            "size_bytes": size_bytes,
        }
    )


def _looks_binary(source: bytes) -> bool:
    return b"\x00" in source[:4096]


def _detect_language(module: ModuleType, path: Path) -> str:
    if hasattr(module, "detect_language"):
        try:
            detected = module.detect_language(path)
        except TypeError:
            try:
                detected = module.detect_language(str(path))
            except Exception:
                detected = ""
        except Exception:
            detected = ""
        if detected:
            return str(detected)
    return COMMON_LANGUAGE_BY_SUFFIX.get(path.suffix.lower(), "")


def _detect_special_language(path: Path, source: bytes) -> str:
    if path.name == "Makefile":
        return "makefile"
    first_line = source.splitlines()[0].decode("utf-8", errors="replace").lower() if source.splitlines() else ""
    if first_line.startswith("#!"):
        if "python" in first_line:
            return "python"
        if any(shell in first_line for shell in ("sh", "bash", "zsh")):
            return "shell"
    if path.suffix:
        return ""
    return ""


def _try_process(module: ModuleType, path: Path, source: bytes, language: str) -> Mapping[str, Any] | None:
    process = getattr(module, "process", None)
    if not callable(process):
        return None
    attempts = (
        lambda: process(path),
        lambda: process(str(path)),
        lambda: process(source.decode("utf-8", errors="replace"), language=language),
    )
    for attempt in attempts:
        try:
            result = attempt()
        except TypeError:
            continue
        except Exception:
            return None
        if isinstance(result, Mapping):
            return result
    return None


def _normalize_processed(path: str, language: str, payload: Mapping[str, Any], *, size_bytes: int) -> dict[str, Any]:
    symbols: list[dict[str, Any]] = []
    raw_symbols = payload.get("symbols", [])
    if isinstance(raw_symbols, list):
        symbols.extend(
            normalize_repomap_symbol(item, language=language)
            for item in raw_symbols
            if isinstance(item, Mapping)
        )
    for key, kind in (("functions", "function"), ("classes", "class")):
        items = payload.get(key, [])
        if isinstance(items, list):
            symbols.extend(_normalize_named_items(items, kind=kind, language=language))

    imports: list[dict[str, Any]] = []
    raw_imports = payload.get("imports", [])
    if isinstance(raw_imports, list):
        imports.extend(normalize_repomap_import(item) for item in raw_imports if isinstance(item, (Mapping, str)))

    return normalize_repomap_file_record(
        {
            "path": path,
            "language": language,
            "symbols": symbols,
            "imports": imports,
            "metadata_only": False,
            "provider": REPO_MAP_PROVIDER,
            "reason": "",
            "size_bytes": size_bytes,
        }
    )


def _normalize_named_items(items: Iterable[Any], *, kind: str, language: str) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(normalize_repomap_symbol({"name": item, "kind": kind}, language=language))
        elif isinstance(item, Mapping):
            payload = dict(item)
            payload.setdefault("kind", kind)
            normalized.append(normalize_repomap_symbol(payload, language=language))
    return normalized


def _extract_lightweight_metadata(path: str, language: str, source: bytes, *, size_bytes: int) -> dict[str, Any] | None:
    text = source.decode("utf-8", errors="replace")
    if language == "markdown":
        symbols = _markdown_heading_symbols(text)
    elif language in {"json", "toml", "yaml"}:
        symbols = _config_key_symbols(text, language)
    elif language in {"makefile", "shell"}:
        symbols = [_symbol(Path(path).name or path, "entrypoint", language, 1)]
    else:
        return None
    if not symbols:
        symbols = [_symbol(Path(path).name or path, "file", language, 1)]
    return _record_with_symbols(path, language, symbols, size_bytes=size_bytes)


def _extract_python_static_metadata(path: str, source: bytes, *, size_bytes: int) -> dict[str, Any] | None:
    text = source.decode("utf-8", errors="replace")
    try:
        module = ast.parse(text)
    except SyntaxError:
        return None
    symbols: list[dict[str, Any]] = []
    imports_added = 0
    constants_added = 0
    for node in module.body:
        if imports_added < 8 and isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in _import_names(node):
                symbols.append(_symbol(name, "import", "python", int(getattr(node, "lineno", 0) or 0)))
                imports_added += 1
                if imports_added >= 8:
                    break
        elif constants_added < 8 and isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    symbols.append(_symbol(target.id, "constant", "python", int(getattr(node, "lineno", 0) or 0)))
                    constants_added += 1
                if constants_added >= 8:
                    break
        elif constants_added < 8 and isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id.isupper():
            symbols.append(_symbol(node.target.id, "constant", "python", int(getattr(node, "lineno", 0) or 0)))
            constants_added += 1
    if not symbols:
        kind = "entrypoint" if Path(path).name in {"__main__.py", "cli.py"} else "module"
        symbols.append(_symbol(Path(path).stem or path, kind, "python", 1))
    return _record_with_symbols(path, "python", symbols, size_bytes=size_bytes)


def _import_names(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Import):
        return [alias.asname or alias.name for alias in node.names[:8]]
    if isinstance(node, ast.ImportFrom):
        module = "." * int(node.level or 0) + str(node.module or "")
        return [f"{module}.{alias.asname or alias.name}".strip(".") for alias in node.names[:8]]
    return []


def _markdown_heading_symbols(text: str) -> list[dict[str, Any]]:
    symbols: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        match = re.match(r"^(#{1,3})\s+(.+?)\s*$", line)
        if match:
            title = match.group(2).strip().strip("#").strip()
            if title:
                symbols.append(_symbol(title, "heading", "markdown", line_no))
        if len(symbols) >= 6:
            break
    return symbols


def _config_key_symbols(text: str, language: str) -> list[dict[str, Any]]:
    if language == "json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            return [_symbol(str(key), "config_key", language, 1) for key in list(payload)[:8]]
        return []
    symbols: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", "---")):
            continue
        if language == "toml":
            section = re.match(r"^\[([A-Za-z0-9_.-]+)\]$", stripped)
            key = re.match(r"^([A-Za-z0-9_.-]+)\s*=", stripped)
            name = section.group(1) if section else key.group(1) if key else ""
        else:
            key = re.match(r"^([A-Za-z0-9_.-]+):", stripped)
            name = key.group(1) if key else ""
        if name:
            symbols.append(_symbol(name, "config_key", language, line_no))
        if len(symbols) >= 8:
            break
    return symbols


def _record_with_symbols(path: str, language: str, symbols: list[dict[str, Any]], *, size_bytes: int) -> dict[str, Any]:
    return normalize_repomap_file_record(
        {
            "path": path,
            "language": language,
            "symbols": symbols,
            "imports": [],
            "metadata_only": False,
            "provider": REPO_MAP_PROVIDER,
            "reason": "",
            "size_bytes": size_bytes,
        }
    )


def _symbol(name: str, kind: str, language: str, line: int) -> dict[str, Any]:
    return normalize_repomap_symbol(
        {
            "name": name,
            "kind": kind,
            "line": line,
            "end_line": line,
            "language": language,
        },
        language=language,
    )


def _try_tree_sitter_traversal(module: ModuleType, source: bytes, language: str) -> Mapping[str, Any] | None:
    get_parser = getattr(module, "get_parser", None)
    if not callable(get_parser):
        return None
    try:
        parser = get_parser(language)
        tree = parser.parse(source)
        root = tree.root_node
    except Exception:
        return None
    symbols: list[dict[str, Any]] = []
    _walk_tree(root, language, symbols)
    if not symbols:
        return None
    return {"symbols": symbols, "imports": []}


def _walk_tree(node: Any, language: str, symbols: list[dict[str, Any]]) -> None:
    node_type = str(getattr(node, "type", "") or "")
    if node_type in SYMBOL_NODE_KINDS:
        name = _node_name(node)
        if name:
            start = getattr(node, "start_point", (0, 0))
            end = getattr(node, "end_point", start)
            symbols.append(
                {
                    "name": name,
                    "kind": SYMBOL_NODE_KINDS[node_type],
                    "line": int(start[0]) + 1 if isinstance(start, tuple) and start else 0,
                    "end_line": int(end[0]) + 1 if isinstance(end, tuple) and end else 0,
                    "language": language,
                }
            )
    for child in getattr(node, "children", []) or []:
        _walk_tree(child, language, symbols)


def _node_name(node: Any) -> str:
    child = None
    child_by_field_name = getattr(node, "child_by_field_name", None)
    if callable(child_by_field_name):
        try:
            child = child_by_field_name("name")
        except Exception:
            child = None
    if child is None:
        return ""
    text = getattr(child, "text", b"")
    if isinstance(text, bytes):
        return text.decode("utf-8", errors="replace")
    return str(text or "")
