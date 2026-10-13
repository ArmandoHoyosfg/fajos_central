"""Ajustes operativos y preferencias de UI (JSON, sin BD)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR

SETTINGS_FILE = Path(BASE_DIR) / "data" / "ops_settings.json"

# Preferencias de filtrado + captura + UI
DEFAULTS: dict[str, Any] = {
    # Rarezas (dashboard / captura)
    "anomaly_pct": 0.30,  # ±30 %
    # Por día
    "por_dia_solo_pendientes": False,  # filtro por defecto
    "por_dia_auto_sync": True,  # recargar si Plata cambió filas
    # Plata (filtros iniciales)
    "plata_solo_sin_firmar_avance": False,
    "plata_solo_sin_firmar_sin_avance": False,
    "plata_solo_sin_gramos_hoy": False,
    # Captura
    "confirm_edit_past_days": True,  # pedir confirmación al editar días pasados con gramos
    "gramos_step": 10,  # incremento sugerido (UI)
    # Export
    "export_omit_zero": True,  # no exportar filas en 0 (regla fija recomendada)
    "export_checklist": True,  # mostrar checklist antes de formal
    # UI general
    "theme_default": "",  # "" = no forzar; oscuro|claro|taller
    "remember_semana": True,  # sessionStorage semana entre vistas
    "hide_zeros_in_tables": True,
}


def load() -> dict[str, Any]:
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            out = dict(DEFAULTS)
            if isinstance(data, dict):
                out.update(data)
            return out
    except Exception:
        pass
    return dict(DEFAULTS)


def save(updates: dict[str, Any]) -> dict[str, Any]:
    cur = load()
    for k, v in (updates or {}).items():
        if k not in DEFAULTS:
            continue  # allowlist: solo claves conocidas
        cur[k] = v
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(
        json.dumps(cur, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return cur


def get_anomaly_pct() -> float:
    v = load().get("anomaly_pct", 0.30)
    try:
        f = float(v)
        return min(max(f, 0.05), 0.90)
    except (TypeError, ValueError):
        return 0.30


def get_bool(key: str, default: bool | None = None) -> bool:
    if default is None:
        default = bool(DEFAULTS.get(key, False))
    v = load().get(key, default)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v or "").strip().lower()
    return s in ("1", "true", "yes", "si", "sí", "on")


def public_settings() -> dict[str, Any]:
    """Payload listo para UI (incluye display del umbral)."""
    s = load()
    s["anomaly_pct_display"] = int(round(get_anomaly_pct() * 100))
    return s
