#!/usr/bin/env python3
"""Exporta una muestra ANÓNIMA de la BD para desarrollo (sin nombres reales).

Uso (desde la raíz del proyecto, con config BD):
  python scripts/export_muestra_anonima.py

Genera: exports/muestra_anonima.json
"""
from __future__ import annotations

import json
import hashlib
from datetime import date
from pathlib import Path

# bootstrap path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.connection import get_db  # noqa: E402


def _hash_id(v) -> str:
    return hashlib.sha256(str(v).encode("utf-8")).hexdigest()[:10]


def main() -> None:
    db = get_db()
    out: dict = {"generado": str(date.today()), "notas": "IDs hasheados; sin nombres"}
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT tipo, puesto, sueldo_modo,
                   COUNT(*) AS n,
                   SUM(CASE WHEN activo=1 THEN 1 ELSE 0 END) AS activos
            FROM trabajadores
            GROUP BY tipo, puesto, sueldo_modo
            """
        )
        out["trabajadores_por_tipo"] = list(cur.fetchall() or [])

        cur.execute(
            """
            SELECT id, codigo, fecha_inicio, fecha_fin, cerrada
            FROM semanas ORDER BY fecha_inicio DESC LIMIT 8
            """
        )
        out["semanas_recientes"] = list(cur.fetchall() or [])

        cur.execute(
            """
            SELECT semana_id,
                   COUNT(*) AS lineas,
                   SUM(CASE WHEN COALESCE(total_gramos,0)>0 THEN 1 ELSE 0 END) AS con_gramos,
                   ROUND(SUM(COALESCE(total_gramos,0)),1) AS gramos,
                   ROUND(SUM(COALESCE(efectivo,0)),2) AS efectivo
            FROM produccion_plata
            GROUP BY semana_id ORDER BY semana_id DESC LIMIT 8
            """
        )
        out["plata_por_semana"] = list(cur.fetchall() or [])

        cur.execute(
            """
            SELECT semana_id, COUNT(*) AS lineas,
                   ROUND(SUM(COALESCE(efectivo,0)),2) AS efectivo
            FROM produccion_pita
            GROUP BY semana_id ORDER BY semana_id DESC LIMIT 8
            """
        )
        out["pita_por_semana"] = list(cur.fetchall() or [])

        cur.execute(
            """
            SELECT semana_id, puesto,
                   COUNT(*) AS lineas,
                   ROUND(AVG(COALESCE(sueldo,0)),2) AS sueldo_prom,
                   ROUND(SUM(COALESCE(total,0)),2) AS total
            FROM nomina_taller
            GROUP BY semana_id, puesto
            ORDER BY semana_id DESC, puesto
            LIMIT 40
            """
        )
        out["taller_por_semana_puesto"] = list(cur.fetchall() or [])

        # Muestra de 15 filas plata sin nombre (solo hashes)
        cur.execute(
            """
            SELECT trabajador_id, ubic, material, modelo, tarifa_gr,
                   total_gramos, efectivo, semana_id
            FROM produccion_plata
            WHERE COALESCE(total_gramos,0) > 0
            ORDER BY id DESC LIMIT 15
            """
        )
        rows = []
        for r in cur.fetchall() or []:
            rows.append({
                "trabajador_hash": _hash_id(r.get("trabajador_id") or r.get("ubic")),
                "ubic": r.get("ubic"),
                "material": r.get("material"),
                "modelo": r.get("modelo"),
                "tarifa_gr": float(r["tarifa_gr"]) if r.get("tarifa_gr") is not None else None,
                "total_gramos": float(r.get("total_gramos") or 0),
                "efectivo": float(r.get("efectivo") or 0),
                "semana_id": r.get("semana_id"),
            })
        out["muestra_plata"] = rows

    dest = ROOT / "exports"
    dest.mkdir(exist_ok=True)
    path = dest / "muestra_anonima.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print("OK →", path)


if __name__ == "__main__":
    main()
