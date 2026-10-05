"""Router: nominas."""
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

@router.get("/nomina-taller", response_class=HTMLResponse)
async def page_nomina_taller(
    request: Request,
    semana_id: int | None = None,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
    trab_repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.core.calendar_util import marcar_semanas
    semanas = marcar_semanas(sem_repo.listar())
    if semana_id is None and semanas:
        actual = next((s for s in semanas if s.get("es_actual")), None)
        semana_id = (actual or semanas[0]).get("id")
    lineas = repo.listar_por_semana(semana_id) if semana_id else []
    totales = repo.totales(semana_id) if semana_id else {}
    trabajadores = [t for t in trab_repo.listar(solo_activos=True) if "TLL" in str(t.get("tipo") or "").upper() or "Mixto" in str(t.get("tipo") or "")]
    return templates.TemplateResponse(
        request,
        "nomina_taller.html",
        _ctx(
            request, semanas=semanas, semana_id=semana_id, lineas=lineas, totales=totales, trabajadores=trabajadores,
            precio_pita_default=NominaTallerRepo.precio_pita_default(),
            semana_cerrada=bool(next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")) if semana_id else False,
        ),
    )



@router.get("/nomina-pita", response_class=HTMLResponse)
async def page_nomina_pita(
    request: Request,
    semana_id: int | None = None,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    trab_repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.core.calendar_util import marcar_semanas
    semanas = marcar_semanas(sem_repo.listar())
    if semana_id is None and semanas:
        actual = next((s for s in semanas if s.get("es_actual")), None)
        semana_id = (actual or semanas[0]).get("id")
    lineas = repo.listar_por_semana(semana_id) if semana_id else []
    totales = repo.totales(semana_id) if semana_id else {}
    trabajadores = [t for t in trab_repo.listar(solo_activos=True) if "PIT" in str(t.get("tipo") or "").upper() or "Mixto" in str(t.get("tipo") or "")]
    return templates.TemplateResponse(
        request,
        "nomina_pita.html",
        _ctx(
            request, semanas=semanas, semana_id=semana_id, lineas=lineas, totales=totales, trabajadores=trabajadores,
            semana_cerrada=bool(next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")) if semana_id else False,
        ),
    )



@router.post("/api/nomina-taller/{semana_id}")
async def api_add_taller(
    semana_id: int,
    nombre: str = Form(...),
    ubic: int = Form(...),
    puesto: str | None = Form(None),
    sueldo: float = Form(0),
    extras: float = Form(0),
    pitas: float | None = Form(None),
    precio_pita: float | None = Form(None),
    trabajador_id: int | None = Form(None),
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    payload = {
        "nombre": nombre, "ubic": ubic, "puesto": puesto,
        "sueldo": sueldo, "extras": extras, "trabajador_id": trabajador_id,
    }
    if pitas is not None:
        payload["pitas"] = pitas
    if precio_pita is not None:
        payload["precio_pita"] = precio_pita
    new_id = repo.insertar(semana_id, payload)
    return {"ok": True, "id": new_id}



@router.post("/api/nomina-pita/{semana_id}")
async def api_add_pita(
    semana_id: int,
    nombre: str = Form(...),
    ubic: int = Form(...),
    modelo: str | None = Form(None),
    folio: str | None = Form(None),
    material: str | None = Form("PITA 6X6"),
    producto: str | None = Form("Cinturón"),
    pitas: float | None = Form(None),
    efectivo: float = Form(0),
    trabajador_id: int | None = Form(None),
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
):
    new_id = repo.insertar(semana_id, {
        "nombre": nombre, "ubic": ubic, "modelo": modelo, "folio": folio,
        "material": material, "producto": producto, "pitas": pitas,
        "efectivo": efectivo, "trabajador_id": trabajador_id,
    })
    return {"ok": True, "id": new_id}



@router.get("/api/resumen/{semana_id}")
async def api_resumen_semana(
    semana_id: int,
    plt: ProduccionRepo = Depends(get_produccion_repo),
    pit: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    tll: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    """Totales tipo captura: Taller + Plata + Pita + gran total."""
    t_plt = plt.totales_semana(semana_id) if hasattr(plt, "totales_semana") else {}
    t_pit = pit.totales(semana_id)
    t_tll = tll.totales(semana_id)
    plata = float(t_plt.get("total_efectivo") or 0)
    pita = float(t_pit.get("total") or 0)
    taller = float(t_tll.get("total") or 0)
    return {
        "semana_id": semana_id,
        "nomina_taller": taller,
        "nomina_plata": plata,
        "nomina_pita": pita,
        "total_nomina": taller + plata + pita,
    }



@router.patch("/api/nomina-pita/linea/{row_id}")
async def api_patch_pita(
    row_id: int,
    request: Request,
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
):
    """Actualiza solo los campos enviados en el formulario."""
    form = await request.form()
    data = {}
    for key in ("modelo", "folio", "material", "producto", "notas"):
        if key in form:
            v = str(form.get(key) or "").strip()
            data[key] = v or None
    if "pitas" in form:
        data["pitas"] = _parse_num(str(form.get("pitas")), allow_empty_none=True)
    if "efectivo" in form:
        data["efectivo"] = _parse_num(str(form.get("efectivo")), default=0, allow_empty_none=False) or 0
    if "firmado" in form:
        try:
            data["firmado"] = 1 if int(str(form.get("firmado"))) else 0
        except ValueError:
            data["firmado"] = 0
    if not data:
        return {"ok": True, "id": row_id, "unchanged": True}
    repo.actualizar(row_id, data)
    return {"ok": True, "id": row_id, "updated": list(data.keys())}



@router.patch("/api/nomina-taller/linea/{row_id}")
async def api_patch_taller(
    row_id: int,
    request: Request,
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    """Actualiza campos. Torcedor: al guardar pitas → sueldo = pitas × precio (def. 3.2)."""
    form = await request.form()
    data = {}
    if "puesto" in form:
        v = str(form.get("puesto") or "").strip()
        data["puesto"] = v or None
    if "sueldo" in form:
        data["sueldo"] = _parse_num(str(form.get("sueldo")), default=0, allow_empty_none=False) or 0
    if "extras" in form:
        data["extras"] = _parse_num(str(form.get("extras")), default=0, allow_empty_none=False) or 0
    if "pitas" in form:
        data["pitas"] = _parse_num(str(form.get("pitas")), allow_empty_none=True)
    if "precio_pita" in form:
        data["precio_pita"] = _parse_num(str(form.get("precio_pita")), default=3.2, allow_empty_none=True)
    if "firmado" in form:
        try:
            data["firmado"] = 1 if int(str(form.get("firmado"))) else 0
        except ValueError:
            data["firmado"] = 0
    if "notas" in form:
        data["notas"] = str(form.get("notas") or "").strip() or None
    if not data:
        return {"ok": True, "id": row_id, "unchanged": True}
    repo.actualizar(row_id, data)
    row = repo.obtener(row_id) or {}
    try:
        if data.get("precio_pita") is not None:
            from app.db.repository import HistorialPreciosRepo
            HistorialPreciosRepo().registrar(
                "PITA", float(data["precio_pita"]), modelo="torcedor", fuente="taller",
            )
    except Exception:
        pass
    return {
        "ok": True,
        "id": row_id,
        "updated": list(data.keys()),
        "sueldo": row.get("sueldo"),
        "extras": row.get("extras"),
        "total": row.get("total"),
        "pitas": row.get("pitas"),
        "precio_pita": row.get("precio_pita"),
    }



@router.delete("/api/nomina-pita/linea/{row_id}")
async def api_del_pita(
    row_id: int,
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
):
    repo.eliminar(row_id)
    return {"ok": True, "id": row_id}



@router.delete("/api/nomina-taller/linea/{row_id}")
async def api_del_taller(
    row_id: int,
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    repo.eliminar(row_id)
    return {"ok": True, "id": row_id}


# ---------- Inteligencia operativa ----------
