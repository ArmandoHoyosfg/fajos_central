"""Estadísticas históricas por trabajador y folio."""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.db.connection import get_db
from app.db.repository import SemanasRepo, ProduccionRepo
from app.utils.fechas_nomina import parse_fecha, fecha_es


class StatsService:
    def __init__(self, db=None):
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.prod = ProduccionRepo(self.db)

    def listar_semanas(self) -> list[dict]:
        return self.semanas.listar() or []

    def stats_trabajador(
        self,
        q: str = "",
        semana_ids: list[int] | None = None,
        limit: int = 80,
    ) -> list[dict]:
        """Agrega gramos y $ por trabajador en semanas seleccionadas (o todas)."""
        semanas = self.listar_semanas()
        if semana_ids:
            want = set(int(x) for x in semana_ids)
            semanas = [s for s in semanas if int(s["id"]) in want]
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
                })
                g = float(r.get("total_gramos") or 0)
                e = float(r.get("efectivo") or 0)
                slot["total_gramos"] += g
                slot["total_efectivo"] += e
                slot["semanas"].add(s.get("codigo") or str(sid))
                folio = (r.get("folio") or "").strip()
                if folio:
                    slot["folios"].add(folio)
                fi = parse_fecha(s.get("fecha_inicio"))
                if fi:
                    if slot["primera"] is None or fi < slot["primera"]:
                        slot["primera"] = fi
                    if slot["ultima"] is None or fi > slot["ultima"]:
                        slot["ultima"] = fi
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
            })
        out.sort(key=lambda x: (-x["total_efectivo"], x["nombre"]))
        return out[:limit]

    def stats_folio(
        self,
        q: str = "",
        semana_ids: list[int] | None = None,
        limit: int = 80,
    ) -> list[dict]:
        semanas = self.listar_semanas()
        if semana_ids:
            want = set(int(x) for x in semana_ids)
            semanas = [s for s in semanas if int(s["id"]) in want]
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
                })
                slot["total_gramos"] += float(r.get("total_gramos") or 0)
                slot["total_efectivo"] += float(r.get("efectivo") or 0)
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
            })
        out.sort(key=lambda x: (-x["total_gramos"], x["folio"]))
        return out[:limit]
