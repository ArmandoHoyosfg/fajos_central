"""Tarifas por material desde la base de datos."""
from __future__ import annotations

from app.db.connection import Database, get_db
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Fallback si BD no disponible
FALLBACK = {"AG3": 12.0, "AG4": 13.0, "DOL": 13.0, "DLO": 13.0}


class TarifasService:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()
        self._cache: dict[str, float] | None = None

    def mapa(self, force: bool = False) -> dict[str, float]:
        if self._cache is not None and not force:
            return self._cache
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT material, tarifa_por_gramo FROM tarifas_material WHERE activo = 1"
                )
                rows = cur.fetchall() or []
            m = {
                str(r["material"]).upper(): float(r["tarifa_por_gramo"])
                for r in rows
                if r.get("material") is not None
            }
            if m:
                self._cache = m
                return m
        except Exception as e:
            logger.warning("tarifas desde BD no disponibles: %s", e)
        self._cache = dict(FALLBACK)
        return self._cache

    def tarifa(self, material: str | None) -> float:
        mat = (material or "AG3").strip().upper()
        return float(self.mapa().get(mat, FALLBACK.get(mat, 12.0)))
