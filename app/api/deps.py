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
