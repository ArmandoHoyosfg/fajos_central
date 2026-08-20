"""
Calendario de nómina (sáb→vie). Preferir app.core; fallback local si falla el path.
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

WEEKDAY_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}
MONTH_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def today() -> date:
    return date.today()


def format_fecha_larga(d: date | None = None) -> str:
    d = d or today()
    return f"{WEEKDAY_ES[d.weekday()].capitalize()} {d.day} de {MONTH_ES[d.month]} de {d.year}"


def format_fecha_corta(d: date | None = None) -> str:
    d = d or today()
    return d.strftime("%d/%m/%Y")


def parse_db_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        return None


def semana_contiene(fecha: date, inicio: Any, fin: Any) -> bool:
    fi, ff = parse_db_date(inicio), parse_db_date(fin)
    if not fi or not ff:
        return False
    if fi > ff:
        fi, ff = ff, fi
    return fi <= fecha <= ff


def encontrar_semana_actual(semanas: list[dict], ref: date | None = None) -> dict | None:
    ref = ref or today()
    for s in semanas:
        if semana_contiene(ref, s.get("fecha_inicio"), s.get("fecha_fin")):
            return s
    return None


def marcar_semanas(semanas: list[dict], ref: date | None = None) -> list[dict]:
    ref = ref or today()
    out = []
    for s in semanas:
        row = dict(s)
        row["es_actual"] = semana_contiene(ref, s.get("fecha_inicio"), s.get("fecha_fin"))
        cod = s.get("codigo") or "?"
        row["etiqueta"] = f"{cod} ★ ACTUAL" if row["es_actual"] else str(cod)
        out.append(row)
    return out


def etiqueta_semana(s: dict, ref: date | None = None) -> str:
    ref = ref or today()
    codigo = s.get("codigo") or "?"
    fi = parse_db_date(s.get("fecha_inicio"))
    ff = parse_db_date(s.get("fecha_fin"))
    rango = f"  ({fi.isoformat()} → {ff.isoformat()})" if fi and ff else ""
    marca = "  ★ ACTUAL" if semana_contiene(ref, fi, ff) else ""
    return f"{codigo}{rango}{marca}"


def sugerir_codigo_semana(ref: date | None = None) -> tuple[str, date, date]:
    ref = ref or today()
    days_since_sat = (ref.weekday() - 5) % 7
    sab = ref - timedelta(days=days_since_sat)
    vie = sab + timedelta(days=6)
    return f"{sab.day:02d}-{vie.day:02d}", sab, vie


# Prefer canonical app.core if available (same names)
try:
    from app.core.calendar_util import (  # type: ignore  # noqa: F401
        MONTH_ES as _M,
        WEEKDAY_ES as _W,
        encontrar_semana_actual,
        etiqueta_semana,
        format_fecha_corta,
        format_fecha_larga,
        marcar_semanas,
        parse_db_date,
        semana_contiene,
        sugerir_codigo_semana,
        today,
    )
except Exception:
    pass

__all__ = [
    "WEEKDAY_ES", "MONTH_ES", "today", "format_fecha_larga", "format_fecha_corta",
    "parse_db_date", "semana_contiene", "encontrar_semana_actual", "marcar_semanas",
    "etiqueta_semana", "sugerir_codigo_semana",
]
