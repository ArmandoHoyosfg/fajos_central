"""Mapeo de días de la semana de nómina (sáb→vie) y reglas de edición."""
from __future__ import annotations

from datetime import date
from typing import Any

# Python weekday: Mon=0 ... Sun=6  →  columnas de nómina
DAY_BY_WEEKDAY = {
    5: "gm_sab",
    6: "gm_dom",
    0: "gm_lun",
    1: "gm_mar",
    2: "gm_mie",
    3: "gm_jue",
    4: "gm_vie",
}
DAY_LABELS = {
    "gm_sab": "Sábado",
    "gm_dom": "Domingo",
    "gm_lun": "Lunes",
    "gm_mar": "Martes",
    "gm_mie": "Miércoles",
    "gm_jue": "Jueves",
    "gm_vie": "Viernes",
}
DAY_SHORT = {
    "gm_sab": "Sáb",
    "gm_dom": "Dom",
    "gm_lun": "Lun",
    "gm_mar": "Mar",
    "gm_mie": "Mié",
    "gm_jue": "Jue",
    "gm_vie": "Vie",
}
ORDERED_DAYS = ["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"]


def col_hoy(ref: date | None = None) -> str:
    ref = ref or date.today()
    return DAY_BY_WEEKDAY.get(ref.weekday(), "gm_lun")


def label_hoy(ref: date | None = None) -> str:
    return DAY_LABELS[col_hoy(ref)]


def es_dia_pasado(col: str, ref: date | None = None) -> bool:
    """True si `col` es un día de la semana de nómina anterior a hoy."""
    ref = ref or date.today()
    hoy = col_hoy(ref)
    try:
        return ORDERED_DAYS.index(col) < ORDERED_DAYS.index(hoy)
    except ValueError:
        return False


def valor_gramos(row: dict, col: str) -> float:
    v = row.get(col)
    if v is None or v == "":
        return 0.0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def requiere_confirmacion_pasado(row: dict, col: str, ref: date | None = None) -> bool:
    """Editar un día pasado que ya tiene gramos → pedir confirmación."""
    return es_dia_pasado(col, ref) and valor_gramos(row, col) > 0


def trabajos_sin_gramos_hoy(lineas: list[dict], ref: date | None = None) -> list[dict]:
    """Líneas/trabajos activos sin captura en el día de hoy."""
    col = col_hoy(ref)
    out = []
    for r in lineas:
        if valor_gramos(r, col) <= 0:
            out.append(r)
    return out
