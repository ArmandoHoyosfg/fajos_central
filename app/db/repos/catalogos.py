"""Repositorio: CatalogosRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class CatalogosRepo:
    """Catálogos: tarifas_material y modelos (fuente de verdad en BD)."""

    def __init__(self, db=None) -> None:
        self.db = db or get_db()

    def listar_materiales(self, solo_activos: bool = True) -> list[dict]:
        sql = "SELECT id, material, tarifa_por_gramo, descripcion, activo FROM tarifas_material"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY material"
        try:
            with self.db.cursor() as cur:
                cur.execute(sql)
                return list(cur.fetchall() or [])
        except Exception:
            return []

    def upsert_material(
        self,
        material: str,
        tarifa_por_gramo: float,
        descripcion: str | None = None,
        activo: int = 1,
        mat_id: int | None = None,
    ) -> dict:
        material = (material or "").strip().upper()
        if not material:
            raise ValueError("Material vacío")
        with self.db.cursor() as cur:
            if mat_id:
                cur.execute(
                    """
                    UPDATE tarifas_material
                       SET material=%s, tarifa_por_gramo=%s, descripcion=%s, activo=%s
                     WHERE id=%s
                    """,
                    (material, tarifa_por_gramo, descripcion, int(bool(activo)), mat_id),
                )
                return {"id": mat_id, "ok": True}
            cur.execute(
                """
                INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion, activo)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  tarifa_por_gramo = VALUES(tarifa_por_gramo),
                  descripcion = VALUES(descripcion),
                  activo = VALUES(activo)
                """,
                (material, tarifa_por_gramo, descripcion, int(bool(activo))),
            )
            cur.execute("SELECT id FROM tarifas_material WHERE material=%s", (material,))
            row = cur.fetchone() or {}
            return {"id": row.get("id"), "ok": True}

    def set_material_activo(self, mat_id: int, activo: bool) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE tarifas_material SET activo=%s WHERE id=%s",
                (1 if activo else 0, mat_id),
            )

    def listar_modelos(self, tipo: str | None = None) -> list[dict]:
        sql = "SELECT id, modelo, tipo, material_default, tarifa_default, notas FROM modelos"
        params: tuple = ()
        if tipo:
            sql += " WHERE tipo=%s"
            params = (tipo,)
        sql += " ORDER BY tipo, modelo"
        try:
            with self.db.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall() or [])
        except Exception:
            return []

    def upsert_modelo(
        self,
        modelo: str,
        tipo: str = "PLT",
        material_default: str | None = None,
        tarifa_default: float | None = None,
        notas: str | None = None,
        modelo_id: int | None = None,
    ) -> dict:
        modelo = (modelo or "").strip().upper()
        tipo = (tipo or "PLT").strip().upper()
        if not modelo:
            raise ValueError("Modelo vacío")
        with self.db.cursor() as cur:
            if modelo_id:
                cur.execute(
                    """
                    UPDATE modelos
                       SET modelo=%s, tipo=%s, material_default=%s, tarifa_default=%s, notas=%s
                     WHERE id=%s
                    """,
                    (modelo, tipo, material_default, tarifa_default, notas, modelo_id),
                )
                return {"id": modelo_id, "ok": True}
            cur.execute(
                """
                INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  material_default = VALUES(material_default),
                  tarifa_default = VALUES(tarifa_default),
                  notas = VALUES(notas)
                """,
                (modelo, tipo, material_default, tarifa_default, notas),
            )
            cur.execute(
                "SELECT id FROM modelos WHERE modelo=%s AND tipo=%s",
                (modelo, tipo),
            )
            row = cur.fetchone() or {}
            return {"id": row.get("id"), "ok": True}

    def eliminar_modelo(self, modelo_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM modelos WHERE id=%s", (modelo_id,))

    def materiales_nombres(self, solo_activos: bool = True) -> list[str]:
        return [str(m["material"]) for m in self.listar_materiales(solo_activos=solo_activos) if m.get("material")]

    def tarifa_de(self, material: str) -> float | None:
        material = (material or "").strip().upper()
        if not material:
            return None
        for m in self.listar_materiales(solo_activos=False):
            if str(m.get("material") or "").upper() == material:
                try:
                    return float(m.get("tarifa_por_gramo") or 0)
                except (TypeError, ValueError):
                    return None
        return None


