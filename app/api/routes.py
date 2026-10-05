"""
Rutas API REST + páginas web.

La implementación vive en app.api.routers.* (por dominio).
Este módulo reexporta el router agregado para no romper:
  from app.api.routes import router
"""
from __future__ import annotations

from app.api.routers import router
from app.api.helpers import templates, _ctx, get_catalogos_repo  # noqa: F401

__all__ = ["router", "templates", "_ctx", "get_catalogos_repo"]
