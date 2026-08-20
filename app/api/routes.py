"""
Rutas API REST + páginas web.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.api.deps import (
    get_dashboard_service,
    get_export_service,
    get_produccion_repo,
    get_semanas_repo,
    get_trabajadores_repo,
)
from app.core.exceptions import AppError
from app.db.repository import ProduccionRepo, SemanasRepo, TrabajadoresRepo
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


# ---------- Web pages ----------

@router.get("/", response_class=HTMLResponse)
async def page_dashboard(
    request: Request,
    svc: DashboardService = Depends(get_dashboard_service),
):
    data = svc.get_dashboard()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "kpis": data["kpis"],
            "semanas": data["ultimas_semanas"],
            "db_ok": data.get("db_ok", True),
        },
    )


@router.get("/trabajadores", response_class=HTMLResponse)
async def page_trabajadores(
    request: Request,
    q: str | None = None,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.services.dashboard_service import check_db
    rows = repo.listar(solo_activos=False, busqueda=q)
    return templates.TemplateResponse(
        request,
        "trabajadores.html",
        {"trabajadores": rows, "q": q or "", "db_ok": check_db()},
    )



@router.get("/buscar", response_class=HTMLResponse)
async def page_buscar(
    request: Request,
    q: str | None = None,
    svc: DashboardService = Depends(get_dashboard_service),
):
    data = svc.buscar(q or "")
    return templates.TemplateResponse(
        request,
        "buscar.html",
        {
            "q": q or "",
            "trabajadores": data["trabajadores"],
            "semanas": data["semanas"],
            "db_ok": data.get("db_ok", True),
        },
    )


@router.get("/produccion", response_class=HTMLResponse)
async def page_produccion(
    request: Request,
    semana_id: int | None = None,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    prod_repo: ProduccionRepo = Depends(get_produccion_repo),
    trab_repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.services.dashboard_service import check_db
    semanas = sem_repo.listar()
    if semana_id is None and semanas:
        semana_id = semanas[0]["id"]
    lineas = prod_repo.listar_por_semana(semana_id) if semana_id else []
    totales = prod_repo.totales_semana(semana_id) if semana_id else {}
    trabajadores = trab_repo.listar(solo_plt=True, solo_activos=True)
    return templates.TemplateResponse(
        request,
        "produccion.html",
        {
            "semanas": semanas,
            "semana_id": semana_id,
            "lineas": lineas,
            "totales": totales,
            "trabajadores": trabajadores,
            "db_ok": check_db(),
        },
    )


# ---------- API JSON ----------

@router.get("/api/health")
async def health():
    from app import __version__
    from app.services.dashboard_service import check_db
    db_ok = check_db()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": "fajos_central",
        "version": __version__,
        "database": "ok" if db_ok else "error",
    }


@router.get("/api/dashboard")
async def api_dashboard(svc: DashboardService = Depends(get_dashboard_service)):
    return svc.get_dashboard()


@router.get("/api/trabajadores")
async def api_trabajadores(
    solo_plt: bool = False,
    solo_activos: bool = True,
    q: str | None = None,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    return repo.listar(solo_plt=solo_plt, solo_activos=solo_activos, busqueda=q)


@router.post("/api/trabajadores")
async def api_crear_trabajador(
    nombre_mostrar: str = Form(...),
    ubic: int = Form(...),
    tipo: str = Form("PLT"),
    puesto: str | None = Form(None),
    fecha_incorporacion: str | None = Form(None),
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    new_id = repo.agregar({
        "nombre_mostrar": nombre_mostrar,
        "ubic": ubic,
        "tipo": tipo,
        "puesto": puesto,
        "fecha_incorporacion": fecha_incorporacion or None,
    })
    return {"id": new_id, "ok": True}


@router.get("/api/semanas")
async def api_semanas(repo: SemanasRepo = Depends(get_semanas_repo)):
    return repo.listar()


@router.post("/api/semanas")
async def api_crear_semana(
    codigo: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...),
    anio: int = Form(2026),
    notas: str | None = Form(None),
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    new_id = repo.crear({
        "codigo": codigo,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "anio": anio,
        "notas": notas,
    })
    return {"id": new_id, "ok": True}


@router.get("/api/produccion/{semana_id}")
async def api_produccion(semana_id: int, repo: ProduccionRepo = Depends(get_produccion_repo)):
    return {
        "lineas": repo.listar_por_semana(semana_id),
        "totales": repo.totales_semana(semana_id),
    }


@router.post("/api/produccion/{semana_id}")
async def api_add_produccion(
    semana_id: int,
    nombre: str = Form(...),
    ubic: int = Form(...),
    folio: str | None = Form(None),
    modelo: str | None = Form(None),
    material: str | None = Form("AG3"),
    tarifa_gr: float | None = Form(12.0),
    gm_sab: float | None = Form(None),
    gm_dom: float | None = Form(None),
    gm_lun: float | None = Form(None),
    gm_mar: float | None = Form(None),
    gm_mie: float | None = Form(None),
    gm_jue: float | None = Form(None),
    gm_vie: float | None = Form(None),
    trabajador_id: int | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    new_id = repo.insertar(semana_id, {
        "nombre": nombre,
        "ubic": ubic,
        "folio": folio,
        "modelo": modelo,
        "material": material,
        "tarifa_gr": tarifa_gr,
        "gm_sab": gm_sab,
        "gm_dom": gm_dom,
        "gm_lun": gm_lun,
        "gm_mar": gm_mar,
        "gm_mie": gm_mie,
        "gm_jue": gm_jue,
        "gm_vie": gm_vie,
        "trabajador_id": trabajador_id,
    })
    return {"id": new_id, "ok": True}


@router.delete("/api/produccion/linea/{prod_id}")
async def api_del_produccion(prod_id: int, repo: ProduccionRepo = Depends(get_produccion_repo)):
    repo.eliminar(prod_id)
    return {"ok": True}


@router.get("/api/export/produccion/{semana_id}")
async def api_export(
    semana_id: int,
    fmt: str = Query("xlsx", pattern="^(xlsx|csv|pdf|json)$"),
    formal: int = Query(0, description="1 = ordenar como nómina formal (ubic, nombre)"),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    prod_repo: ProduccionRepo = Depends(get_produccion_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    semana = sem_repo.obtener(semana_id)
    lineas = prod_repo.listar_por_semana(semana_id)
    if formal:
        def _key(row: dict):
            try:
                u = int(row.get("ubic") or 0)
            except (TypeError, ValueError):
                u = 0
            return (u, str(row.get("nombre") or "").upper(), str(row.get("folio") or "").upper())
        lineas = sorted(lineas, key=_key)
        # solo líneas con datos útiles
        lineas = [
            r for r in lineas
            if r.get("folio") or r.get("modelo") or float(r.get("total_gramos") or 0) > 0
        ]
    stem = f"nomina_formal_{semana['codigo']}" if formal else f"nomina_{semana['codigo']}"
    content, media_type, filename = export_svc.export_produccion(
        lineas,
        fmt=fmt,  # type: ignore
        codigo_semana=semana["codigo"],
        filename_stem=stem,
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Error handler helper (used by main) ----------

def error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())
