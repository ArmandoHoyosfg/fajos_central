"""Repositorio: HistorialPreciosRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class HistorialPreciosRepo:
    """Guarda y consulta precios usados (material + modelo → tarifa)."""

    def __init__(self, db=None):
        from app.db.connection import get_db
        self.db = db or get_db()

    def ensure_table(self) -> None:
        sql = """
        CREATE TABLE IF NOT EXISTS historial_precios (
          id INT AUTO_INCREMENT PRIMARY KEY,
          material VARCHAR(64) NOT NULL,
          modelo VARCHAR(128) NULL,
          tarifa_gr DECIMAL(10,2) NOT NULL,
          fuente VARCHAR(32) DEFAULT 'captura',
          semana_id INT NULL,
          prod_id INT NULL,
          creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_hp_mat (material),
          INDEX idx_hp_mat_mod (material, modelo)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        try:
            with self.db.cursor() as cur:
                cur.execute(sql)
        except Exception:
            pass

    def registrar(
        self,
        material: str,
        tarifa_gr: float,
        modelo: str | None = None,
        *,
        fuente: str = "captura",
        semana_id: int | None = None,
        prod_id: int | None = None,
    ) -> None:
        material = (material or "").strip()
        if not material or tarifa_gr is None:
            return
        self.ensure_table()
        modelo = (modelo or "").strip() or None
        try:
            tarifa_gr = float(tarifa_gr)
        except (TypeError, ValueError):
            return
        # Evitar spam: si el último precio igual, no insertar
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT tarifa_gr FROM historial_precios
                WHERE material=%s AND IFNULL(modelo,'')=IFNULL(%s,'')
                ORDER BY id DESC LIMIT 1
                """,
                (material, modelo),
            )
            row = cur.fetchone()
            if row and abs(float(row.get("tarifa_gr") or 0) - tarifa_gr) < 0.001:
                return
            cur.execute(
                """
                INSERT INTO historial_precios
                  (material, modelo, tarifa_gr, fuente, semana_id, prod_id)
                VALUES (%s,%s,%s,%s,%s,%s)
                """,
                (material, modelo, tarifa_gr, fuente, semana_id, prod_id),
            )

    def sugerir(self, material: str, modelo: str | None = None) -> float | None:
        """Último precio conocido para material (+ modelo si hay)."""
        det = self.sugerir_detalle(material, modelo)
        return det.get("tarifa_gr") if det else None

    def sugerir_detalle(self, material: str, modelo: str | None = None) -> dict | None:
        """
        Predicción de precio: historial material+modelo → historial material → None.
        El catálogo de materiales lo aplica la capa superior si esto es None.
        """
        material = (material or "").strip()
        if not material:
            return None
        self.ensure_table()
        modelo = (modelo or "").strip() or None
        with self.db.cursor() as cur:
            if modelo:
                cur.execute(
                    """
                    SELECT tarifa_gr, modelo, fuente, creado_en FROM historial_precios
                    WHERE material=%s AND modelo=%s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (material, modelo),
                )
                row = cur.fetchone()
                if row:
                    return {
                        "tarifa_gr": float(row["tarifa_gr"]),
                        "fuente": "historial_modelo",
                        "modelo": row.get("modelo"),
                        "detalle": f"Último precio usado con modelo {modelo}",
                    }
            cur.execute(
                """
                SELECT tarifa_gr, modelo, fuente, creado_en FROM historial_precios
                WHERE material=%s
                ORDER BY id DESC LIMIT 1
                """,
                (material,),
            )
            row = cur.fetchone()
            if row:
                return {
                    "tarifa_gr": float(row["tarifa_gr"]),
                    "fuente": "historial_material",
                    "modelo": row.get("modelo"),
                    "detalle": "Último precio usado para este material",
                }
        return None

