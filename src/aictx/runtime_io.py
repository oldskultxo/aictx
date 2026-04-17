from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

MTIME_TOLERANCE_SECONDS = 0.5


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = '\n'.join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text((payload + '\n') if payload else '', encoding='utf-8')


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')


def slugify(text: str) -> str:
    ascii_text = text.lower()
    ascii_text = re.sub(r'[^a-z0-9]+', '_', ascii_text)
    ascii_text = re.sub(r'_+', '_', ascii_text).strip('_')
    return ascii_text or 'item'


def relative_posix(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def file_mtime(path: Path) -> float:
    return round(path.stat().st_mtime, 6)


def mtime_changed(previous: Any, current: float) -> bool:
    if previous is None:
        return True
    return abs(float(previous) - current) > MTIME_TOLERANCE_SECONDS


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(65536), b''):
            digest.update(chunk)
    return digest.hexdigest()


def iso_date_or_today(value: Any) -> str:
    text = str(value or '').strip()
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}', text):
        return text
    return date.today().isoformat()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def days_since(value: Any) -> int:
    text = iso_date_or_today(value)
    year, month, day = (int(part) for part in text.split('-'))
    current = date.today()
    return max(0, (current - date(year, month, day)).days)


def truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return ' '.join(words[:max_words]).strip() + ' ...'
