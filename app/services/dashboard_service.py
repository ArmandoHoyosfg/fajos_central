"""Servicio de dashboard."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger
from app.db.repository import DashboardRepo

logger = get_logger(__name__)


def _to_plain(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_plain(x) for x in obj]
    return obj


class DashboardService:
    def __init__(self, repo: DashboardRepo | None = None):
        self.repo = repo or DashboardRepo()

    def get_dashboard(self) -> dict:
        try:
            general = self.repo.resumen_general()
            semanas = self.repo.ultimas_semanas(8)
        except DatabaseError:
            raise
        except Exception as e:
            logger.exception("Dashboard DB error")
            raise DatabaseError(
                "No se pudieron cargar los datos del dashboard.",
                details={"hint": "Revisa config.ini y que MariaDB esté en marcha."},
                cause=e,
            ) from e

        return {
            "kpis": _to_plain(general),
            "ultimas_semanas": _to_plain(semanas),
        }
