"""Router: trabajadores."""
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

@router.post("/api/trabajadores/merge")
async def api_merge_trabajadores(
    id_keep: int = Form(...),
    id_merge: int = Form(...),
    auto_nombre: int = Form(1),
):
    """Une fichas. Por defecto conserva el nombre más completo (auto_nombre=1)."""
    from app.services.aprendizaje_service import AprendizajeService
    return AprendizajeService().fusionar_trabajadores(
        id_keep, id_merge, auto_nombre=bool(int(auto_nombre)),
    )


@router.get("/api/dev/fusiones")
async def api_dev_fusiones(limit: int = 50):
    from app.services.aprendizaje_service import AprendizajeService
    return {"ok": True, "items": AprendizajeService().listar_fusiones(limit=limit)}


@router.post("/api/dev/fusiones/{event_id}/deshacer")
async def api_dev_deshacer_fusion(event_id: int):
    from app.services.aprendizaje_service import AprendizajeService
    return AprendizajeService().deshacer_fusion(event_id)



@router.post("/api/trabajadores/duplicados/descartar")
async def api_descartar_duplicado(
    id_a: int = Form(...),
    id_b: int = Form(...),
):
    from app.services.aprendizaje_service import AprendizajeService
    return AprendizajeService().descartar_duplicado(id_a, id_b, dias=7)



@router.get("/api/trabajadores/duplicados")
async def api_trabajadores_duplicados():
    from app.services.aprendizaje_service import AprendizajeService
    return {"ok": True, "items": AprendizajeService().candidatos_duplicados_trabajadores()}



@router.get("/trabajadores", response_class=HTMLResponse)
async def page_trabajadores(
    request: Request,
    q: str | None = None,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    try:
        trabajadores = repo.listar(solo_activos=False, busqueda=q)
    except Exception as e:
        from app.core.logging_config import get_logger
        get_logger(__name__).exception("page_trabajadores")
        trabajadores = []
    duplicados: list = []
    try:
        from app.services.aprendizaje_service import AprendizajeService
        duplicados = AprendizajeService().candidatos_duplicados_trabajadores()
    except Exception:
        duplicados = []
    return templates.TemplateResponse(
        request,
        "trabajadores.html",
        _ctx(request, trabajadores=trabajadores, q=q, duplicados=duplicados),
    )




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
    sueldo_modo: str | None = Form("variable"),
    sueldo_base: str | None = Form(None),
    fecha_incorporacion: str | None = Form(None),
    nombre_completo: str | None = Form(None),
    notas: str | None = Form(None),
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.core.normalize import canonical_name
    modo = (sueldo_modo or "variable").strip().lower()
    if modo not in ("fijo", "variable"):
        modo = "variable"
    base = None
    if sueldo_base is not None and str(sueldo_base).strip() != "":
        try:
            base = float(sueldo_base)
        except ValueError:
            base = None
    new_id = repo.agregar({
        "nombre_mostrar": canonical_name(nombre_mostrar),
        "nombre_completo": (nombre_completo or nombre_mostrar).strip(),
        "ubic": ubic,
        "tipo": tipo,
        "puesto": puesto,
        "sueldo_modo": modo,
        "sueldo_base": base,
        "fecha_incorporacion": fecha_incorporacion or None,
        "notas": notas,
    })
    return {"id": new_id, "ok": True}




@router.get("/api/trabajadores/{trabajador_id}")
async def api_get_trabajador(
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    return repo.obtener(trabajador_id)



@router.put("/api/trabajadores/{trabajador_id}")
@router.patch("/api/trabajadores/{trabajador_id}")
async def api_update_trabajador(
    trabajador_id: int,
    nombre_mostrar: str | None = Form(None),
    nombre_completo: str | None = Form(None),
    ubic: int | None = Form(None),
    tipo: str | None = Form(None),
    puesto: str | None = Form(None),
    sueldo_modo: str | None = Form(None),
    sueldo_base: str | None = Form(None),
    fecha_incorporacion: str | None = Form(None),
    notas: str | None = Form(None),
    activo: int | None = Form(None),
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.core.normalize import canonical_name
    data: dict = {}
    if nombre_mostrar is not None and nombre_mostrar.strip():
        data["nombre_mostrar"] = canonical_name(nombre_mostrar)
    if nombre_completo is not None:
        data["nombre_completo"] = nombre_completo.strip() or data.get("nombre_mostrar")
    if ubic is not None:
        data["ubic"] = ubic
    if tipo is not None:
        data["tipo"] = tipo
    if puesto is not None:
        data["puesto"] = puesto or None
    if sueldo_modo is not None:
        m = sueldo_modo.strip().lower()
        data["sueldo_modo"] = m if m in ("fijo", "variable") else "variable"
    if sueldo_base is not None:
        try:
            data["sueldo_base"] = float(sueldo_base) if str(sueldo_base).strip() != "" else None
        except ValueError:
            data["sueldo_base"] = None
    if fecha_incorporacion is not None:
        data["fecha_incorporacion"] = fecha_incorporacion or None
    if notas is not None:
        data["notas"] = notas or None
    if activo is not None:
        data["activo"] = 1 if int(activo) else 0
    row = repo.actualizar(trabajador_id, data)
    # Asegura sync aunque actualizar ya lo hizo (idempotente)
    try:
        sync = repo.sincronizar_denormalizados(trabajador_id)
    except Exception:
        sync = {}
    if isinstance(row, dict):
        row = {**row, "sync": sync, "ok": True}
    return row



@router.post("/api/trabajadores/{trabajador_id}/baja")
async def api_baja_trabajador(
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    repo.desactivar(trabajador_id)
    return {"ok": True, "id": trabajador_id, "activo": 0}



@router.post("/api/trabajadores/{trabajador_id}/activar")
async def api_activar_trabajador(
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    repo.activar(trabajador_id)
    return {"ok": True, "id": trabajador_id, "activo": 1}





@router.post("/api/trabajadores/{trabajador_id}/sincronizar")
async def api_sync_trabajador(
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    """Propaga nombre/ubic del catálogo a Plata, Pita y Taller."""
    sync = repo.sincronizar_denormalizados(trabajador_id)
    return {"ok": True, "id": trabajador_id, "sync": sync}



@router.post("/api/trabajadores/sincronizar-todo")
async def api_sync_todos_trabajadores(
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    """Repara denormalizados de todos los trabajadores (una vez tras migrar datos)."""
    total = repo.sincronizar_todos_denormalizados()
    return {"ok": True, **total}



@router.get("/api/trabajadores/{trabajador_id}/desempeno")
async def api_desempeno_trabajador(
    trabajador_id: int,
    trab_repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
    trabajos_repo: TrabajosRepo = Depends(get_trabajos_repo),
):
    trab_repo.obtener(trabajador_id)
    return trabajos_repo.desempeno_trabajador(trabajador_id)



@router.get("/api/trabajadores/{trabajador_id}/qr.png")
async def api_trabajador_qr_png(
    trabajador_id: int,
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    """QR PNG. Payload: URL móvil /m/t/{id}."""
    from fastapi.responses import Response
    import io
    try:
        t = repo.obtener(trabajador_id)
        code = (t.get("codigo_qr") if isinstance(t, dict) else None) or f"FC{trabajador_id:06d}"
    except Exception:
        code = f"FC{trabajador_id:06d}"
    base = str(request.base_url).rstrip("/")
    payload = f"{base}/m/t/{trabajador_id}"
    try:
        import qrcode
        from qrcode.image.pil import PilImage
        qr = qrcode.QRCode(version=None, box_size=6, border=2)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return Response(
            content=buf.getvalue(),
            media_type="image/png",
            headers={"Cache-Control": "no-cache", "Content-Disposition": f'inline; filename="{code}.png"'},
        )
    except Exception as e:
        # SVG con el código legible si falta qrcode o Pillow
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="240" height="120">'
            f'<rect width="100%" height="100%" fill="#fff"/>'
            f'<text x="20" y="50" font-size="14" fill="#000">QR: {code}</text>'
            f'<text x="20" y="75" font-size="10" fill="#666">{payload[:40]}</text>'
            f'<text x="20" y="95" font-size="9" fill="#c00">pip install qrcode[pil] ({type(e).__name__})</text>'
            f"</svg>"
        )
        return Response(content=svg.encode("utf-8"), media_type="image/svg+xml")




@router.get("/trabajadores/qr-lote", response_class=HTMLResponse)
async def page_qr_lote(
    request: Request,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.web.qr_pages import response_qr_lote
    try:
        rows = repo.listar(solo_activos=True)
    except Exception:
        rows = []
    return response_qr_lote(rows)



@router.get("/trabajadores/{trabajador_id}/qr", response_class=HTMLResponse)
async def page_trabajador_qr(
    request: Request,
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.web.qr_pages import response_trabajador_qr
    t = None
    try:
        t = repo.obtener(trabajador_id)
    except Exception:
        pass
    return response_trabajador_qr(trabajador_id, t if isinstance(t, dict) else None)


