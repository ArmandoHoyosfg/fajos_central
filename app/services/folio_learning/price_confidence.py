"""Precio sugerido: producción real (moda) → historial → fallback."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.connection import get_db
from app.services.folio_learning.production_patterns import ProductionPatterns


class PriceConfidence:
    def __init__(self, db=None):
        self.db = db or get_db()
        self.prod = ProductionPatterns(self.db)

    def sugerir(self, material: str, modelo: str | None = None, limit: int = 80) -> dict[str, Any] | None:
        material = (material or "").strip()
        if not material:
            return None
        modelo = (modelo or "").strip() or None

        # 1) Producción con gramos (más fiable que historial de un solo insert)
        prod = self.prod.tarifa_por_material(material, modelo, limit=limit)
        if prod and prod.get("confianza", 0) >= 0.4:
            return prod

        # 2) Historial de precios
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
                    rows = [
                        float(r["tarifa_gr"])
                        for r in (cur.fetchall() or [])
                        if r.get("tarifa_gr") is not None
                    ]
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
                    rows = [
                        float(r["tarifa_gr"])
                        for r in (cur.fetchall() or [])
                        if r.get("tarifa_gr") is not None
                    ]
                    if rows:
                        fuente = "historial_material"
                except Exception:
                    rows = []

        if not rows and prod:
            return prod  # aunque confianza < 0.4
        if not rows:
            return prod

        rounded = [round(x, 2) for x in rows]
        cnt = Counter(rounded)
        moda, n_moda = cnt.most_common(1)[0]
        confianza = round(n_moda / len(rounded), 2)
        hist = {
            "tarifa_gr": float(moda),
            "confianza": confianza,
            "muestras": len(rounded),
            "veces_moda": n_moda,
            "fuente": fuente,
            "detalle": f"${moda:g} en {n_moda}/{len(rounded)} usos historial ({int(confianza*100)}%)",
            "alternativas": [
                {"tarifa_gr": float(t), "veces": c} for t, c in cnt.most_common(3)
            ],
        }
        # Si producción tiene más muestras o igual moda, preferirla
        if prod and prod.get("muestras", 0) >= hist["muestras"]:
            return prod
        return hist
