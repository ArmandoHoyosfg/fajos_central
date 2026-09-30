"""
Repositorios de acceso a datos.

La implementación vive en app.db.repos.* (un archivo por dominio).
Este módulo reexporta las clases para no romper imports existentes:
  from app.db.repository import ProduccionRepo, TrabajadoresRepo, ...
"""
from __future__ import annotations

from app.db.repos import (  # noqa: F401
    BaseRepo,
    CatalogosRepo,
    DashboardRepo,
    HistorialPreciosRepo,
    NominaTallerRepo,
    ProduccionPitaRepo,
    ProduccionRepo,
    ResumenRepo,
    SemanasRepo,
    TrabajadoresRepo,
    TrabajosRepo,
    _parse_fecha_sql,
)

__all__ = [
    "BaseRepo",
    "CatalogosRepo",
    "DashboardRepo",
    "HistorialPreciosRepo",
    "NominaTallerRepo",
    "ProduccionPitaRepo",
    "ProduccionRepo",
    "ResumenRepo",
    "SemanasRepo",
    "TrabajadoresRepo",
    "TrabajosRepo",
    "_parse_fecha_sql",
]
