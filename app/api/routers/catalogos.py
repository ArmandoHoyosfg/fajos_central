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
    """Catálogos de materiales y modelos (asistencia a captura)."""
    from app.db.repository import CatalogosRepo, HistorialPreciosRepo
    cat = CatalogosRepo()
    materiales = cat.listar_materiales(solo_activos=False) or []
    modelos = cat.listar_modelos() or []
    # Último precio de historial por material (para mostrar en UI)
    hist_map: dict[str, float] = {}
    try:
        hp = HistorialPreciosRepo()
        for m in materiales:
            nom = str(m.get("material") or "").strip()
            if not nom:
                continue
            sug = hp.sugerir(nom, None)
            if sug is not None:
                hist_map[nom.upper()] = float(sug)
        # precio pita / torcedor
        pita = hp.sugerir("PITA", "torcedor")
        if pita is not None:
            hist_map["PITA"] = float(pita)
    except Exception:
        pass
    # Asegurar material PITA visible como tarifa de torcedores si no existe
    has_pita = any(str(m.get("material") or "").upper() == "PITA" for m in materiales)
    return templates.TemplateResponse(
        request,
        "catalogos.html",
        _ctx(
            request,
            materiales=materiales,
            modelos=modelos,
            hist_map=hist_map,
            has_pita=has_pita,
            precio_pita_sugerido=hist_map.get("PITA"),
        ),
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


@router.get("/api/catalogos/sugerir-tarifa")
async def api_sugerir_tarifa(
    material: str = Query(""),
    modelo: str = Query(""),
):
    """
    Predicción de $/g: catálogo de materiales → historial material+modelo → historial material.
    El cliente puede sobrescribir el valor en el mismo campo de texto.
    """
    material = (material or "").strip()
    modelo = (modelo or "").strip() or None
    out = {
        "ok": True,
        "material": material,
        "modelo": modelo,
        "tarifa_gr": None,
        "fuente": None,
        "detalle": None,
    }
    if not material:
        return out
    # 1) Catálogo
    try:
        from app.db.repository import CatalogosRepo
        mats = CatalogosRepo().listar_materiales(solo_activos=True) or []
        for m in mats:
            nom = str(m.get("nombre") or m.get("material") or "").strip()
            if nom.upper() == material.upper():
                t = m.get("tarifa_por_gramo")
                if t is None:
                    t = m.get("tarifa_gr")
                if t is not None and float(t) > 0:
                    out["tarifa_gr"] = float(t)
                    out["fuente"] = "catalogo"
                    out["detalle"] = f"Precio de catálogo ({nom})"
                    break
    except Exception:
        pass
    # 2) Historial (más específico gana si existe)
    try:
        from app.db.repository import HistorialPreciosRepo
        det = HistorialPreciosRepo().sugerir_detalle(material, modelo)
        if det and det.get("tarifa_gr") is not None:
            # Prefer historial de modelo si hay; si solo catálogo, historial material también aporta aprendizaje
            if det.get("fuente") == "historial_modelo" or out["tarifa_gr"] is None:
                out["tarifa_gr"] = float(det["tarifa_gr"])
                out["fuente"] = det.get("fuente")
                out["detalle"] = det.get("detalle")
            elif det.get("fuente") == "historial_material" and out.get("fuente") == "catalogo":
                # Mostrar ambos: default catálogo, hint historial
                out["historial_sugerido"] = float(det["tarifa_gr"])
                out["detalle"] = (out.get("detalle") or "") + f" · historial reciente ${det['tarifa_gr']}"
    except Exception:
        pass
    return out
