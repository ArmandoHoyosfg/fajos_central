"""Ajustes operativos persistidos (JSON simple, sin BD)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR

SETTINGS_FILE = Path(BASE_DIR) / "data" / "ops_settings.json"

DEFAULTS = {
    "anomaly_pct": 0.30,  # ±30 %
}


def load() -> dict[str, Any]:
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            out = dict(DEFAULTS)
            out.update(data or {})
            return out
    except Exception:
        pass
    return dict(DEFAULTS)


def save(updates: dict[str, Any]) -> dict[str, Any]:
    cur = load()
    cur.update(updates or {})
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8")
    return cur


def get_anomaly_pct() -> float:
    v = load().get("anomaly_pct", 0.30)
    try:
        f = float(v)
        return min(max(f, 0.05), 0.90)  # 5 % … 90 %
    except (TypeError, ValueError):
        return 0.30
