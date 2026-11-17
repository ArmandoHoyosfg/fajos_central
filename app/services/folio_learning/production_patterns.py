"""Patrones reales de produccion_plata: precio y modelo cuando faltan datos."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.connection import get_db


class ProductionPatterns:
    """Aprende de líneas con gramos > 0 (ignora filas vacías por duplicar semana)."""

    def __init__(self, db=None):
        self.db = db or get_db()

    def tarifa_por_material(
        self,
        material: str,
        modelo: str | None = None,
        limit: int = 120,
    ) -> dict[str, Any] | None:
        material = (material or "").strip()
        if not material:
            return None
        modelo = (modelo or "").strip() or None
        rows: list[float] = []
        fuente = "produccion"
        try:
            with self.db.cursor() as cur:
                if modelo:
                    cur.execute(
                        """
                        SELECT tarifa_gr FROM produccion_plata
                        WHERE UPPER(TRIM(material)) = UPPER(%s)
                          AND UPPER(TRIM(COALESCE(modelo,''))) = UPPER(%s)
                          AND tarifa_gr IS NOT NULL
                          AND COALESCE(total_gramos, 0) > 0
                        ORDER BY id DESC LIMIT %s
                        """,
                        (material, modelo, int(limit)),
                    )
                    rows = [
                        float(r["tarifa_gr"])
                        for r in (cur.fetchall() or [])
                        if r.get("tarifa_gr") is not None
                    ]
                    if rows:
                        fuente = "produccion_modelo"
                if not rows:
                    cur.execute(
                        """
                        SELECT tarifa_gr FROM produccion_plata
                        WHERE UPPER(TRIM(material)) = UPPER(%s)
                          AND tarifa_gr IS NOT NULL
                          AND COALESCE(total_gramos, 0) > 0
                        ORDER BY id DESC LIMIT %s
                        """,
                        (material, int(limit)),
                    )
                    rows = [
                        float(r["tarifa_gr"])
                        for r in (cur.fetchall() or [])
                        if r.get("tarifa_gr") is not None
                    ]
                    if rows:
                        fuente = "produccion_material"
        except Exception:
            return None
        if not rows:
            return None
        rounded = [round(x, 2) for x in rows]
        cnt = Counter(rounded)
        moda, n_moda = cnt.most_common(1)[0]
        conf = round(n_moda / len(rounded), 2)
        return {
            "tarifa_gr": float(moda),
            "confianza": conf,
            "muestras": len(rounded),
            "veces_moda": n_moda,
            "fuente": fuente,
            "detalle": (
                f"${moda:g}/g en {n_moda}/{len(rounded)} capturas "
                f"con gramos ({int(conf * 100)}%)"
                + (f" · modelo {modelo}" if modelo and fuente == "produccion_modelo" else "")
            ),
            "alternativas": [
                {"tarifa_gr": float(t), "veces": c} for t, c in cnt.most_common(3)
            ],
        }

    def modelos_por_material(self, material: str, limit: int = 5) -> list[dict]:
        """Modelos más usados con este material (solo filas con modelo y gramos)."""
        material = (material or "").strip()
        if not material:
            return []
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT TRIM(modelo) AS modelo, COUNT(*) AS n
                    FROM produccion_plata
                    WHERE UPPER(TRIM(material)) = UPPER(%s)
                      AND modelo IS NOT NULL AND TRIM(modelo) <> ''
                      AND COALESCE(total_gramos, 0) > 0
                    GROUP BY TRIM(modelo)
                    ORDER BY n DESC
                    LIMIT %s
                    """,
                    (material, int(limit)),
                )
                rows = cur.fetchall() or []
        except Exception:
            return []
        total = sum(int(r.get("n") or 0) for r in rows) or 1
        out = []
        for r in rows:
            n = int(r.get("n") or 0)
            out.append({
                "modelo": r.get("modelo"),
                "veces": n,
                "confianza": round(n / total, 2),
            })
        return out

    def meta_folio_completa(self, folio: str) -> dict[str, Any] | None:
        """Última línea del folio con datos útiles; prioriza la que tenga modelo."""
        folio = (folio or "").strip()
        if not folio:
            return None
        try:
            with self.db.cursor() as cur:
                # Preferir fila con modelo no vacío
                cur.execute(
                    """
                    SELECT modelo, material, tarifa_gr, total_gramos
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) = UPPER(%s)
                      AND COALESCE(total_gramos, 0) > 0
                    ORDER BY
                      CASE WHEN modelo IS NOT NULL AND TRIM(modelo) <> '' THEN 0 ELSE 1 END,
                      id DESC
                    LIMIT 1
                    """,
                    (folio,),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT modelo, material, tarifa_gr, total_gramos
                        FROM produccion_plata
                        WHERE UPPER(TRIM(folio)) = UPPER(%s)
                        ORDER BY
                          CASE WHEN modelo IS NOT NULL AND TRIM(modelo) <> '' THEN 0 ELSE 1 END,
                          id DESC
                        LIMIT 1
                        """,
                        (folio,),
                    )
                    row = cur.fetchone()
        except Exception:
            return None
        if not row:
            return None
        return {
            "modelo": (row.get("modelo") or "").strip() or None,
            "material": (row.get("material") or "").strip() or None,
            "tarifa_gr": float(row["tarifa_gr"]) if row.get("tarifa_gr") is not None else None,
            "fuente": "folio_historial",
        }

    def ultimo_del_trabajador(
        self,
        *,
        trabajador_id: int | None = None,
        nombre: str | None = None,
        ubic: int | None = None,
    ) -> dict[str, Any] | None:
        try:
            with self.db.cursor() as cur:
                if trabajador_id:
                    cur.execute(
                        """
                        SELECT modelo, material, tarifa_gr
                        FROM produccion_plata
                        WHERE trabajador_id = %s
                          AND COALESCE(total_gramos, 0) > 0
                        ORDER BY id DESC LIMIT 1
                        """,
                        (int(trabajador_id),),
                    )
                elif nombre is not None:
                    cur.execute(
                        """
                        SELECT modelo, material, tarifa_gr
                        FROM produccion_plata
                        WHERE UPPER(TRIM(nombre)) = UPPER(%s)
                          AND (%s IS NULL OR ubic = %s)
                          AND COALESCE(total_gramos, 0) > 0
                        ORDER BY id DESC LIMIT 1
                        """,
                        (nombre, ubic, ubic),
                    )
                else:
                    return None
                row = cur.fetchone()
        except Exception:
            return None
        if not row:
            return None
        return {
            "modelo": (row.get("modelo") or "").strip() or None,
            "material": (row.get("material") or "").strip() or None,
            "tarifa_gr": float(row["tarifa_gr"]) if row.get("tarifa_gr") is not None else None,
            "fuente": "trabajador_reciente",
        }
