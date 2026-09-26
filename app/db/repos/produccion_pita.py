"""Repositorio: ProduccionPitaRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class ProduccionPitaRepo(BaseRepo):
    """Nómina Pita: modelo/folio/material PITA NxN + efectivo."""

    def listar_por_semana(self, semana_id: int, **_kwargs) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.semana_id, p.trabajador_id,
                       COALESCE(tr.nombre_mostrar, p.nombre) AS nombre,
                       COALESCE(tr.ubic, p.ubic) AS ubic,
                       p.modelo, p.folio, p.material, p.producto, p.pitas, p.efectivo,
                       p.firmado, p.notas
                FROM produccion_pita p
                LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
                WHERE p.semana_id = %s
                ORDER BY COALESCE(tr.ubic, p.ubic), COALESCE(tr.nombre_mostrar, p.nombre)
                """,
                (semana_id,),
            )
            return list(cur.fetchall() or [])

    def totales(self, semana_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS lineas,
                       COALESCE(SUM(pitas),0) AS sum_pitas,
                       COALESCE(SUM(efectivo),0) AS total
                FROM produccion_pita WHERE semana_id = %s
                """,
                (semana_id,),
            )
            return cur.fetchone() or {}

    def insertar(self, semana_id: int, data: dict) -> int:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO produccion_pita
                  (semana_id, trabajador_id, nombre, ubic, modelo, folio, material,
                   producto, pitas, efectivo, firmado, notas)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    semana_id,
                    data.get("trabajador_id"),
                    data["nombre"],
                    data["ubic"],
                    data.get("modelo"),
                    data.get("folio"),
                    data.get("material"),
                    data.get("producto") or "Cinturón",
                    data.get("pitas"),
                    float(data.get("efectivo") or 0),
                    1 if data.get("firmado") else 0,
                    data.get("notas"),
                ),
            )
            return cur.lastrowid

    def actualizar(self, row_id: int, data: dict) -> None:
        fields = []
        params: list = []
        for k in (
            "nombre", "ubic", "modelo", "folio", "material", "producto",
            "pitas", "efectivo", "firmado", "notas", "trabajador_id",
        ):
            if k in data:
                fields.append(f"{k}=%s")
                params.append(data[k])
        if not fields:
            return
        params.append(row_id)
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE produccion_pita SET {', '.join(fields)} WHERE id=%s", params)

    def eliminar(self, row_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM produccion_pita WHERE id=%s", (row_id,))


