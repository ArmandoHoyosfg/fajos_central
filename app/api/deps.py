"""Dependencias FastAPI."""
from app.db.connection import Database, get_db
from app.db.repository import (
    DashboardRepo,
    ProduccionRepo,
    ResumenRepo,
    SemanasRepo,
    TrabajadoresRepo,
)
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService


def get_database() -> Database:
    return get_db()


def get_trabajadores_repo() -> TrabajadoresRepo:
    return TrabajadoresRepo()


def get_semanas_repo() -> SemanasRepo:
    return SemanasRepo()


def get_produccion_repo() -> ProduccionRepo:
    return ProduccionRepo()


def get_resumen_repo() -> ResumenRepo:
    return ResumenRepo()


def get_dashboard_service() -> DashboardService:
    return DashboardService()


def get_export_service() -> ExportService:
    return ExportService()


def common_template_context(extra: dict | None = None) -> dict:
    """Contexto compartido web/desktop parity: fecha, versión, semana actual flags."""
    from app import __version__
    from app.core.calendar_util import format_fecha_corta, format_fecha_larga, today
    from app.services.dashboard_service import check_db

    ctx = {
        "fecha_hoy": today(),
        "fecha_hoy_larga": format_fecha_larga(),
        "fecha_hoy_corta": format_fecha_corta(),
        "app_version": __version__,
        "db_ok": check_db(),
    }
    if extra:
        ctx.update(extra)
    return ctx
