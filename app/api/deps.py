"""Dependencias FastAPI."""
from app.db.connection import Database, get_db
from app.db.repository import (
    DashboardRepo,
    ProduccionRepo,
    ProduccionPitaRepo,
    NominaTallerRepo,
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

    from app.core.network import lan_urls, local_ip
    from app.core.config import get_settings
    try:
        settings = get_settings()
        port = int(getattr(settings, "app_port", 8000) or 8000)
        https = bool(getattr(settings, "force_https", False))
    except Exception:
        port, https = 8000, False
    urls = lan_urls(port=port, https=https)
    ctx = {
        "fecha_hoy": today(),
        "fecha_hoy_larga": format_fecha_larga(),
        "fecha_hoy_corta": format_fecha_corta(),
        "app_version": __version__,
        "db_ok": check_db(),
        "lan_ip": urls["ip"],
        "lan_url": urls["lan"],
        "local_url": urls["local"],
        "app_port": port,
    }
    if extra:
        ctx.update(extra)
    return ctx


def get_nomina_taller_repo() -> NominaTallerRepo:
    return NominaTallerRepo()


def get_produccion_pita_repo() -> ProduccionPitaRepo:
    return ProduccionPitaRepo()


def get_insights_service():
    from app.services.insights_service import InsightsService
    return InsightsService()


def get_trabajos_repo():
    from app.db.repository import TrabajosRepo
    return TrabajosRepo()
