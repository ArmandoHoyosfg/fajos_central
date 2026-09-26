"""Router: catalogos."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from app.api.deps import (
    common_template_context,
    get_dashboard_service,
    get_export_service,
    get_insights_service,
    get_produccion_repo,
    get_produccion_pita_repo,
    get_nomina_taller_repo,
    get_semanas_repo,
    get_trabajadores_repo,
    get_trabajos_repo,
)
from app.api.helpers import (
    templates,
    _ctx,
    get_catalogos_repo,
    _dev_page_payload,
    _parse_num,
)
from app.core.exceptions import AppError
from app.db.repository import (
    ProduccionRepo,
    ProduccionPitaRepo,
    NominaTallerRepo,
    SemanasRepo,
    TrabajadoresRepo,
    TrabajosRepo,
    CatalogosRepo,
)
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService, linea_tiene_gramos

router = APIRouter()

@router.get("/catalogos", response_class=HTMLResponse)
async def page_catalogos(request: Request):
    from app.db.repository import CatalogosRepo
    cat = CatalogosRepo()
    materiales = cat.listar_materiales(solo_activos=False)
    modelos = cat.listar_modelos()
    return templates.TemplateResponse(
        request,
        "catalogos.html",
        _ctx(request, materiales=materiales, modelos=modelos),
    )



@router.post("/api/catalogos/material")
async def api_catalogo_material(
    material: str = Form(...),
    tarifa_por_gramo: float = Form(...),
    descripcion: str | None = Form(None),
    activo: int = Form(1),
    mat_id: int | None = Form(None),
):
    from fastapi.responses import JSONResponse
    from app.db.repository import CatalogosRepo
    try:
        r = CatalogosRepo().upsert_material(
            material=material,
            tarifa_por_gramo=tarifa_por_gramo,
            descripcion=descripcion,
            activo=activo,
            mat_id=mat_id,
        )
        return r
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)



@router.post("/api/catalogos/material/{mat_id}/activo")
async def api_catalogo_material_activo(mat_id: int, activo: int = Form(...)):
    from app.db.repository import CatalogosRepo
    CatalogosRepo().set_material_activo(mat_id, bool(activo))
    return {"ok": True}



@router.post("/api/catalogos/modelo")
async def api_catalogo_modelo(
    modelo: str = Form(...),
    tipo: str = Form("PLT"),
    material_default: str | None = Form(None),
    tarifa_default: float | None = Form(None),
    notas: str | None = Form(None),
    modelo_id: int | None = Form(None),
):
    from fastapi.responses import JSONResponse
    from app.db.repository import CatalogosRepo
    try:
        return CatalogosRepo().upsert_modelo(
            modelo=modelo,
            tipo=tipo,
            material_default=material_default,
            tarifa_default=tarifa_default,
            notas=notas,
            modelo_id=modelo_id,
        )
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)



@router.delete("/api/catalogos/modelo/{modelo_id}")
async def api_catalogo_modelo_del(modelo_id: int):
    from app.db.repository import CatalogosRepo
    CatalogosRepo().eliminar_modelo(modelo_id)
    return {"ok": True}



@router.get("/api/catalogos/materiales")
async def api_catalogos_materiales():
    from app.db.repository import CatalogosRepo
    return CatalogosRepo().listar_materiales(solo_activos=True)
