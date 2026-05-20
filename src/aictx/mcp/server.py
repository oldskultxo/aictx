from __future__ import annotations

import argparse
import json
import sys
from typing import Any, BinaryIO

from .._version import __version__
from ..integrations.mcp_config import DEFAULT_MCP_PROFILE, normalize_mcp_profile
from .permissions import allowed_tools
from .prompts import get_prompt, list_prompts
from .resources import list_resources, resource_content
from .tools import call_tool, error, tool_specs

SUPPORTED_PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26", "2024-11-05")
DEFAULT_PROTOCOL_VERSION = SUPPORTED_PROTOCOL_VERSIONS[0]


def _read_message(stream: BinaryIO) -> dict[str, Any] | None:
    first = stream.readline()
    if not first:
        return None
    if first.lower().startswith(b"content-length:"):
        length = int(first.split(b":", 1)[1].strip())
        while True:
            line = stream.readline()
            if line in {b"\r\n", b"\n", b""}:
                break
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1].strip())
        raw = stream.read(length)
    else:
        raw = first
    if not raw.strip():
        return None
    return json.loads(raw.decode("utf-8"))


def _write_message(stream: BinaryIO, payload: dict[str, Any], *, headers: bool = False) -> None:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if headers:
        stream.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("ascii") + raw)
    else:
        stream.write(raw + b"\n")
    stream.flush()


def _result(req: dict[str, Any], result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req.get("id"), "result": result}


def _error_response(req: dict[str, Any], code: int, message: str, data: Any = None) -> dict[str, Any]:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req.get("id"), "error": err}


def handle_request(req: dict[str, Any], *, repo: str, profile: str) -> dict[str, Any] | None:
    method = str(req.get("method") or "")
    params = req.get("params") if isinstance(req.get("params"), dict) else {}
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        requested_protocol = str(params.get("protocolVersion") or "")
        protocol_version = requested_protocol if requested_protocol in SUPPORTED_PROTOCOL_VERSIONS else DEFAULT_PROTOCOL_VERSION
        return _result(req, {"protocolVersion": protocol_version, "serverInfo": {"name": "aictx", "version": __version__}, "capabilities": {"tools": {}, "resources": {}, "prompts": {}}})
    if method == "tools/list":
        return _result(req, {"tools": tool_specs(allowed_tools(profile))})
    if method == "tools/call":
        name = str(params.get("name") or "")
        args = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
        args.setdefault("repo", repo)
        known = {tool["name"] for tool in tool_specs()}
        if name not in known:
            payload = call_tool(name, args)
        elif name not in allowed_tools(profile):
            payload = error("permission_denied", f"Tool not allowed by {profile} profile", {"tool": name, "profile": profile})
        else:
            payload = call_tool(name, args)
        return _result(req, {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}], "structuredContent": payload, "isError": not bool(payload.get("ok", False))})
    if method == "resources/list":
        return _result(req, {"resources": list_resources()})
    if method == "resources/read":
        try:
            return _result(req, resource_content(str(params.get("uri") or ""), repo))
        except KeyError:
            return _error_response(req, -32602, "Unknown resource")
    if method == "prompts/list":
        return _result(req, {"prompts": list_prompts()})
    if method == "prompts/get":
        try:
            return _result(req, get_prompt(str(params.get("name") or "")))
        except KeyError:
            return _error_response(req, -32602, "Unknown prompt")
    return _error_response(req, -32601, f"Method not found: {method}")


def serve_stdio(*, repo: str = ".", profile: str = DEFAULT_MCP_PROFILE) -> int:
    profile = normalize_mcp_profile(profile)
    while True:
        try:
            req = _read_message(sys.stdin.buffer)
        except Exception as exc:
            _write_message(sys.stdout.buffer, {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}})
            continue
        if req is None:
            return 0
        if not isinstance(req, dict):
            _write_message(sys.stdout.buffer, {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid Request"}})
            continue
        response = handle_request(req, repo=repo, profile=profile)
        if response is not None and "id" in req:
            _write_message(sys.stdout.buffer, response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="aictx mcp-server")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--profile", choices=["readonly", "standard", "full"], default=DEFAULT_MCP_PROFILE)
    args = parser.parse_args(argv)
    return serve_stdio(repo=args.repo, profile=args.profile)
