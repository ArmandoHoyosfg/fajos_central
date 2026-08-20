"""
Compatibilidad: reexporta el calendario canónico de app.core.
Evita divergencias entre web y escritorio.
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.calendar_util import (  # noqa: F401
    MONTH_ES,
    WEEKDAY_ES,
    encontrar_semana_actual,
    format_fecha_corta,
    format_fecha_larga,
    marcar_semanas,
    parse_db_date,
    semana_contiene,
    sugerir_codigo_semana,
    today,
)

__all__ = [
    "WEEKDAY_ES",
    "MONTH_ES",
    "today",
    "format_fecha_larga",
    "format_fecha_corta",
    "parse_db_date",
    "semana_contiene",
    "encontrar_semana_actual",
    "marcar_semanas",
    "sugerir_codigo_semana",
]
