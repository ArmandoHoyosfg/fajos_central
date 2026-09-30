"""Estadísticas históricas por trabajador, folio y día."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from app.core.calendar_util import today as today_fn
from app.db.connection import get_db
from app.db.repository import SemanasRepo, ProduccionRepo
from app.utils.fechas_nomina import parse_fecha, fecha_es

# Orden de columnas de gramos (semana nómina sáb→vie)
_DAY_COLS = ("gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie")
_DAY_LABELS = {
    "gm_sab": "Sáb", "gm_dom": "Dom", "gm_lun": "Lun",
    "gm_mar": "Mar", "gm_mie": "Mié", "gm_jue": "Jue", "gm_vie": "Vie",
}


class StatsService:
    def __init__(self, db=None):
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.prod = ProduccionRepo(self.db)

    def listar_semanas(self) -> list[dict]:
        return self.semanas.listar() or []

    def _semanas_filtradas(
        self,
        semana_ids: list[int] | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
    ) -> list[dict]:
        semanas = self.listar_semanas()
        if semana_ids:
            want = set(int(x) for x in semana_ids)
            semanas = [s for s in semanas if int(s["id"]) in want]
        if fecha_desde or fecha_hasta:
            out = []
            for s in semanas:
                fi = parse_fecha(s.get("fecha_inicio"))
                ff = parse_fecha(s.get("fecha_fin")) or fi
                if not fi:
                    continue
                if fecha_desde and ff and ff < fecha_desde:
                    continue
                if fecha_hasta and fi and fi > fecha_hasta:
                    continue
                out.append(s)
            semanas = out
        return semanas

    def stats_trabajador(
        self,
        q: str = "",
        semana_ids: list[int] | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        limit: int = 80,
    ) -> list[dict]:
        """Agrega gramos y $ por trabajador en semanas/rango seleccionados."""
        semanas = self._semanas_filtradas(semana_ids, fecha_desde, fecha_hasta)
        agg: dict[tuple, dict] = {}
        for s in semanas:
            sid = int(s["id"])
            try:
                rows = self.prod.listar_por_semana(sid, incluir_terminados=True)
            except Exception:
                continue
            for r in rows:
                nombre = str(r.get("nombre") or "").strip()
                try:
                    ubic = int(r.get("ubic") or 0)
                except (TypeError, ValueError):
                    ubic = 0
                if q:
                    ql = q.lower()
                    if ql not in nombre.lower() and ql not in str(ubic):
                        continue
                key = (nombre.upper(), ubic)
                slot = agg.setdefault(key, {
                    "nombre": nombre,
                    "ubic": ubic,
                    "total_gramos": 0.0,
                    "total_efectivo": 0.0,
                    "semanas": set(),
                    "folios": set(),
                    "primera": None,
                    "ultima": None,
                    "dias_con_avance": 0,
                })
                g = float(r.get("total_gramos") or 0)
                e = float(r.get("efectivo") or 0)
                # Si hay rango de fechas, sumar solo días del rango
                if fecha_desde or fecha_hasta:
                    g, e, n_dias = self._sum_dias_rango(r, s, fecha_desde, fecha_hasta)
                    slot["dias_con_avance"] += n_dias
                else:
                    for col in _DAY_COLS:
                        if float(r.get(col) or 0) > 0:
                            slot["dias_con_avance"] += 1
                slot["total_gramos"] += g
                slot["total_efectivo"] += e
                slot["semanas"].add(s.get("codigo") or str(sid))
                folio = (r.get("folio") or "").strip()
                if folio:
                    slot["folios"].add(folio)
                fi = parse_fecha(s.get("fecha_inicio"))
                ff = parse_fecha(s.get("fecha_fin"))
                if fi and (slot["primera"] is None or fi < slot["primera"]):
                    slot["primera"] = fi
                if ff and (slot["ultima"] is None or ff > slot["ultima"]):
                    slot["ultima"] = ff
        out = []
        for slot in agg.values():
            out.append({
                "nombre": slot["nombre"],
                "ubic": slot["ubic"],
                "total_gramos": round(slot["total_gramos"], 1),
                "total_efectivo": round(slot["total_efectivo"], 2),
                "n_semanas": len(slot["semanas"]),
                "n_folios": len(slot["folios"]),
                "folios": sorted(slot["folios"])[:12],
                "primera": fecha_es(slot["primera"]) if slot["primera"] else "—",
                "ultima": fecha_es(slot["ultima"]) if slot["ultima"] else "—",
                "dias_con_avance": slot["dias_con_avance"],
            })
        out.sort(key=lambda x: (-x["total_gramos"], x["nombre"]))
        return out[:limit]

    def stats_folio(
        self,
        q: str = "",
        semana_ids: list[int] | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        limit: int = 80,
    ) -> list[dict]:
        semanas = self._semanas_filtradas(semana_ids, fecha_desde, fecha_hasta)
        agg: dict[str, dict] = {}
        for s in semanas:
            sid = int(s["id"])
            try:
                rows = self.prod.listar_por_semana(sid, incluir_terminados=True)
            except Exception:
                continue
            fi = parse_fecha(s.get("fecha_inicio"))
            for r in rows:
                folio = (r.get("folio") or "").strip()
                if not folio:
                    continue
                if q and q.lower() not in folio.lower() and q.lower() not in str(r.get("nombre") or "").lower():
                    continue
                slot = agg.setdefault(folio.upper(), {
                    "folio": folio,
                    "total_gramos": 0.0,
                    "total_efectivo": 0.0,
                    "trabajadores": set(),
                    "materiales": set(),
                    "modelos": set(),
                    "semanas": set(),
                    "inicio": None,
                    "dias_con_avance": 0,
                })
                if fecha_desde or fecha_hasta:
                    g, e, n_dias = self._sum_dias_rango(r, s, fecha_desde, fecha_hasta)
                    slot["dias_con_avance"] += n_dias
                else:
                    g = float(r.get("total_gramos") or 0)
                    e = float(r.get("efectivo") or 0)
                    for col in _DAY_COLS:
                        if float(r.get(col) or 0) > 0:
                            slot["dias_con_avance"] += 1
                slot["total_gramos"] += g
                slot["total_efectivo"] += e
                slot["trabajadores"].add(f"{r.get('nombre')} ({r.get('ubic')})")
                if r.get("material"):
                    slot["materiales"].add(str(r.get("material")))
                if r.get("modelo"):
                    slot["modelos"].add(str(r.get("modelo")))
                slot["semanas"].add(s.get("codigo") or str(sid))
                if fi and (slot["inicio"] is None or fi < slot["inicio"]):
                    slot["inicio"] = fi
        out = []
        for slot in agg.values():
            out.append({
                "folio": slot["folio"],
                "total_gramos": round(slot["total_gramos"], 1),
                "total_efectivo": round(slot["total_efectivo"], 2),
                "n_semanas": len(slot["semanas"]),
                "trabajadores": sorted(slot["trabajadores"])[:8],
                "materiales": sorted(slot["materiales"]),
                "modelos": sorted(slot["modelos"])[:6],
                "inicio": fecha_es(slot["inicio"]) if slot["inicio"] else "—",
                "dias_con_avance": slot["dias_con_avance"],
            })
        out.sort(key=lambda x: (-x["total_gramos"], x["folio"]))
        return out[:limit]

    def stats_diario(
        self,
        q: str = "",
        semana_ids: list[int] | None = None,
        fecha_desde: date | None = None,
        fecha_hasta: date | None = None,
        agrupar: str = "dia",  # dia | trabajador | folio
        limit: int = 120,
    ) -> list[dict]:
        """Desglose por día calendario (gramos/$), opcionalmente filtrado."""
        ref = today_fn()
        if not fecha_desde and not fecha_hasta and not semana_ids:
            fecha_hasta = ref
            fecha_desde = ref - timedelta(days=13)
        semanas = self._semanas_filtradas(semana_ids, fecha_desde, fecha_hasta)
        # key -> slot
        agg: dict[Any, dict] = {}
        for s in semanas:
            sid = int(s["id"])
            fi = parse_fecha(s.get("fecha_inicio"))
            if not fi:
                continue
            try:
                rows = self.prod.listar_por_semana(sid, incluir_terminados=True)
            except Exception:
                continue
            for r in rows:
                nombre = str(r.get("nombre") or "").strip()
                folio = str(r.get("folio") or "").strip()
                if q:
                    ql = q.lower()
                    if ql not in nombre.lower() and ql not in folio.lower() and ql not in str(r.get("ubic") or ""):
                        continue
                tarifa = float(r.get("tarifa_gr") or 0)
                for i, col in enumerate(_DAY_COLS):
                    d = fi + timedelta(days=i)
                    if fecha_desde and d < fecha_desde:
                        continue
                    if fecha_hasta and d > fecha_hasta:
                        continue
                    g = float(r.get(col) or 0)
                    if g <= 0:
                        continue
                    e = g * tarifa if tarifa else float(r.get("efectivo") or 0) * (
                        g / float(r.get("total_gramos") or g or 1)
                    )
                    if agrupar == "trabajador":
                        key = (d.isoformat(), nombre.upper(), int(r.get("ubic") or 0))
                        label = nombre
                    elif agrupar == "folio":
                        key = (d.isoformat(), folio.upper() or "—")
                        label = folio or "—"
                    else:
                        key = d.isoformat()
                        label = fecha_es(d) or d.isoformat()
                    slot = agg.setdefault(key, {
                        "fecha": d.isoformat(),
                        "fecha_label": fecha_es(d) or d.isoformat(),
                        "dia_semana": _DAY_LABELS.get(col, col),
                        "label": label,
                        "nombre": nombre if agrupar == "trabajador" else None,
                        "ubic": int(r.get("ubic") or 0) if agrupar == "trabajador" else None,
                        "folio": folio if agrupar == "folio" else None,
                        "total_gramos": 0.0,
                        "total_efectivo": 0.0,
                        "n_lineas": 0,
                    })
                    slot["total_gramos"] += g
                    slot["total_efectivo"] += e
                    slot["n_lineas"] += 1
        out = []
        for slot in agg.values():
            out.append({
                **{k: v for k, v in slot.items() if k != "label"},
                "label": slot["label"],
                "total_gramos": round(slot["total_gramos"], 1),
                "total_efectivo": round(slot["total_efectivo"], 2),
            })
        out.sort(key=lambda x: (x["fecha"], x.get("label") or ""))
        return out[:limit]

    @staticmethod
    def _sum_dias_rango(
        row: dict,
        semana: dict,
        fecha_desde: date | None,
        fecha_hasta: date | None,
    ) -> tuple[float, float, int]:
        fi = parse_fecha(semana.get("fecha_inicio"))
        if not fi:
            return float(row.get("total_gramos") or 0), float(row.get("efectivo") or 0), 0
        tarifa = float(row.get("tarifa_gr") or 0)
        gsum = 0.0
        n = 0
        for i, col in enumerate(_DAY_COLS):
            d = fi + timedelta(days=i)
            if fecha_desde and d < fecha_desde:
                continue
            if fecha_hasta and d > fecha_hasta:
                continue
            g = float(row.get(col) or 0)
            if g > 0:
                gsum += g
                n += 1
        esum = gsum * tarifa if tarifa else 0.0
        return gsum, esum, n
