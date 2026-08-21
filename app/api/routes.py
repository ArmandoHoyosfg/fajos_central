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
    get_produccion_pita_repo,
    get_nomina_taller_repo,
    get_semanas_repo,
    get_trabajadores_repo,
)
from app.core.exceptions import AppError
from app.db.repository import ProduccionRepo, ProduccionPitaRepo, NominaTallerRepo, SemanasRepo, TrabajadoresRepo
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService, linea_tiene_gramos

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
            col_hoy=__import__("app.core.dias", fromlist=["col_hoy"]).col_hoy(),
            day_cols=["gm_sab","gm_dom","gm_lun","gm_mar","gm_mie","gm_jue","gm_vie"],
        ),
    )




@router.get("/trabajos", response_class=HTMLResponse)
async def page_trabajos(
    request: Request,
    semana_id: int | None = None,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    from app.core.calendar_util import encontrar_semana_actual, marcar_semanas, today
    from app.core.dias import DAY_LABELS, col_hoy, trabajos_sin_gramos_hoy
    from app.db.repository import TrabajosRepo

    semanas_raw = sem_repo.listar()
    semanas = marcar_semanas(semanas_raw)
    if semana_id is None and semanas:
        actual = encontrar_semana_actual(semanas_raw, today())
        semana_id = actual["id"] if actual else semanas[0]["id"]
    trabajos = []
    recordatorio = None
    cerrada = False
    if semana_id:
        trabajos = TrabajosRepo().listar_con_semana(semana_id, solo_activos=True)
        col = col_hoy()
        for r in trabajos:
            try:
                g = float(r.get(col) or 0)
            except (TypeError, ValueError):
                g = 0
            r["sin_hoy"] = g <= 0
        sin = [r for r in trabajos if r["sin_hoy"]]
        if sin:
            names = ", ".join(f"{x.get('nombre')}[{x.get('folio') or '—'}]" for x in sin[:8])
            extra = f" (+{len(sin)-8})" if len(sin) > 8 else ""
            recordatorio = (
                f"Aún no hay gramos de {DAY_LABELS[col]} en {len(sin)} trabajo(s): {names}{extra}"
            )
        cerrada = bool(
            next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")
        )
    return templates.TemplateResponse(
        request,
        "trabajos.html",
        _ctx(
            request,
            semanas=semanas,
            semana_id=semana_id,
            trabajos=trabajos,
            recordatorio=recordatorio,
            col_hoy=col_hoy(),
            col_hoy_label=DAY_LABELS[col_hoy()],
            day_cols=["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"],
            semana_cerrada=cerrada,
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
async def api_trabajos(
    solo_activos: bool = True,
    trabajador_id: int | None = None,
    semana_id: int | None = None,
):
    from app.db.repository import TrabajosRepo
    repo = TrabajosRepo()
    if semana_id is not None:
        return repo.listar_con_semana(semana_id, solo_activos=solo_activos)
    return repo.listar(solo_activos=solo_activos, trabajador_id=trabajador_id)




@router.get("/api/dia/estado")
async def api_dia_estado():
    from app.services.dia_service import DiaService
    return DiaService().estado_hoy()


@router.post("/api/dia/cerrar")
async def api_dia_cerrar(usuario: str | None = Form("web")):
    from app.services.dia_service import DiaService
    return DiaService().cerrar_hoy(usuario=usuario or "web")


@router.get("/api/dia/avisos")
async def api_dia_avisos():
    from app.services.dia_service import DiaService
    return {"avisos": DiaService().avisos_apertura()}


@router.post("/api/produccion/{semana_id}/duplicar")
async def api_duplicar(
    semana_id: int,
    destino_id: int | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    from app.services.dia_service import siguiente_rango_semana
    from app.core.calendar_util import parse_db_date

    origen = sem_repo.obtener(semana_id)
    if not origen:
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError('Semana origen no encontrada')
    if destino_id is None:
        ff = parse_db_date(origen.get("fecha_fin"))
        if not ff:
            from app.core.exceptions import ValidationAppError
            raise ValidationAppError("Semana origen sin fecha_fin")
        codigo, sab, vie = siguiente_rango_semana(ff)
        existentes = sem_repo.listar()
        dest = next((s for s in existentes if s.get("codigo") == codigo), None)
        if dest:
            destino_id = dest["id"]
        else:
            destino_id = sem_repo.crear({
                "codigo": codigo,
                "fecha_inicio": sab.isoformat(),
                "fecha_fin": vie.isoformat(),
                "anio": sab.year,
                "notas": "Duplicada desde " + str(origen.get("codigo")),
            })
    result = repo.duplicar_trabajos_a_semana(semana_id, int(destino_id))
    result["destino_id"] = destino_id
    return result


@router.get("/api/export/suministro")
async def api_export_suministro():
    from app.services.dia_service import DiaService
    from app.services.export_service import ExportService, linea_tiene_gramos
    from fastapi.responses import Response
    st = DiaService().estado_hoy()
    # simple xlsx via openpyxl in export or reuse bytes
    from openpyxl import Workbook
    from io import BytesIO
    wb = Workbook()
    ws = wb.active
    ws.title = "Suministro"
    ws["A1"] = "SUMINISTRO DIARIO — " + st["fecha"] + " — " + st["label_dia"]
    headers = ["#", "Nombre", "Ubic", "Folio", "Modelo", "Mat", "Gramos", "Notas"]
    for c, h in enumerate(headers, 1):
        ws.cell(row=3, column=c, value=h)
    for i, r in enumerate(st.get("trabajos") or []):
        ws.cell(row=4+i, column=1, value=i+1)
        ws.cell(row=4+i, column=2, value=r.get("nombre"))
        ws.cell(row=4+i, column=3, value=r.get("ubic"))
        ws.cell(row=4+i, column=4, value=r.get("folio"))
        ws.cell(row=4+i, column=5, value=r.get("modelo"))
        ws.cell(row=4+i, column=6, value=r.get("material"))
    buf = BytesIO()
    wb.save(buf)
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="suministro.xlsx"'},
    )


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
    nombre_completo: str | None = Form(None),
    notas: str | None = Form(None),
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
):
    from app.core.normalize import canonical_name
    new_id = repo.agregar({
        "nombre_mostrar": canonical_name(nombre_mostrar),
        "nombre_completo": (nombre_completo or nombre_mostrar).strip(),
        "ubic": ubic,
        "tipo": tipo,
        "puesto": puesto,
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
    if fecha_incorporacion is not None:
        data["fecha_incorporacion"] = fecha_incorporacion or None
    if notas is not None:
        data["notas"] = notas or None
    if activo is not None:
        data["activo"] = 1 if int(activo) else 0
    return repo.actualizar(trabajador_id, data)


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
    trabajo_id: int | None = Form(None),
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
        "trabajo_id": trabajo_id,
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
    trabajo_id: int | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """
    Alta rápida de un día. Si ya existe línea (mismo trabajador+folio+material)
    actualiza ese día; si no, crea línea ligada a trabajo.
    """
    from app.core.normalize import canonical_name
    day_map = {
        "sab": "gm_sab", "dom": "gm_dom", "lun": "gm_lun", "mar": "gm_mar",
        "mie": "gm_mie", "jue": "gm_jue", "vie": "gm_vie",
        "gm_sab": "gm_sab", "gm_dom": "gm_dom", "gm_lun": "gm_lun", "gm_mar": "gm_mar",
        "gm_mie": "gm_mie", "gm_jue": "gm_jue", "gm_vie": "gm_vie",
    }
    col = day_map.get((dia or "").strip().lower())
    if not col:
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError(f"Día inválido: {dia}")
    nombre_c = canonical_name(nombre)
    # buscar línea existente
    existing = None
    try:
        existing = repo.buscar_linea(semana_id, nombre_c, int(ubic), folio)
    except Exception:
        existing = None
    if existing is None and trabajo_id:
        for row in repo.listar_por_semana(semana_id):
            if row.get("trabajo_id") == trabajo_id:
                existing = row
                break
    if existing:
        repo.actualizar_gramos_dia(int(existing["id"]), col, gramos)
        return {"id": existing["id"], "ok": True, "dia": dia, "gramos": gramos, "updated": True}
    payload = {
        "nombre": nombre_c,
        "ubic": ubic,
        "folio": folio,
        "modelo": modelo,
        "material": material,
        "tarifa_gr": tarifa_gr,
        "trabajador_id": trabajador_id,
        "trabajo_id": trabajo_id,
        "gm_sab": None, "gm_dom": None, "gm_lun": None,
        "gm_mar": None, "gm_mie": None, "gm_jue": None, "gm_vie": None,
    }
    payload[col] = gramos
    new_id = repo.insertar(semana_id, payload)
    return {"id": new_id, "ok": True, "dia": dia, "gramos": gramos, "updated": False}


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
    if not semana:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    lineas = prod_repo.listar_por_semana(semana_id)
    # Formal (y siempre limpio): solo filas con gramos en al menos un día
    lineas = [r for r in lineas if linea_tiene_gramos(r)]
    if formal:
        def _key(row: dict):
            try:
                u = int(row.get("ubic") or 0)
            except (TypeError, ValueError):
                u = 0
            return (u, str(row.get("nombre") or "").upper(), str(row.get("folio") or "").upper())
        lineas = sorted(lineas, key=_key)
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


# ---------- Taller (TLL) y Pita (PIT) ----------

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
        _ctx(request, semanas=semanas, semana_id=semana_id, lineas=lineas, totales=totales, trabajadores=trabajadores),
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
        _ctx(request, semanas=semanas, semana_id=semana_id, lineas=lineas, totales=totales, trabajadores=trabajadores),
    )


@router.post("/api/nomina-taller/{semana_id}")
async def api_add_taller(
    semana_id: int,
    nombre: str = Form(...),
    ubic: int = Form(...),
    puesto: str | None = Form(None),
    sueldo: float = Form(0),
    extras: float = Form(0),
    trabajador_id: int | None = Form(None),
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    new_id = repo.insertar(semana_id, {
        "nombre": nombre, "ubic": ubic, "puesto": puesto,
        "sueldo": sueldo, "extras": extras, "trabajador_id": trabajador_id,
    })
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


@router.get("/api/export/nomina-taller/{semana_id}")
async def api_export_taller(
    semana_id: int,
    include_resumen: int = Query(1),
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
    pit: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    plt: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Excel formal de nómina Taller (imprimible)."""
    sem = sem_repo.obtener(semana_id)
    if not sem:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    lineas = [
        r for r in repo.listar_por_semana(semana_id)
        if float(r.get("total") or 0) > 0 or float(r.get("sueldo") or 0) > 0 or float(r.get("extras") or 0) > 0
    ]
    resumen = None
    if include_resumen:
        t_plt = plt.totales_semana(semana_id)
        t_pit = pit.totales(semana_id)
        t_tll = repo.totales(semana_id)
        resumen = {
            "nomina_taller": float(t_tll.get("total") or 0),
            "nomina_plata": float(t_plt.get("total_efectivo") or 0),
            "nomina_pita": float(t_pit.get("total") or 0),
        }
    codigo = sem.get("codigo") or str(semana_id)
    data, media, fname = export_svc.export_nomina_taller(
        lineas, codigo_semana=codigo, filename_stem=f"nomina_taller_{codigo}", resumen=resumen
    )
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/export/nomina-pita/{semana_id}")
async def api_export_pita(
    semana_id: int,
    include_resumen: int = Query(1),
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    tll: NominaTallerRepo = Depends(get_nomina_taller_repo),
    plt: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Excel formal de nómina Pita (imprimible)."""
    sem = sem_repo.obtener(semana_id)
    if not sem:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    lineas = [
        r for r in repo.listar_por_semana(semana_id)
        if float(r.get("efectivo") or 0) > 0
    ]
    resumen = None
    if include_resumen:
        t_plt = plt.totales_semana(semana_id)
        t_pit = repo.totales(semana_id)
        t_tll = tll.totales(semana_id)
        resumen = {
            "nomina_taller": float(t_tll.get("total") or 0),
            "nomina_plata": float(t_plt.get("total_efectivo") or 0),
            "nomina_pita": float(t_pit.get("total") or 0),
        }
    codigo = sem.get("codigo") or str(semana_id)
    data, media, fname = export_svc.export_nomina_pita(
        lineas, codigo_semana=codigo, filename_stem=f"nomina_pita_{codigo}", resumen=resumen
    )
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/api/export/resumen/{semana_id}")
async def api_export_resumen(
    semana_id: int,
    repo_tll: NominaTallerRepo = Depends(get_nomina_taller_repo),
    repo_pit: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    plt: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Excel solo con el bloque de totales (Taller + Plata + Pita + Total)."""
    sem = sem_repo.obtener(semana_id)
    if not sem:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    t_plt = plt.totales_semana(semana_id)
    t_pit = repo_pit.totales(semana_id)
    t_tll = repo_tll.totales(semana_id)
    codigo = sem.get("codigo") or str(semana_id)
    data, media, fname = export_svc.export_resumen_tres_nominas(
        codigo_semana=codigo,
        nomina_taller=float(t_tll.get("total") or 0),
        nomina_plata=float(t_plt.get("total_efectivo") or 0),
        nomina_pita=float(t_pit.get("total") or 0),
        filename_stem=f"resumen_nominas_{codigo}",
    )
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
