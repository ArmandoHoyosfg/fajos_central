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
    common_template_context,
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

def _ctx(request: Request, **kwargs):
    """Contexto de plantilla unificado (fecha, versión, db_ok + kwargs)."""
    data = common_template_context(kwargs)
    data["request"] = request
    return data



# ---------- Web pages ----------

@router.get("/", response_class=HTMLResponse)
async def page_dashboard(
    request: Request,
    svc: DashboardService = Depends(get_dashboard_service),
):
    from app.core.calendar_util import marcar_semanas
    data = svc.get_dashboard()
    semanas = marcar_semanas(data["ultimas_semanas"])
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(request, kpis=data["kpis"], semanas=semanas),
    )


@router.get("/trabajadores", response_class=HTMLResponse)
async def page_trabajadores(
    request: Request,
    q: str | None = None,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    trabajadores = repo.listar(solo_activos=False, busqueda=q)
    return templates.TemplateResponse(
        request,
        "trabajadores.html",
        _ctx(request, trabajadores=trabajadores, q=q),
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
        _ctx(request, q=q, trabajadores=data["trabajadores"], semanas=data["semanas"]),
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
    from app.core.calendar_util import encontrar_semana_actual, marcar_semanas, today
    semanas_raw = sem_repo.listar()
    semanas = marcar_semanas(semanas_raw)
    if semana_id is None and semanas:
        actual = encontrar_semana_actual(semanas_raw, today())
        semana_id = actual["id"] if actual else semanas[0]["id"]
    lineas = prod_repo.listar_por_semana(semana_id) if semana_id else []
    totales = prod_repo.totales_semana(semana_id) if semana_id else {}
    trabajadores = trab_repo.listar(solo_plt=False, solo_activos=True)
    return templates.TemplateResponse(
        request,
        "produccion.html",
        _ctx(
            request,
            semanas=semanas,
            semana_id=semana_id,
            lineas=lineas,
            totales=totales,
            trabajadores=trabajadores,
            semana_cerrada=bool(
                next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")
            ) if semana_id else False,
        ),
    )


# ---------- API JSON ----------




@router.post("/api/semanas/actual")
async def api_crear_semana_actual(
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    """Crea (o devuelve) la semana sáb–vie que contiene hoy."""
    from app.core.calendar_util import encontrar_semana_actual, sugerir_codigo_semana, today

    existentes = repo.listar()
    actual = encontrar_semana_actual(existentes, today())
    if actual:
        return {"ok": True, "created": False, "semana": actual}
    codigo, sab, vie = sugerir_codigo_semana(today())
    new_id = repo.crear({
        "codigo": codigo,
        "fecha_inicio": sab.isoformat(),
        "fecha_fin": vie.isoformat(),
        "anio": sab.year,
        "notas": "Creada automáticamente (semana actual)",
    })
    return {
        "ok": True,
        "created": True,
        "semana": {
            "id": new_id,
            "codigo": codigo,
            "fecha_inicio": sab.isoformat(),
            "fecha_fin": vie.isoformat(),
            "anio": sab.year,
        },
    }


@router.patch("/api/produccion/linea/{prod_id}/firmado")
async def api_toggle_firmado(
    prod_id: int,
    firmado: int = Form(1),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    repo.set_firmado(prod_id, bool(int(firmado)))
    return {"ok": True, "prod_id": prod_id, "firmado": bool(int(firmado))}


@router.get("/api/trabajos")
async def api_trabajos(solo_activos: bool = True, trabajador_id: int | None = None):
    from app.db.repository import TrabajosRepo
    return TrabajosRepo().listar(solo_activos=solo_activos, trabajador_id=trabajador_id)


@router.get("/api/tarifas")
async def api_tarifas():
    from app.services.tarifas_service import TarifasService
    return TarifasService().mapa()


@router.post("/api/semanas/{semana_id}/cerrar")
async def api_cerrar_semana(
    semana_id: int,
    usuario: str | None = Form(None),
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    repo.cerrar(semana_id, usuario=usuario or "web")
    return {"ok": True, "semana_id": semana_id, "cerrada": True}


@router.post("/api/semanas/{semana_id}/reabrir")
async def api_reabrir_semana(
    semana_id: int,
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    repo.reabrir(semana_id)
    return {"ok": True, "semana_id": semana_id, "cerrada": False}


@router.get("/api/semanas/{semana_id}/historial")
async def api_historial(semana_id: int, limit: int = Query(50, ge=1, le=500)):
    from app.services.audit_service import AuditService
    return AuditService().listar_por_semana(semana_id, limit=limit)


@router.get("/api/suministro")
async def api_suministro(fecha: str | None = None):
    """Avance del día (suministro) + líneas de la semana actual si aplica."""
    from datetime import date as _date
    from app.core.calendar_util import encontrar_semana_actual, today
    from app.db.connection import get_db
    from app.db.repository import ProduccionRepo, SemanasRepo

    d = _date.fromisoformat(fecha) if fecha else today()
    day_map = {5: "gm_sab", 6: "gm_dom", 0: "gm_lun", 1: "gm_mar", 2: "gm_mie", 3: "gm_jue", 4: "gm_vie"}
    col = day_map.get(d.weekday(), "gm_lun")
    sem_repo = SemanasRepo()
    semanas = sem_repo.listar()
    actual = encontrar_semana_actual(semanas, d)
    lineas = []
    if actual:
        prod = ProduccionRepo().listar_por_semana(actual["id"])
        for r in prod:
            gr = r.get(col)
            try:
                grf = float(gr) if gr is not None else 0
            except (TypeError, ValueError):
                grf = 0
            lineas.append({
                "produccion_id": r.get("id"),
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "folio": r.get("folio"),
                "modelo": r.get("modelo"),
                "material": r.get("material"),
                "gramos_hoy": grf if grf else None,
                "campo_dia": col,
            })
    return {
        "fecha": d.isoformat(),
        "campo_dia": col,
        "semana": actual,
        "lineas": lineas,
    }



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
    from app.core.normalize import canonical_name
    new_id = repo.insertar(semana_id, {
        "nombre": canonical_name(nombre),
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




@router.patch("/api/produccion/linea/{prod_id}/dia")
async def api_patch_dia(
    prod_id: int,
    dia: str = Form(...),
    gramos: float | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """Registra o corrige un solo día de trabajo en una línea existente."""
    repo.actualizar_gramos_dia(prod_id, dia, gramos)
    return {"ok": True, "prod_id": prod_id, "dia": dia, "gramos": gramos}


@router.post("/api/produccion/{semana_id}/dia")
async def api_add_un_dia(
    semana_id: int,
    nombre: str = Form(...),
    ubic: int = Form(...),
    dia: str = Form(...),
    gramos: float = Form(...),
    folio: str | None = Form(None),
    modelo: str | None = Form(None),
    material: str | None = Form("AG3"),
    tarifa_gr: float | None = Form(12.0),
    trabajador_id: int | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """
    Alta rápida: una línea con un solo día lleno (resto vacío).
    Ideal para capturar el avance del día sin rellenar la semana completa.
    """
    from app.core.normalize import canonical_name
    day_map = {
        "sab": "gm_sab", "dom": "gm_dom", "lun": "gm_lun", "mar": "gm_mar",
        "mie": "gm_mie", "jue": "gm_jue", "vie": "gm_vie",
    }
    col = day_map.get(dia.strip().lower())
    if not col:
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError(f"Día inválido: {dia}")
    payload = {
        "nombre": canonical_name(nombre),
        "ubic": ubic,
        "folio": folio,
        "modelo": modelo,
        "material": material,
        "tarifa_gr": tarifa_gr,
        "trabajador_id": trabajador_id,
        "gm_sab": None, "gm_dom": None, "gm_lun": None,
        "gm_mar": None, "gm_mie": None, "gm_jue": None, "gm_vie": None,
    }
    payload[col] = gramos
    new_id = repo.insertar(semana_id, payload)
    return {"id": new_id, "ok": True, "dia": dia, "gramos": gramos}


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
    if formal and fmt in ("xlsx", "pdf"):
        try:
            from app.services.backup_service import BackupService
            BackupService().guardar_export(
                content,
                codigo_semana=str(semana.get("codigo") or ""),
                extension=f".{fmt}",
                prefijo="formal",
            )
        except Exception:
            pass
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ---------- Error handler helper (used by main) ----------

def error_response(exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())
