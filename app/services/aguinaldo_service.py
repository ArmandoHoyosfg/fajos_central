"""Reporte de trabajadores elegibles a aguinaldo (actividad real en N semanas)."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.db.connection import get_db
from app.db.repos.semanas import SemanasRepo
from app.db.repos.trabajadores import TrabajadoresRepo
from app.utils.fechas_nomina import parse_fecha, fecha_es, fecha_pago


def _key_tid(tid: Any) -> str | None:
    if tid is None or tid == "":
        return None
    try:
        return f"id:{int(tid)}"
    except (TypeError, ValueError):
        return None


def _key_nombre_ubic(nombre: Any, ubic: Any) -> str:
    n = str(nombre or "").strip().upper()
    try:
        u = int(ubic)
    except (TypeError, ValueError):
        u = 0
    return f"nu:{n}|{u}"


class AguinaldoService:
    """Detecta actividad real (gramos/pagos > 0) en las últimas N semanas."""

    def __init__(self, db=None):
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.trab = TrabajadoresRepo(self.db)

    def ultimas_semanas(self, n: int = 5) -> list[dict]:
        n = max(1, min(int(n or 5), 52))
        rows = self.semanas.listar() or []
        # listar suele venir reciente primero; ordenar por fecha_inicio desc
        def _fi(s):
            d = parse_fecha(s.get("fecha_inicio"))
            return d or date.min

        rows = sorted(rows, key=_fi, reverse=True)
        return rows[:n]

    def calcular(
        self,
        *,
        n_semanas: int = 5,
        monto_fijo_piteador: float = 0.0,
        min_semanas_activas: int = 1,
    ) -> dict[str, Any]:
        """
        Devuelve filas elegibles + meta.
        Activo = pago/gramos > 0 en al menos min_semanas_activas de las N.
        """
        n_semanas = max(1, min(int(n_semanas or 5), 52))
        min_semanas_activas = max(1, min(int(min_semanas_activas or 1), n_semanas))
        try:
            monto_fijo = float(monto_fijo_piteador or 0)
        except (TypeError, ValueError):
            monto_fijo = 0.0

        semanas = self.ultimas_semanas(n_semanas)
        semana_ids = [int(s["id"]) for s in semanas]
        codigos = [str(s.get("codigo") or s["id"]) for s in semanas]

        # catálogo (todos, para cruzar bajas)
        try:
            catalogo = self.trab.listar(solo_activos=False) or []
        except Exception:
            catalogo = []
        by_id: dict[int, dict] = {}
        by_nu: dict[str, dict] = {}
        for t in catalogo:
            if t.get("id") is not None:
                by_id[int(t["id"])] = t
            by_nu[_key_nombre_ubic(t.get("nombre_mostrar"), t.get("ubic"))] = t

        # acumuladores por clave canónica
        # slot: pagos por semana, totales por área
        slots: dict[str, dict] = {}

        def slot_for(tid, nombre, ubic) -> dict:
            k = _key_tid(tid)
            if not k:
                k = _key_nombre_ubic(nombre, ubic)
            if k not in slots:
                cat = None
                if _key_tid(tid) and int(tid) in by_id:
                    cat = by_id[int(tid)]
                else:
                    cat = by_nu.get(_key_nombre_ubic(nombre, ubic))
                slots[k] = {
                    "key": k,
                    "trabajador_id": int(tid) if _key_tid(tid) else (cat or {}).get("id"),
                    "nombre": (cat or {}).get("nombre_mostrar") or nombre or "",
                    "ubic": (cat or {}).get("ubic") if cat and cat.get("ubic") is not None else ubic,
                    "tipo_cat": (cat or {}).get("tipo") or "",
                    "puesto": (cat or {}).get("puesto") or "",
                    "puestos_tll": set(),  # puestos vistos en nómina taller
                    "activo_cat": bool((cat or {}).get("activo", 1)) if cat else None,
                    "sueldo_modo": (cat or {}).get("sueldo_modo") or "variable",
                    "sueldo_base": (cat or {}).get("sueldo_base"),
                    "semanas_pago": set(),
                    "plt_gramos": 0.0,
                    "plt_efectivo": 0.0,
                    "pit_efectivo": 0.0,
                    "tll_total": 0.0,
                    "tll_sueldos": [],
                    "ultima_semana": None,
                    "ultima_codigo": None,
                    "ultima_fecha_inicio": None,
                    "ultima_fecha_fin": None,
                }
            # actualizar nombre si viene más completo
            s = slots[k]
            if nombre and (not s["nombre"] or len(str(nombre)) > len(str(s["nombre"]))):
                if not s.get("trabajador_id"):
                    s["nombre"] = nombre
            return s

        if not semana_ids:
            return {
                "ok": True,
                "filas": [],
                "meta": {
                    "n_semanas": n_semanas,
                    "min_semanas_activas": min_semanas_activas,
                    "monto_fijo_piteador": monto_fijo,
                    "semanas": [],
                    "n_elegibles": 0,
                },
            }

        # --- Plata ---
        try:
            with self.db.cursor() as cur:
                ph = ",".join(["%s"] * len(semana_ids))
                cur.execute(
                    f"""
                    SELECT semana_id, trabajador_id, nombre, ubic,
                           COALESCE(SUM(total_gramos), 0) AS g,
                           COALESCE(SUM(efectivo), 0) AS e
                    FROM produccion_plata
                    WHERE semana_id IN ({ph})
                    GROUP BY semana_id, trabajador_id, nombre, ubic
                    """,
                    tuple(semana_ids),
                )
                for r in cur.fetchall() or []:
                    g = float(r.get("g") or 0)
                    e = float(r.get("e") or 0)
                    if g <= 0 and e <= 0:
                        continue
                    s = slot_for(r.get("trabajador_id"), r.get("nombre"), r.get("ubic"))
                    s["plt_gramos"] += g
                    s["plt_efectivo"] += e
                    sid = int(r["semana_id"])
                    s["semanas_pago"].add(sid)
                    self._touch_ultima(s, sid, semanas)
        except Exception:
            pass

        # --- Pita ---
        try:
            with self.db.cursor() as cur:
                ph = ",".join(["%s"] * len(semana_ids))
                cur.execute(
                    f"""
                    SELECT semana_id, trabajador_id, nombre, ubic,
                           COALESCE(SUM(efectivo), 0) AS e
                    FROM produccion_pita
                    WHERE semana_id IN ({ph})
                    GROUP BY semana_id, trabajador_id, nombre, ubic
                    """,
                    tuple(semana_ids),
                )
                for r in cur.fetchall() or []:
                    e = float(r.get("e") or 0)
                    if e <= 0:
                        continue
                    s = slot_for(r.get("trabajador_id"), r.get("nombre"), r.get("ubic"))
                    s["pit_efectivo"] += e
                    sid = int(r["semana_id"])
                    s["semanas_pago"].add(sid)
                    self._touch_ultima(s, sid, semanas)
        except Exception:
            pass

        # --- Taller ---
        try:
            with self.db.cursor() as cur:
                ph = ",".join(["%s"] * len(semana_ids))
                cur.execute(
                    f"""
                    SELECT semana_id, trabajador_id, nombre, ubic, puesto,
                           COALESCE(SUM(total), 0) AS t,
                           COALESCE(SUM(sueldo), 0) AS su
                    FROM nomina_taller
                    WHERE semana_id IN ({ph})
                    GROUP BY semana_id, trabajador_id, nombre, ubic, puesto
                    """,
                    tuple(semana_ids),
                )
                for r in cur.fetchall() or []:
                    t = float(r.get("t") or 0)
                    su = float(r.get("su") or 0)
                    pago = t if t > 0 else su
                    if pago <= 0:
                        continue
                    s = slot_for(r.get("trabajador_id"), r.get("nombre"), r.get("ubic"))
                    s["tll_total"] += pago
                    s["tll_sueldos"].append(pago)
                    pue = str(r.get("puesto") or "").strip()
                    if pue:
                        s["puestos_tll"].add(pue)
                        if not s.get("puesto"):
                            s["puesto"] = pue
                    sid = int(r["semana_id"])
                    s["semanas_pago"].add(sid)
                    self._touch_ultima(s, sid, semanas)
        except Exception:
            pass

        filas = []
        for s in slots.values():
            n_act = len(s["semanas_pago"])
            if n_act < min_semanas_activas:
                continue
            tiene_plt = s["plt_gramos"] > 0 or s["plt_efectivo"] > 0
            tiene_pit = s["pit_efectivo"] > 0
            tiene_tll = s["tll_total"] > 0
            if not (tiene_plt or tiene_pit or tiene_tll):
                continue

            # Etiqueta de área/puesto legible
            partes_piteo = []
            if tiene_plt:
                partes_piteo.append("Plata")
            if tiene_pit:
                partes_piteo.append("Pita")
            puesto_tll = s.get("puesto") or ""
            if s.get("puestos_tll"):
                # el más frecuente no lo tenemos; listar únicos
                puesto_tll = " / ".join(sorted(s["puestos_tll"]))
            if tiene_tll and (tiene_plt or tiene_pit):
                area = f"Mixto · Taller ({puesto_tll or 'sin puesto'}) + {'/'.join(partes_piteo)}"
                area_grupo = "Mixto"
            elif tiene_tll:
                area = f"Taller · {puesto_tll}" if puesto_tll else "Taller"
                area_grupo = "Taller"
            else:
                area = " / ".join(partes_piteo) if partes_piteo else "Piteador"
                area_grupo = "Piteador"

            notas = []
            if s["activo_cat"] is False:
                notas.append("Baja en catálogo pero con actividad")
            if n_act < 2:
                notas.append("Solo 1 semana con pago")
            if area_grupo == "Mixto":
                notas.append("Actividad taller + piteado")

            modo = str(s.get("sueldo_modo") or "variable").strip().lower()
            es_fijo = modo == "fijo"
            sueldo_ref = None
            aguinaldo = None  # None → celda en blanco
            base_calc = None

            if area_grupo in ("Taller", "Mixto") and tiene_tll:
                if es_fijo:
                    sueldo_ref = self._sueldo_referencia_fijo(s)
                    if sueldo_ref and sueldo_ref > 0:
                        base_calc = sueldo_ref
                        aguinaldo = round(2.0 * sueldo_ref, 2)
                    else:
                        notas.append("Sueldo fijo sin base; aguinaldo pendiente")
                else:
                    notas.append("Sueldo variable; aguinaldo no aplica (solo fijo ×2)")
                    # base informativa opcional: dejar en blanco también
                    base_calc = None
                    aguinaldo = None
                # Mixto sin taller fijo: no rellenar con fijo piteador automáticamente
            else:
                # Piteador
                base_calc = monto_fijo
                aguinaldo = round(monto_fijo, 2) if monto_fijo else None
                if not monto_fijo:
                    notas.append("Definir monto fijo piteador")

            filas.append({
                "nombre": s["nombre"],
                "ubic": s["ubic"],
                "area": area,
                "area_grupo": area_grupo,
                "semanas_activas": n_act,
                "ultimo_pago": self._fmt_ultimo_pago(s),
                "base_calculo": base_calc if base_calc not in (None, "") else "",
                "aguinaldo": aguinaldo if aguinaldo is not None else "",
                "notas": "; ".join(notas),
                "activo_catalogo": s["activo_cat"],
                "sueldo_modo": modo,
                "plt_efectivo": round(s["plt_efectivo"], 2),
                "pit_efectivo": round(s["pit_efectivo"], 2),
                "tll_total": round(s["tll_total"], 2),
            })

        # Orden: área, nombre, ubic
        order_area = {"Taller": 0, "Mixto": 1, "Piteador": 2}
        filas.sort(key=lambda r: (
            order_area.get(r.get("area_grupo") or r.get("area"), 9),
            str(r.get("nombre") or "").upper(),
            int(r.get("ubic") or 0),
        ))

        return {
            "ok": True,
            "filas": filas,
            "meta": {
                "n_semanas": n_semanas,
                "min_semanas_activas": min_semanas_activas,
                "monto_fijo_piteador": monto_fijo,
                "semanas": [
                    {
                        "id": int(s["id"]),
                        "codigo": s.get("codigo"),
                        "fecha_inicio": str(s.get("fecha_inicio") or ""),
                        "fecha_fin": str(s.get("fecha_fin") or ""),
                    }
                    for s in semanas
                ],
                "codigos": codigos,
                "n_elegibles": len(filas),
                "total_aguinaldo": round(
                    sum(
                        float(f["aguinaldo"])
                        for f in filas
                        if f.get("aguinaldo") not in (None, "")
                    ),
                    2,
                ),
            },
        }

    @staticmethod
    def _touch_ultima(slot: dict, semana_id: int, semanas: list[dict]) -> None:
        idx = {int(s["id"]): i for i, s in enumerate(semanas)}
        cur = slot.get("_ultima_idx")
        new_i = idx.get(semana_id)
        if new_i is None:
            return
        if cur is None or new_i < cur:
            sem = semanas[new_i]
            slot["_ultima_idx"] = new_i
            slot["ultima_semana"] = semana_id
            slot["ultima_codigo"] = sem.get("codigo") or str(semana_id)
            slot["ultima_fecha_inicio"] = sem.get("fecha_inicio")
            slot["ultima_fecha_fin"] = sem.get("fecha_fin")

    @staticmethod
    def _fmt_ultimo_pago(slot: dict) -> str:
        """Ej: sábado 25 de octubre de 2026 (sem. 24-30)."""
        fi = parse_fecha(slot.get("ultima_fecha_inicio"))
        ff = parse_fecha(slot.get("ultima_fecha_fin"))
        pago = fecha_pago(fi, ff)
        cod = slot.get("ultima_codigo") or ""
        if pago:
            label = fecha_es(pago, con_anio=True)
            return f"{label} (sem. {cod})" if cod else label
        if fi:
            # sábado de inicio de semana de captura
            sab = fi
            label = fecha_es(sab, con_anio=True)
            return f"{label} (sem. {cod})" if cod else label
        return cod or "—"

    @staticmethod
    def _sueldo_referencia_fijo(slot: dict) -> float | None:
        """Solo sueldo base de catálogo en modo fijo (no promedios variables)."""
        base = slot.get("sueldo_base")
        if base in (None, ""):
            return None
        try:
            v = float(base)
            return v if v > 0 else None
        except (TypeError, ValueError):
            return None

    def export_excel(
        self,
        *,
        n_semanas: int = 5,
        monto_fijo_piteador: float = 0.0,
        min_semanas_activas: int = 1,
    ) -> tuple[bytes, str, str]:
        data = self.calcular(
            n_semanas=n_semanas,
            monto_fijo_piteador=monto_fijo_piteador,
            min_semanas_activas=min_semanas_activas,
        )
        content = self._to_xlsx(data)
        stem = f"aguinaldo_ultimas_{data['meta']['n_semanas']}_semanas"
        return (
            content,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{stem}.xlsx",
        )

    def _to_xlsx(self, data: dict) -> bytes:
        filas = data.get("filas") or []
        meta = data.get("meta") or {}
        wb = Workbook()
        ws = wb.active
        ws.title = "Aguinaldo"

        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        title_font = Font(name="Calibri", bold=True, size=13, color="1F4E79")
        money = '"$"#,##0.00'
        thin = Border(
            left=Side(style="thin", color="CCCCCC"),
            right=Side(style="thin", color="CCCCCC"),
            top=Side(style="thin", color="CCCCCC"),
            bottom=Side(style="thin", color="CCCCCC"),
        )
        alt = PatternFill("solid", fgColor="F5F7FA")

        ws["A1"] = "Elegibles a aguinaldo — actividad real en nómina"
        ws["A1"].font = title_font
        ws.merge_cells("A1:H1")

        cods = ", ".join(meta.get("codigos") or [])
        ws["A2"] = (
            f"Últimas {meta.get('n_semanas', 5)} semanas: {cods or '—'} · "
            f"Mín. semanas con pago: {meta.get('min_semanas_activas', 1)} · "
            f"Fijo piteador: ${float(meta.get('monto_fijo_piteador') or 0):,.2f} · "
            f"Taller fijo: 2 × sueldo base · variable en blanco · "
            f"Elegibles: {meta.get('n_elegibles', 0)}"
        )
        ws["A2"].font = Font(name="Calibri", size=9, color="666666")
        ws.merge_cells("A2:H2")

        headers = [
            "Nombre", "Ubic", "Área", "Semanas activas",
            "Último pago", "Base cálculo", "Aguinaldo", "Notas",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(4, col, h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin

        for i, r in enumerate(filas):
            row = 5 + i
            vals = [
                r.get("nombre"),
                r.get("ubic"),
                r.get("area"),
                r.get("semanas_activas"),
                r.get("ultimo_pago"),
                r.get("base_calculo"),
                r.get("aguinaldo"),
                r.get("notas") or "",
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row, col, v if v is not None else "")
                cell.border = thin
                if col in (6, 7) and isinstance(v, (int, float)):
                    cell.number_format = money
                if i % 2:
                    cell.fill = alt

        # Totales
        tot_row = 5 + len(filas)
        ws.cell(tot_row, 1, "TOTAL").font = Font(bold=True)
        cell = ws.cell(tot_row, 7, float(meta.get("total_aguinaldo") or 0))
        cell.font = Font(bold=True)
        cell.number_format = money
        cell.fill = PatternFill("solid", fgColor="C6EFCE")

        widths = [28, 8, 10, 14, 14, 12, 12, 36]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.freeze_panes = "A5"
        if filas:
            ws.auto_filter.ref = f"A4:H{4 + len(filas)}"

        # Hoja breve de reglas
        ws2 = wb.create_sheet("Criterios")
        ws2["A1"] = "Criterios"
        ws2["A1"].font = title_font
        lines = [
            "Se incluye quien tuvo gramos o pagos > 0 en Plata, Pita o Taller en el periodo.",
            "No se usa solo el flag «activo» del catálogo (hay bajas mal registradas).",
            "Último pago: sábado de pago de la última semana con actividad (legible).",
            "Piteador (Plata/Pita): monto fijo configurable.",
            "Taller: aguinaldo = 2 × sueldo SOLO si sueldo_modo = fijo y hay sueldo_base; variable queda en blanco.",
            "Área indica Plata, Pita y/o Taller con puesto cuando aplica.",
        ]
        for i, t in enumerate(lines, 3):
            ws2.cell(i, 1, t)
        ws2.column_dimensions["A"].width = 100

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()
