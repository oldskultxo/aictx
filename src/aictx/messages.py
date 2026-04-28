from __future__ import annotations

from pathlib import Path
from typing import Any

from .state import REPO_MEMORY_DIR, read_json, write_json

MESSAGE_MODE_MUTED = "muted"
MESSAGE_MODE_UNMUTED = "unmuted"
VALID_MESSAGE_MODES = {MESSAGE_MODE_MUTED, MESSAGE_MODE_UNMUTED}


def user_preferences_path(repo: Path) -> Path:
    return repo / REPO_MEMORY_DIR / "user_preferences.json"


def normalize_message_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode in VALID_MESSAGE_MODES:
        return mode
    return MESSAGE_MODE_UNMUTED


def get_message_mode(repo: Path) -> str:
    prefs = read_json(user_preferences_path(repo), {})
    messages = prefs.get("messages", {}) if isinstance(prefs.get("messages"), dict) else {}
    return normalize_message_mode(messages.get("mode"))


def messages_muted(repo: Path) -> bool:
    return get_message_mode(repo) == MESSAGE_MODE_MUTED


def set_message_mode(repo: Path, mode: str) -> dict[str, Any]:
    normalized = normalize_message_mode(mode)
    path = user_preferences_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    prefs = read_json(path, {})
    messages = prefs.get("messages", {}) if isinstance(prefs.get("messages"), dict) else {}
    messages["mode"] = normalized
    prefs["messages"] = messages
    write_json(path, prefs)
    return {"messages": {"mode": normalized}}
