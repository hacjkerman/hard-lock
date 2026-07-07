"""Append-only event log and per-day usage history (JSONL).

Two files under the data dir:
  - events.jsonl  — one record per lock event (settings change, warning fire,
    shutdown, day rollover, ...). Newest-last.
  - history.jsonl — one record per completed day: how much active time was used,
    the cap in force, and whether the cap was hit.

Both are append-only and best-effort: logging must never break the app, and a
torn last line is skipped rather than fatal.
"""

import datetime as dt
import json
from pathlib import Path


def _now_iso() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _read_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    out = []
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue  # skip a torn/garbled line rather than fail the whole read
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _append_jsonl(path: Path, record: dict) -> None:
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except OSError:
        pass  # best-effort: never let logging crash the app


class EventLog:
    def __init__(self, path: Path):
        self._path = path

    def append(self, event_type: str, ts: "str | None" = None, **detail) -> None:
        record = {"ts": ts or _now_iso(), "type": event_type}
        record.update(detail)
        _append_jsonl(self._path, record)

    def all(self) -> list:
        return _read_jsonl(self._path)

    def recent(self, limit: int = 50) -> list:
        """Newest first."""
        rows = _read_jsonl(self._path)
        return list(reversed(rows[-limit:]))


class DayHistory:
    def __init__(self, path: Path):
        self._path = path

    def append_day(self, summary: dict) -> None:
        _append_jsonl(self._path, summary)

    def all(self) -> list:
        return _read_jsonl(self._path)

    def by_date(self) -> dict:
        """Map date → summary. If a date was written more than once, the last
        record wins (covers a same-day re-summarize)."""
        result = {}
        for rec in _read_jsonl(self._path):
            date = rec.get("date")
            if isinstance(date, str):
                result[date] = rec
        return result
