"""Routers de la API/web."""
from __future__ import annotations
from fastapi import APIRouter

from app.api.routers.pages import router as pages_router
from app.api.routers.trabajadores import router as trabajadores_router
from app.api.routers.produccion import router as produccion_router
from app.api.routers.semanas import router as semanas_router
from app.api.routers.nominas import router as nominas_router
from app.api.routers.export import router as export_router
from app.api.routers.dev import router as dev_router
from app.api.routers.insights import router as insights_router
from app.api.routers.catalogos import router as catalogos_router

def build_api_router() -> APIRouter:
    root = APIRouter()
    root.include_router(pages_router)
    root.include_router(trabajadores_router)
    root.include_router(produccion_router)
    root.include_router(semanas_router)
    root.include_router(nominas_router)
    root.include_router(export_router)
    root.include_router(dev_router)
    root.include_router(insights_router)
    root.include_router(catalogos_router)
    return root

router = build_api_router()
