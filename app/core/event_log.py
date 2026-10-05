"""Buffer circular de eventos para la consola Dev (solo lectura en UI)."""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

_LOCK = threading.Lock()
_BUFFER: deque[dict[str, Any]] = deque(maxlen=500)
_SEQ = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


def push(
    level: str,
    message: str,
    *,
    source: str = "server",
    detail: str | None = None,
    path: str | None = None,
) -> dict[str, Any]:
    global _SEQ
    level = (level or "info").lower()
    if level not in ("debug", "info", "warning", "error", "success"):
        level = "info"
    with _LOCK:
        _SEQ += 1
        entry = {
            "id": _SEQ,
            "ts": _now_iso(),
            "level": level,
            "source": source or "server",
            "message": str(message)[:2000],
            "detail": (str(detail)[:4000] if detail else None),
            "path": path,
        }
        _BUFFER.append(entry)
        return entry


def list_since(after_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit or 200), 500))
    after_id = int(after_id or 0)
    with _LOCK:
        items = [e for e in _BUFFER if e["id"] > after_id]
        if not after_id:
            items = list(_BUFFER)[-limit:]
        else:
            items = items[-limit:]
        return list(items)


def clear() -> None:
    with _LOCK:
        _BUFFER.clear()


class MemoryLogHandler:
    """logging.Handler → buffer Dev."""

    def __init__(self, level: int = 20):  # INFO
        import logging
        self.level = level
        self._logging = logging

    def handle(self, record) -> bool:  # noqa: A003
        try:
            if record.levelno < self.level:
                return True
            level = "info"
            if record.levelno >= 40:
                level = "error"
            elif record.levelno >= 30:
                level = "warning"
            elif record.levelno <= 10:
                level = "debug"
            msg = record.getMessage()
            detail = None
            if record.exc_info:
                import traceback
                detail = "".join(traceback.format_exception(*record.exc_info))[-3000:]
            push(
                level,
                f"{record.name}: {msg}",
                source="log",
                detail=detail,
            )
        except Exception:
            pass
        return True

    def createLock(self):  # noqa: N802
        return None

    def acquire(self):
        pass

    def release(self):
        pass

    def filter(self, record):
        return True

    def setLevel(self, level):  # noqa: N802
        self.level = level

    def format(self, record):
        return record.getMessage()

    def emit(self, record):
        self.handle(record)

    def flush(self):
        pass

    def close(self):
        pass
