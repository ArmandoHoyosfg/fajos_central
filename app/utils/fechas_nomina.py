"""Fechas legibles de nómina: periodo de captura y día de pago (sábado)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

MESES = (
    "", "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def parse_fecha(v: Any) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def fecha_pago(fecha_inicio: Any, fecha_fin: Any) -> date | None:
    """
    Día de pago: sábado.
    La nómina se cierra/imprime en viernes; se paga el sábado siguiente.
    Si fecha_fin es viernes → +1 día; si ya es sábado → ese día; si no → próximo sábado.
    """
    fin = parse_fecha(fecha_fin)
    if not fin:
        ini = parse_fecha(fecha_inicio)
        if not ini:
            return None
        # sábado de la semana de inicio + 7 (pago al cierre)
        fin = ini + timedelta(days=6)
    wd = fin.weekday()  # lun=0 … dom=6
    if wd == 4:  # viernes
        return fin + timedelta(days=1)
    if wd == 5:  # sábado
        return fin
    # próximo sábado después de fin
    delta = (5 - wd) % 7
    if delta == 0:
        delta = 7
    return fin + timedelta(days=delta)


def fecha_es(d: date | None, *, con_anio: bool = True) -> str:
    if not d:
        return "—"
    base = f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month]}"
    if con_anio:
        base += f" de {d.year}"
    return base


def leyenda_nomina(
    fecha_inicio: Any = None,
    fecha_fin: Any = None,
    *,
    codigo: str = "",
) -> dict:
    """Textos listos para encabezados de export / UI."""
    ini = parse_fecha(fecha_inicio)
    fin = parse_fecha(fecha_fin)
    pago = fecha_pago(ini, fin)
    periodo = ""
    if ini and fin:
        if ini.month == fin.month and ini.year == fin.year:
            periodo = (
                f"{DIAS[ini.weekday()]} {ini.day} — "
                f"{DIAS[fin.weekday()]} {fin.day} de {MESES[fin.month]} de {fin.year}"
            )
        else:
            periodo = f"{fecha_es(ini)} — {fecha_es(fin)}"
    return {
        "titulo_pago": f"Nómina del {fecha_es(pago).capitalize()}" if pago else (f"Nómina {codigo}" if codigo else "Nómina"),
        "periodo_captura": periodo,
        "cierre": "Cierre e impresión: viernes",
        "pago": f"Día de pago: {fecha_es(pago)}" if pago else "Día de pago: sábado",
        "fecha_pago": pago,
        "fecha_inicio": ini,
        "fecha_fin": fin,
        "linea": " · ".join(
            x for x in [
                f"Nómina del {fecha_es(pago).capitalize()}" if pago else None,
                f"Periodo: {periodo}" if periodo else None,
                "Cierre/impresión: viernes",
            ] if x
        ),
    }


def dias_en_periodo(fecha_inicio: Any, fecha_fin: Any) -> list[date]:
    ini = parse_fecha(fecha_inicio)
    fin = parse_fecha(fecha_fin)
    if not ini or not fin or fin < ini:
        return []
    out = []
    d = ini
    while d <= fin:
        out.append(d)
        d += timedelta(days=1)
    return out
