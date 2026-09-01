"""
Logging estructurado para la aplicación.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from app.core.config import settings


def setup_logging() -> None:
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    log_file = settings.log_dir / "fajos.log"

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Consola
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    sh.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Archivo
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.setLevel(logging.INFO)

    root.handlers.clear()
    root.addHandler(sh)
    root.addHandler(fh)
    try:
        from app.core.event_log import MemoryLogHandler
        mh = MemoryLogHandler()
        mh.setLevel(logging.INFO)
        root.addHandler(mh)  # type: ignore[arg-type]
    except Exception:
        pass


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
