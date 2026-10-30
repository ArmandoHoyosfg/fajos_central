"""Hábitos recientes de un trabajador (folios, materiales, tarifas)."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.connection import get_db


class WorkerHistory:
    def __init__(self, db=None):
        self.db = db or get_db()

    def resumen(
        self,
        trabajador_id: int | None = None,
        nombre: str | None = None,
        ubic: int | None = None,
        limit: int = 12,
    ) -> dict[str, Any]:
        if not trabajador_id and not nombre:
            return {"ok": False, "lineas": [], "materiales": [], "modelos": []}
        with self.db.cursor() as cur:
            if trabajador_id:
                cur.execute(
                    """
                    SELECT folio, material, modelo, tarifa_gr, semana_id, nombre, ubic
                    FROM produccion_plata
                    WHERE trabajador_id = %s
                    ORDER BY id DESC LIMIT %s
                    """,
                    (int(trabajador_id), int(limit) * 3),
                )
            else:
                cur.execute(
                    """
                    SELECT folio, material, modelo, tarifa_gr, semana_id, nombre, ubic
                    FROM produccion_plata
                    WHERE UPPER(TRIM(nombre)) = UPPER(%s)
                      AND (%s IS NULL OR ubic = %s)
                    ORDER BY id DESC LIMIT %s
                    """,
                    (nombre, ubic, ubic, int(limit) * 3),
                )
            rows = [dict(r) for r in (cur.fetchall() or [])]
        mats = Counter(str(r.get("material") or "").strip().upper() for r in rows if r.get("material"))
        mods = Counter(str(r.get("modelo") or "").strip() for r in rows if r.get("modelo"))
        folios = []
        seen = set()
        for r in rows:
            f = str(r.get("folio") or "").strip()
            if not f or f.upper() in seen:
                continue
            seen.add(f.upper())
            folios.append({
                "folio": f,
                "material": r.get("material"),
                "modelo": r.get("modelo"),
                "tarifa_gr": float(r["tarifa_gr"]) if r.get("tarifa_gr") is not None else None,
            })
        top_mat = mats.most_common(1)[0][0] if mats else None
        top_mod = mods.most_common(1)[0][0] if mods else None
        return {
            "ok": True,
            "folios_recientes": folios[:limit],
            "material_habitual": top_mat,
            "modelo_habitual": top_mod,
            "materiales": [{"material": m, "veces": c} for m, c in mats.most_common(5)],
            "modelos": [{"modelo": m, "veces": c} for m, c in mods.most_common(5)],
            "muestras": len(rows),
        }
