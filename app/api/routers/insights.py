"""Router: insights."""
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

@router.get("/api/consistencia")
async def api_consistencia(reparar: int = 0):
    from app.services.consistency_service import ConsistencyService
    return ConsistencyService().revisar(auto_repair=bool(reparar))



@router.post("/api/consistencia/reparar")
async def api_consistencia_reparar():
    from app.services.consistency_service import ConsistencyService
    from app.db.repository import ResumenRepo
    # 1) Recalcular todos los resúmenes desde captura
    ResumenRepo().recalcular_todas(52)
    # 2) Enlaces y demás auto-reparables
    r = ConsistencyService().revisar(auto_repair=True, limit_semanas=16)
    # 3) Estado final (sin reparar de nuevo)
    despues = ConsistencyService().revisar(auto_repair=False, limit_semanas=16)
    return {
        "ok": True,
        "reparados": r.get("reparados", 0),
        "detalles_repair": r.get("detalles_repair") or [],
        "n_avisos_restantes": despues.get("n_avisos", 0),
        "n_manuales": despues.get("n_manuales", 0),
        "n_reparables": despues.get("n_reparables", 0),
        "despues": despues,
    }



@router.get("/api/insights/hoy")
async def api_insights_hoy(svc=Depends(get_insights_service)):
    return svc.avisos_hoy()



@router.get("/api/insights/sugerir-trabajo")
async def api_sugerir_trabajo(
    trabajador_id: int | None = None,
    nombre: str | None = None,
    ubic: int | None = None,
    svc=Depends(get_insights_service),
):
    return svc.sugerir_trabajo(trabajador_id=trabajador_id, nombre=nombre, ubic=ubic)



@router.get("/api/insights/rarezas/{semana_id}")
async def api_rarezas(semana_id: int, svc=Depends(get_insights_service)):
    return svc.rarezas_semana(semana_id)



@router.get("/api/insights/checklist/{semana_id}")
async def api_checklist(semana_id: int, svc=Depends(get_insights_service)):
    return svc.checklist_export(semana_id)



@router.get("/api/insights/pronostico/{semana_id}")
async def api_pronostico(semana_id: int, svc=Depends(get_insights_service)):
    return svc.pronostico_semana(semana_id)



@router.post("/api/insights/duplicar/{semana_id}")
async def api_duplicar_completa(
    semana_id: int,
    destino_id: int | None = Form(None),
    areas: str | None = Form("plt,pit,tll"),
    force: str | None = Form("0"),
    svc=Depends(get_insights_service),
):
    """Duplica estructuras a la semana siguiente. No re-inserta líneas ya existentes."""
    lista = [a.strip().lower() for a in (areas or "plt,pit,tll").split(",") if a.strip()]
    force_flag = str(force or "0").strip() in ("1", "true", "True", "yes", "on")
    return svc.duplicar_a_siguiente(
        semana_id, destino_id=destino_id, areas=lista, force=force_flag
    )



@router.get("/api/insights/tendencias")
async def api_tendencias(limit: int = 8, svc=Depends(get_insights_service)):
    return svc.tendencias(limit_semanas=min(max(limit, 3), 16))



@router.get("/api/insights/solo-hoy")
async def api_solo_hoy(svc=Depends(get_insights_service)):
    return svc.captura_solo_hoy()



@router.get("/api/ops/settings")
async def api_ops_settings_get():
    from app.core.ops_settings import load
    return load()



@router.post("/api/ops/settings")
async def api_ops_settings_set(request: Request):
    from app.core.ops_settings import save, get_anomaly_pct
    form = await request.form()
    data = {}
    if "anomaly_pct" in form:
        try:
            # aceptar 30 o 0.30
            raw = str(form.get("anomaly_pct") or "30").replace(",", ".").strip()
            v = float(raw)
            if v > 1:
                v = v / 100.0
            data["anomaly_pct"] = v
        except ValueError:
            from app.core.exceptions import ValidationAppError
            raise ValidationAppError("Umbral inválido")
    out = save(data)
    out["anomaly_pct_display"] = int(round(get_anomaly_pct() * 100))
    return out


