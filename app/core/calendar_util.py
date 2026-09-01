"""Calendario y semanas de nómina (compartido web/API)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

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
    """Copia de semanas con flags es_actual y etiqueta."""
    ref = ref or today()
    out = []
    for s in semanas:
        row = dict(s)
        row["es_actual"] = semana_contiene(ref, s.get("fecha_inicio"), s.get("fecha_fin"))
        cod = s.get("codigo") or "?"
        row["etiqueta"] = f"{cod} ★ ACTUAL" if row["es_actual"] else str(cod)
        out.append(row)
    return out


def rango_sab_vie(ref: date | None = None) -> tuple[date, date]:
    """Devuelve (sábado, viernes) de la semana de nómina que contiene *ref*."""
    ref = ref or today()
    days_since_sat = (ref.weekday() - 5) % 7
    sab = ref - timedelta(days=days_since_sat)
    vie = sab + timedelta(days=6)
    return sab, vie


_MESES_CORTO = (
    "", "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)


def codigo_desde_rango(sab: date, vie: date | None = None) -> str:
    """
    Código legible de semana sáb–vie.
    - Mismo mes: 01-07
    - Cruza mes: 29 ago-4 sep (evita ambigüedad 29/08-04/09 → “abril”)
    """
    vie = vie or (sab + timedelta(days=6))
    if sab.month == vie.month and sab.year == vie.year:
        return f"{sab.day:02d}-{vie.day:02d}"
    return (
        f"{sab.day:02d} {_MESES_CORTO[sab.month]}-"
        f"{vie.day} {_MESES_CORTO[vie.month]}"
    )


def sugerir_codigo_semana(ref: date | None = None) -> tuple[str, date, date]:
    """Semana sáb–vie que contiene la fecha de referencia."""
    sab, vie = rango_sab_vie(ref)
    return codigo_desde_rango(sab, vie), sab, vie


def siguiente_rango_semana(fecha_ref: date) -> tuple[str, date, date]:
    """
    Siguiente semana sáb–vie estricta.

    *fecha_ref* puede ser fecha_fin (idealmente viernes) o cualquier día de la
    semana origen: se normaliza al viernes de esa semana y se avanza +1 día
    (sábado siguiente). Así se evita el bug de saltar una semana cuando
    fecha_fin caía en sábado/domingo.
    """
    _sab_o, vie_o = rango_sab_vie(fecha_ref)
    sab = vie_o + timedelta(days=1)  # siempre el sábado siguiente
    # seguridad
    if sab.weekday() != 5:
        sab, _ = rango_sab_vie(sab)
    vie = sab + timedelta(days=6)
    return codigo_desde_rango(sab, vie), sab, vie


def encontrar_semana_por_rango(
    semanas: list[dict],
    sab: date,
    vie: date,
) -> dict | None:
    """Busca semana por fechas (no solo por código, que puede repetirse)."""
    for s in semanas:
        fi = parse_db_date(s.get("fecha_inicio"))
        ff = parse_db_date(s.get("fecha_fin"))
        if fi == sab and ff == vie:
            return s
        # tolerancia: misma semana si ref cae dentro
        if fi and ff and fi <= sab <= ff and fi <= vie <= ff:
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
