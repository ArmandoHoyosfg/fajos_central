"""Repositorios por dominio (capa de datos)."""
from __future__ import annotations

from app.db.repos.base import BaseRepo, _parse_fecha_sql
from app.db.repos.trabajadores import TrabajadoresRepo
from app.db.repos.semanas import SemanasRepo
from app.db.repos.produccion import ProduccionRepo
from app.db.repos.trabajos import TrabajosRepo
from app.db.repos.resumen import ResumenRepo
from app.db.repos.dashboard import DashboardRepo
from app.db.repos.nomina_taller import NominaTallerRepo
from app.db.repos.produccion_pita import ProduccionPitaRepo
from app.db.repos.catalogos import CatalogosRepo
from app.db.repos.historial_precios import HistorialPreciosRepo

__all__ = [
    "BaseRepo",
    "_parse_fecha_sql",
    "TrabajadoresRepo",
    "SemanasRepo",
    "ProduccionRepo",
    "TrabajosRepo",
    "ResumenRepo",
    "DashboardRepo",
    "NominaTallerRepo",
    "ProduccionPitaRepo",
    "CatalogosRepo",
    "HistorialPreciosRepo",
]
