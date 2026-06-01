from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


def _guard_main(argv: Sequence[str]) -> int:
    from .continuity_guard import GUARD_ACTIONS, GUARD_RISKS, build_continuity_guard

    parser = argparse.ArgumentParser(prog="aictx guard")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--action", choices=sorted(GUARD_ACTIONS), required=True, help="Action boundary to check")
    parser.add_argument("--paths", action="append", default=[], help="Path involved in the action; may be repeated")
    parser.add_argument("--command", default="", help="Command involved in the action")
    parser.add_argument("--intent", default="", help="Short intent for the action")
    parser.add_argument("--risk", choices=sorted(GUARD_RISKS), default="normal", help="Risk level")
    parser.add_argument("--agent-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--session-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Print compact guard JSON")
    args = parser.parse_args(list(argv))
    payload = build_continuity_guard(
        Path(args.repo or ".").expanduser().resolve(),
        action=str(args.action or ""),
        paths=list(args.paths or []),
        command=str(args.command or ""),
        intent=str(args.intent or ""),
        risk=str(args.risk or "normal"),
        agent_id=str(args.agent_id or ""),
        session_id=str(args.session_id or ""),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"AICTX guard: {payload['decision']} ({payload['status']})")
        for item in payload.get("warnings", []):
            print(f"- {item.get('code')}: {item.get('message')}")
        print(f"next: {payload['suggested_next']}")
    return 0


def _steer_main(argv: Sequence[str]) -> int:
    from .steer_guard import STEER_CURRENT_ACTIONS, build_steer_guard

    parser = argparse.ArgumentParser(prog="aictx steer")
    parser.add_argument("--repo", default=".", help="Repository root")
    parser.add_argument("--message", required=True, help="User message to classify")
    parser.add_argument("--current-action", choices=sorted(STEER_CURRENT_ACTIONS), default="unknown", help="Current agent action")
    parser.add_argument("--paths", action="append", default=[], help="Path involved in the current action; may be repeated")
    parser.add_argument("--agent-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--session-id", default="", help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="Print compact steer JSON")
    args = parser.parse_args(list(argv))
    payload = build_steer_guard(
        Path(args.repo or ".").expanduser().resolve(),
        message=str(args.message or ""),
        current_action=str(args.current_action or "unknown"),
        paths=list(args.paths or []),
        agent_id=str(args.agent_id or ""),
        session_id=str(args.session_id or ""),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"AICTX steer: {payload['classification']} -> {payload['decision']} ({payload['status']})")
        print(payload["summary"])
        print(f"next: {payload['agent_instruction']}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "guard":
        return _guard_main(args[1:])
    if args and args[0] == "steer":
        return _steer_main(args[1:])
    from .cli import main as cli_main

    if argv is None:
        return cli_main()
    old_argv = sys.argv[:]
    try:
        sys.argv = [old_argv[0], *args]
        return cli_main()
    finally:
        sys.argv = old_argv
