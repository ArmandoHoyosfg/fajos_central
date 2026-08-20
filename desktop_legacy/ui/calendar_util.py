"""Utilidades de calendario y semanas de nómina."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

# Semana de nómina: sábado → viernes (coincide con columnas gm_sab…gm_vie)
WEEKDAY_ES = {
    0: "lunes",
    1: "martes",
    2: "miércoles",
    3: "jueves",
    4: "viernes",
    5: "sábado",
    6: "domingo",
}
MONTH_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
    5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
    9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def today() -> date:
    return date.today()


def format_fecha_larga(d: date | None = None) -> str:
    """Ej: Jueves 20 de agosto de 2026."""
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
    s = str(value).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def semana_contiene(fecha: date, inicio: Any, fin: Any) -> bool:
    fi = parse_db_date(inicio)
    ff = parse_db_date(fin)
    if not fi or not ff:
        return False
    if fi > ff:
        fi, ff = ff, fi
    return fi <= fecha <= ff


def encontrar_semana_actual(semanas: list[dict], ref: date | None = None) -> dict | None:
    """Devuelve la fila de semana cuyo rango incluye `ref` (hoy por defecto)."""
    ref = ref or today()
    for s in semanas:
        if semana_contiene(ref, s.get("fecha_inicio"), s.get("fecha_fin")):
            return s
    return None


def etiqueta_semana(s: dict, ref: date | None = None) -> str:
    """Texto para combo: código, fechas y marca si es la semana actual."""
    ref = ref or today()
    codigo = s.get("codigo") or "?"
    fi = parse_db_date(s.get("fecha_inicio"))
    ff = parse_db_date(s.get("fecha_fin"))
    rango = ""
    if fi and ff:
        rango = f"  ({fi.isoformat()} → {ff.isoformat()})"
    marca = "  ★ ACTUAL" if semana_contiene(ref, fi, ff) else ""
    return f"{codigo}{rango}{marca}"


def sugerir_codigo_semana(ref: date | None = None) -> tuple[str, date, date]:
    """
    Sugiere código DD-MM y rango sáb→vie de la semana que contiene `ref`.
    Código = día-mes del sábado de inicio (estilo taller: 16-22, 02-05…).
    """
    ref = ref or today()
    # sábado de esta semana de nómina
    # Python: Mon=0 … Sun=6. Sábado = 5.
    # Días desde el sábado anterior (o hoy si es sábado)
    days_since_sat = (ref.weekday() - 5) % 7
    sab = ref - timedelta(days=days_since_sat)
    vie = sab + timedelta(days=6)
    codigo = f"{sab.day:02d}-{vie.day:02d}"
    return codigo, sab, vie
