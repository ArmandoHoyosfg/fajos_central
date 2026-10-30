"""Precio sugerido con moda y nivel de confianza (no solo el último valor)."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.connection import get_db


class PriceConfidence:
    def __init__(self, db=None):
        self.db = db or get_db()

    def sugerir(self, material: str, modelo: str | None = None, limit: int = 40) -> dict[str, Any] | None:
        material = (material or "").strip()
        if not material:
            return None
        modelo = (modelo or "").strip() or None
        rows: list[float] = []
        fuente = "historial"
        with self.db.cursor() as cur:
            if modelo:
                try:
                    cur.execute(
                        """
                        SELECT tarifa_gr FROM historial_precios
                        WHERE material=%s AND modelo=%s
                        ORDER BY id DESC LIMIT %s
                        """,
                        (material, modelo, int(limit)),
                    )
                    rows = [float(r["tarifa_gr"]) for r in (cur.fetchall() or []) if r.get("tarifa_gr") is not None]
                    if rows:
                        fuente = "historial_modelo"
                except Exception:
                    rows = []
            if not rows:
                try:
                    cur.execute(
                        """
                        SELECT tarifa_gr FROM historial_precios
                        WHERE material=%s
                        ORDER BY id DESC LIMIT %s
                        """,
                        (material, int(limit)),
                    )
                    rows = [float(r["tarifa_gr"]) for r in (cur.fetchall() or []) if r.get("tarifa_gr") is not None]
                    if rows:
                        fuente = "historial_material"
                except Exception:
                    rows = []
            # Fallback producción real
            if not rows:
                cur.execute(
                    """
                    SELECT tarifa_gr FROM produccion_plata
                    WHERE UPPER(TRIM(material)) = UPPER(%s)
                      AND tarifa_gr IS NOT NULL
                    ORDER BY id DESC LIMIT %s
                    """,
                    (material, int(limit)),
                )
                rows = [float(r["tarifa_gr"]) for r in (cur.fetchall() or []) if r.get("tarifa_gr") is not None]
                if rows:
                    fuente = "produccion"
        if not rows:
            return None
        rounded = [round(x, 2) for x in rows]
        cnt = Counter(rounded)
        moda, n_moda = cnt.most_common(1)[0]
        confianza = round(n_moda / len(rounded), 2)
        return {
            "tarifa_gr": float(moda),
            "confianza": confianza,
            "muestras": len(rounded),
            "veces_moda": n_moda,
            "fuente": fuente,
            "detalle": f"${moda:g} en {n_moda}/{len(rounded)} usos ({int(confianza*100)}%)",
            "alternativas": [
                {"tarifa_gr": float(t), "veces": c}
                for t, c in cnt.most_common(3)
            ],
        }
