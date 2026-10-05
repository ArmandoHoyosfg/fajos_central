"""Router: semanas."""
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

@router.patch("/api/semanas/{semana_id}")
async def api_patch_semana(
    semana_id: int,
    codigo: str | None = Form(None),
    fecha_inicio: str | None = Form(None),
    fecha_fin: str | None = Form(None),
    notas: str | None = Form(None),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    """Corrige código o fechas de una semana (p. ej. tras un duplicado mal calculado)."""
    from app.core.calendar_util import parse_db_date, rango_sab_vie, codigo_desde_rango
    from app.core.exceptions import NotFoundError, ValidationAppError

    sem = sem_repo.obtener(semana_id)
    if not sem:
        raise NotFoundError("Semana no encontrada")
    data = {}
    if codigo is not None and str(codigo).strip():
        data["codigo"] = str(codigo).strip()
    if fecha_inicio is not None:
        data["fecha_inicio"] = str(fecha_inicio).strip()[:10]
    if fecha_fin is not None:
        data["fecha_fin"] = str(fecha_fin).strip()[:10]
    if notas is not None:
        data["notas"] = notas
    # Si mandan solo una fecha, normalizar a sáb–vie
    if data.get("fecha_inicio") and not data.get("fecha_fin"):
        fi = parse_db_date(data["fecha_inicio"])
        if fi:
            sab, vie = rango_sab_vie(fi)
            data["fecha_inicio"] = sab.isoformat()
            data["fecha_fin"] = vie.isoformat()
            data.setdefault("codigo", codigo_desde_rango(sab, vie))
    if data.get("fecha_inicio") and data.get("fecha_fin"):
        fi = parse_db_date(data["fecha_inicio"])
        ff = parse_db_date(data["fecha_fin"])
        if not fi or not ff:
            raise ValidationAppError("Fechas inválidas")
        if fi > ff:
            fi, ff = ff, fi
            data["fecha_inicio"], data["fecha_fin"] = fi.isoformat(), ff.isoformat()
        # advertir si no es sáb–vie exacto: auto-ajustar al rango de fi
        sab, vie = rango_sab_vie(fi)
        if fi != sab or ff != vie:
            data["fecha_inicio"] = sab.isoformat()
            data["fecha_fin"] = vie.isoformat()
            data["codigo"] = codigo_desde_rango(sab, vie)
    if not data:
        raise ValidationAppError("Nada que actualizar")
    sem_repo.actualizar(semana_id, data)
    return {"ok": True, "semana": sem_repo.obtener(semana_id)}




@router.get("/semanas", response_class=HTMLResponse)
async def page_semanas(
    request: Request,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    """Gestión de semanas: editar fechas/código, eliminar vacías, alinear a actual."""
    from app.core.calendar_util import (
        marcar_semanas,
        sugerir_codigo_semana,
        today,
        format_fecha_corta,
        rango_sab_vie,
    )
    semanas = marcar_semanas(sem_repo.listar())
    for s in semanas:
        s["uso"] = sem_repo.conteo_uso(s["id"])
        # serializable para el modal JS
        for k in ("fecha_inicio", "fecha_fin", "creado_en", "cerrado_en"):
            if s.get(k) is not None:
                s[k] = str(s[k])[:19]
    cod, sab, vie = sugerir_codigo_semana(today())
    return templates.TemplateResponse(
        request,
        "semanas.html",
        _ctx(
            request,
            semanas=semanas,
            sugerida={
                "codigo": cod,
                "fecha_inicio": sab.isoformat(),
                "fecha_fin": vie.isoformat(),
                "label": f"{cod} ({sab.isoformat()} → {vie.isoformat()})",
            },
            hoy=format_fecha_corta(today()),
        ),
    )



@router.get("/api/semanas")
async def api_list_semanas(sem_repo: SemanasRepo = Depends(get_semanas_repo)):
    from app.core.calendar_util import marcar_semanas
    semanas = marcar_semanas(sem_repo.listar())
    for s in semanas:
        s["uso"] = sem_repo.conteo_uso(s["id"])
    return semanas



@router.delete("/api/semanas/{semana_id}")
async def api_delete_semana(
    semana_id: int,
    force: int = Query(0),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    return sem_repo.eliminar(semana_id, force=bool(force))



@router.post("/api/semanas/{semana_id}/alinear-actual")
async def api_alinear_semana_actual(
    semana_id: int,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    """
    Pone esta semana como la sáb–vie que contiene hoy.
    Si otra semana ya ocupa ese rango, error con detalle.
    Conserva todas las líneas de producción.
    """
    from app.core.calendar_util import (
        sugerir_codigo_semana,
        encontrar_semana_por_rango,
        today,
    )
    from app.core.exceptions import ValidationAppError, NotFoundError

    sem = sem_repo.obtener(semana_id)
    if not sem:
        raise NotFoundError("Semana no encontrada")
    codigo, sab, vie = sugerir_codigo_semana(today())
    otras = [s for s in sem_repo.listar() if int(s["id"]) != int(semana_id)]
    choque = encontrar_semana_por_rango(otras, sab, vie)
    if choque:
        raise ValidationAppError(
            f"Ya existe la semana {choque.get('codigo')} "
            f"({choque.get('fecha_inicio')} → {choque.get('fecha_fin')}) "
            f"para ese rango. Elimínala si está vacía o edítala antes.",
            details={"conflicto_id": choque.get("id"), "conflicto_codigo": choque.get("codigo")},
        )
    sem_repo.actualizar(semana_id, {
        "codigo": codigo,
        "fecha_inicio": sab.isoformat(),
        "fecha_fin": vie.isoformat(),
        "anio": sab.year,
        "notas": (str(sem.get("notas") or "") + " | Alineada a semana actual").strip(" |"),
    })
    return {"ok": True, "semana": sem_repo.obtener(semana_id), "mensaje": f"Ahora es {codigo} ({sab} → {vie})"}



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



@router.post("/api/semanas/{semana_id}/cerrar")
async def api_cerrar_semana(
    semana_id: int,
    usuario: str | None = Form(None),
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    from app.db.repository import ResumenRepo
    repo.cerrar(semana_id, usuario=usuario or "web")
    vivos = ResumenRepo().recalcular(semana_id, notas=f"Cierre por {usuario or 'web'}")
    return {"ok": True, "semana_id": semana_id, "cerrada": True, "totales": vivos}



@router.post("/api/semanas/{semana_id}/reabrir")
async def api_reabrir_semana(
    semana_id: int,
    repo: SemanasRepo = Depends(get_semanas_repo),
):
    repo.reabrir(semana_id)
    return {"ok": True, "semana_id": semana_id, "cerrada": False}




@router.get("/historial/{semana_id}", response_class=HTMLResponse)
async def page_historial(
    request: Request,
    semana_id: int,
    limit: int = Query(100, ge=1, le=500),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    from app.services.audit_service import AuditService
    semana = sem_repo.obtener(semana_id)
    rows = AuditService().listar_por_semana(semana_id, limit=limit)
    return templates.TemplateResponse(
        request,
        "historial.html",
        _ctx(request, semana_id=semana_id, semana=semana, rows=rows),
    )



@router.get("/api/semanas/{semana_id}/historial")
async def api_historial(semana_id: int, limit: int = Query(50, ge=1, le=500)):
    from app.services.audit_service import AuditService
    return AuditService().listar_por_semana(semana_id, limit=limit)



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


