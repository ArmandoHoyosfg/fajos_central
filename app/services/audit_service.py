"""Historial de cambios y comprobación de semana cerrada."""
from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db

logger = get_logger(__name__)


class AuditService:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def semana_cerrada(self, semana_id: int) -> bool:
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT cerrada FROM semanas WHERE id = %s",
                (semana_id,),
            )
            row = cur.fetchone()
        if not row:
            return False
        return bool(row.get("cerrada"))

    def assert_semana_abierta(self, semana_id: int) -> None:
        if self.semana_cerrada(semana_id):
            raise ValidationAppError(
                "La semana está cerrada. No se pueden modificar datos de producción.",
                details={"semana_id": semana_id},
            )

    def registrar(
        self,
        *,
        produccion_id: int,
        semana_id: int,
        campo: str,
        valor_anterior: Any,
        valor_nuevo: Any,
        origen: str = "app",
        usuario: str | None = None,
    ) -> None:
        def _s(v: Any) -> str | None:
            if v is None:
                return None
            return str(v)

        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO historial_produccion
                      (produccion_id, semana_id, campo, valor_anterior, valor_nuevo, origen, usuario)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        produccion_id,
                        semana_id,
                        campo,
                        _s(valor_anterior),
                        _s(valor_nuevo),
                        origen,
                        usuario,
                    ),
                )
        except Exception as e:
            # No bloquear el flujo de negocio si la tabla aún no existe
            logger.warning("No se pudo registrar historial: %s", e)

    def listar_por_semana(self, semana_id: int, limit: int = 100) -> list[dict]:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT h.*, p.nombre, p.ubic, p.folio
                    FROM historial_produccion h
                    LEFT JOIN produccion_plata p ON p.id = h.produccion_id
                    WHERE h.semana_id = %s
                    ORDER BY h.creado_en DESC
                    LIMIT %s
                    """,
                    (semana_id, limit),
                )
                return list(cur.fetchall() or [])
        except Exception as e:
            logger.warning("listar historial: %s", e)
            return []
