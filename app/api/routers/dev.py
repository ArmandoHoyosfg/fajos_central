"""Router: dev."""
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

@router.post("/dev/merge-trabajadores", response_class=HTMLResponse)
async def page_dev_merge_trabajadores(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    form = await request.form()
    try:
        id_keep = int(form.get("id_keep") or 0)
        id_merge = int(form.get("id_merge") or 0)
    except (TypeError, ValueError):
        return _dev_page_payload(repo, error="IDs invalidos para fusion")
    from app.services.aprendizaje_service import AprendizajeService
    result = None
    error = None
    try:
        result = AprendizajeService().fusionar_trabajadores(id_keep, id_merge)
        if not result.get("ok"):
            error = result.get("error") or "No se pudo fusionar"
    except Exception as e:
        error = str(e)
    return _dev_page_payload(repo, action_result=result, error=error)



@router.post("/dev/folio-accion", response_class=HTMLResponse)
async def page_dev_folio_accion(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    form = await request.form()
    accion = str(form.get("accion") or "")
    result = None
    error = None
    try:
        prod_id = int(form.get("prod_id") or 0) or None
        from app.services.aprendizaje_service import AprendizajeService
        svc = AprendizajeService()
        if accion == "terminar" and prod_id:
            result = svc.marcar_folio_terminado(prod_id=prod_id)
            if not result.get("ok"):
                error = result.get("error")
        else:
            error = "Acción no reconocida"
    except Exception as e:
        error = str(e)
    return _dev_page_payload(repo, action_result=result, error=error)



@router.post("/dev/migrar", response_class=HTMLResponse)
async def page_dev_migrar(repo: TrabajadoresRepo = Depends(get_trabajadores_repo)):
    from app.db.migrate import MigrationRunner
    try:
        result = MigrationRunner().apply_pending()
        return _dev_page_payload(repo, action_result={"accion": "migrar", **result})
    except Exception as e:
        return _dev_page_payload(repo, error=str(e))



@router.post("/dev/reparar-inteligente", response_class=HTMLResponse)
async def page_dev_reparar_inteligente(repo: TrabajadoresRepo = Depends(get_trabajadores_repo)):
    """Pipeline: migraciones → resumen → consistencia → huérfanos → sync denorm."""
    steps = []
    try:
        from app.db.migrate import MigrationRunner
        m = MigrationRunner().apply_pending()
        steps.append({"paso": "migraciones", **m})
    except Exception as e:
        steps.append({"paso": "migraciones", "ok": False, "error": str(e)})
    try:
        from app.db.repository import ResumenRepo
        r = ResumenRepo().recalcular_todas(52)
        steps.append({"paso": "resumen_totales", **r})
    except Exception as e:
        steps.append({"paso": "resumen_totales", "ok": False, "error": str(e)})
    try:
        from app.services.consistency_service import ConsistencyService
        c = ConsistencyService().revisar(auto_repair=True, limit_semanas=16)
        steps.append({"paso": "consistencia", "reparados": c.get("reparados"), "n_avisos": c.get("n_avisos")})
    except Exception as e:
        steps.append({"paso": "consistencia", "ok": False, "error": str(e)})
    try:
        # huérfanos + sync
        h = repo.reparar_huerfanos() if hasattr(repo, "reparar_huerfanos") else {"skipped": True}
        steps.append({"paso": "huerfanos", **(h if isinstance(h, dict) else {"result": h})})
    except Exception as e:
        steps.append({"paso": "huerfanos", "ok": False, "error": str(e)})
    try:
        s = repo.sincronizar_todos_denormalizados()
        steps.append({"paso": "sync_denorm", **s})
    except Exception as e:
        steps.append({"paso": "sync_denorm", "ok": False, "error": str(e)})
    ok = all(x.get("ok", True) and not x.get("error") for x in steps)
    return _dev_page_payload(repo, action_result={"accion": "reparar_inteligente", "ok": ok, "steps": steps})




@router.get("/api/dev/logs")
async def api_dev_logs(after_id: int = 0, limit: int = 150):
    """Eventos recientes para la consola Dev (solo lectura)."""
    from app.core.event_log import list_since, push
    items = list_since(after_id=after_id, limit=limit)
    return {"ok": True, "events": items, "server_time": __import__("datetime").datetime.now().isoformat(timespec="seconds")}



@router.post("/api/dev/client-log")
async def api_dev_client_log(request: Request):
    """Recibe errores del navegador para la consola Dev."""
    from app.core.event_log import push
    try:
        body = await request.json()
    except Exception:
        body = {}
    level = str(body.get("level") or "error")
    msg = str(body.get("message") or "error cliente")[:1500]
    detail = body.get("detail")
    path = body.get("path") or body.get("url")
    push(level, msg, source="client", detail=str(detail)[:3000] if detail else None, path=str(path) if path else None)
    return {"ok": True}



@router.post("/api/dev/logs/clear")
async def api_dev_logs_clear():
    from app.core.event_log import clear, push
    clear()
    push("info", "Consola Dev limpiada", source="dev")
    return {"ok": True}



@router.get("/dev", response_class=HTMLResponse)
async def page_dev(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    return _dev_page_payload(repo)



@router.post("/dev/sync", response_class=HTMLResponse)
async def page_dev_sync(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    sync_result = None
    error = None
    try:
        sync_result = repo.sincronizar_todos_denormalizados()
    except Exception as e:
        error = str(e)
    return _dev_page_payload(repo, sync_result=sync_result, error=error)



@router.post("/dev/reparar-huerfanos", response_class=HTMLResponse)
async def page_dev_reparar_huerfanos(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    result = None
    error = None
    try:
        result = repo.reparar_huerfanos()
        # tras enlazar, sincronizar nombre/ubic
        repo.sincronizar_todos_denormalizados()
    except Exception as e:
        error = str(e)
    return _dev_page_payload(repo, action_result=result, error=error)



@router.post("/dev/crear-semana-actual", response_class=HTMLResponse)
async def page_dev_crear_semana_actual(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    from app.core.calendar_util import sugerir_codigo_semana
    result = None
    error = None
    try:
        info = repo.semana_actual_info()
        if info.get("existe"):
            result = {"ok": True, "mensaje": "Ya existía", **info}
        else:
            codigo, sab, vie = sugerir_codigo_semana()
            sid = sem_repo.crear({
                "codigo": codigo,
                "fecha_inicio": sab.isoformat(),
                "fecha_fin": vie.isoformat(),
                "anio": sab.year,
            })
            result = {"ok": True, "creada_id": sid, "codigo": codigo, "inicio": sab.isoformat(), "fin": vie.isoformat()}
    except Exception as e:
        error = str(e)
    return _dev_page_payload(repo, action_result=result, error=error)




@router.get("/api/dev/db/meta")
async def api_dev_db_meta():
    """Tablas allowlist, presets y reparaciones disponibles."""
    from app.services.dev_db_service import DevDbService
    svc = DevDbService()
    return {
        "ok": True,
        "tables": svc.list_tables(),
        "presets": svc.list_presets(),
        "repairs": svc.list_repairs(),
        "max_rows": 200,
    }


@router.post("/api/dev/db/query")
async def api_dev_db_query(request: Request):
    """Nivel A: SELECT seguro (preset o SQL de solo lectura)."""
    from app.services.dev_db_service import DevDbService
    body = {}
    try:
        body = await request.json()
    except Exception:
        form = await request.form()
        body = dict(form)
    preset_id = (body.get("preset_id") or body.get("preset") or "").strip() or None
    sql = (body.get("sql") or "").strip() or None
    try:
        return DevDbService().run_select(sql=sql, preset_id=preset_id)
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@router.post("/api/dev/db/repair/{action_id}")
async def api_dev_db_repair(action_id: str):
    """Nivel B: reparación guiada (código fijo, no SQL libre de escritura)."""
    from app.services.dev_db_service import DevDbService
    try:
        return DevDbService().run_repair(action_id)
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

