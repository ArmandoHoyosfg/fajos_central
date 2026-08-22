"""
Rutas API REST + páginas web.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from pathlib import Path

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
)
from app.core.exceptions import AppError
from app.db.repository import ProduccionRepo, ProduccionPitaRepo, NominaTallerRepo, SemanasRepo, TrabajadoresRepo
from app.services.dashboard_service import DashboardService
from app.services.export_service import ExportService, linea_tiene_gramos

TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "web" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

def _jinja_tojson_safe(value):
    """tojson que soporta Decimal/date (evita TypeError en templates)."""
    from app.core.jsonutil import dumps_safe
    return Markup(dumps_safe(value, ensure_ascii=False))

templates.env.filters["tojson"] = _jinja_tojson_safe
templates.env.policies["json.dumps_function"] = lambda obj, **kw: __import__(
    "app.core.jsonutil", fromlist=["dumps_safe"]
).dumps_safe(obj, **kw)


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
    insights=Depends(get_insights_service),
):
    from app.core.calendar_util import marcar_semanas
    data = svc.get_dashboard()
    semanas = marcar_semanas(data["ultimas_semanas"])
    try:
        avisos = insights.avisos_hoy() if data.get("db_ok", True) else {"avisos": [], "resumen": {"n": 0}}
    except Exception:
        avisos = {"avisos": [], "resumen": {"n": 0}}
    try:
        tendencias = insights.tendencias(8) if data.get("db_ok", True) else {"serie": [], "comparacion": None, "top_materiales": []}
    except Exception:
        tendencias = {"serie": [], "comparacion": None, "top_materiales": []}
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        _ctx(
            request,
            kpis=data["kpis"],
            semanas=semanas,
            insights=avisos,
            tendencias=tendencias,
            db_ok=data.get("db_ok", True),
        ),
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
        # Catálogo de trabajos + gramos de hoy de la semana
        col = col_hoy()
        trabajos = TrabajosRepo().listar_con_semana(semana_id, solo_activos=False)
        for r in trabajos:
            try:
                g = float(r.get(col) or 0)
            except (TypeError, ValueError):
                g = 0.0
            r["gramos_hoy"] = g if g > 0 else None
            activo = bool(r.get("trabajo_activo", 1))
            r["trabajo_activo"] = activo
            r["sin_hoy"] = activo and g <= 0
            if not r.get("trabajo_id"):
                r["trabajo_id"] = r.get("id")
        sin = [r for r in trabajos if r.get("sin_hoy")]
        sin_hoy_count = len(sin)
        if sin:
            names = ", ".join(f"{x.get('nombre')}[{x.get('folio') or '—'}]" for x in sin[:6])
            extra = f" (+{len(sin)-6})" if len(sin) > 6 else ""
            recordatorio = (
                f"Sin gramos de {DAY_LABELS[col]} en {len(sin)} trabajo(s) activo(s): {names}{extra}"
            )
        cerrada = bool(
            next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")
        )
    else:
        sin_hoy_count = 0
    return templates.TemplateResponse(
        request,
        "trabajos.html",
        _ctx(
            request,
            semanas=semanas,
            semana_id=semana_id,
            trabajos=trabajos,
            recordatorio=recordatorio,
            sin_hoy_count=locals().get("sin_hoy_count", 0),
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
    row = repo.obtener(prod_id)
    out = {"ok": True, "prod_id": prod_id, "dia": dia, "gramos": gramos}
    if row:
        try:
            out["total_gramos"] = float(row.get("total_gramos") or 0)
            out["total_efectivo"] = float(row.get("total_efectivo") or 0)
        except (TypeError, ValueError):
            pass
    return out


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




@router.patch("/api/produccion/linea/{prod_id}")
async def api_patch_produccion_linea(
    prod_id: int,
    request: Request,
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """Actualiza fila completa de Plata (metadatos y/o gramos diarios)."""
    form = await request.form()
    data = {}
    for key in ("folio", "modelo", "material", "notas"):
        if key in form:
            data[key] = str(form.get(key) or "").strip() or None
    if "tarifa_gr" in form:
        data["tarifa_gr"] = str(form.get("tarifa_gr") or "").strip()
    if "firmado" in form:
        data["firmado"] = form.get("firmado")
    for d in ("gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"):
        if d in form:
            data[d] = str(form.get(d) or "").strip()
    if not data:
        return {"ok": True, "id": prod_id, "unchanged": True}
    repo.actualizar_linea(prod_id, data)
    return {"ok": True, "id": prod_id, "updated": list(data.keys())}

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
        _ctx(
            request, semanas=semanas, semana_id=semana_id, lineas=lineas, totales=totales, trabajadores=trabajadores,
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
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Excel formal de nómina Pita (imprimible). Sin bloque de totales generales."""
    sem = sem_repo.obtener(semana_id)
    if not sem:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    lineas = [
        r for r in repo.listar_por_semana(semana_id)
        if float(r.get("efectivo") or 0) > 0
    ]
    codigo = sem.get("codigo") or str(semana_id)
    data, media, fname = export_svc.export_nomina_pita(
        lineas, codigo_semana=codigo, filename_stem=f"nomina_pita_{codigo}", resumen=None
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


def _parse_num(val: str | None, default=None, allow_empty_none: bool = True):
    """Convierte string de formulario a float de forma segura."""
    if val is None:
        return default
    s = str(val).strip().replace(",", ".")
    if s == "":
        return None if allow_empty_none else 0.0
    try:
        return float(s)
    except ValueError as e:
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError(f"Valor numérico inválido: {val!r}") from e


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
    """Actualiza solo los campos enviados en el formulario."""
    form = await request.form()
    data = {}
    if "puesto" in form:
        v = str(form.get("puesto") or "").strip()
        data["puesto"] = v or None
    if "sueldo" in form:
        data["sueldo"] = _parse_num(str(form.get("sueldo")), default=0, allow_empty_none=False) or 0
    if "extras" in form:
        data["extras"] = _parse_num(str(form.get("extras")), default=0, allow_empty_none=False) or 0
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
    return {"ok": True, "id": row_id, "updated": list(data.keys())}


@router.get("/api/export/master")
async def api_export_master(
    export_svc: ExportService = Depends(get_export_service),
):
    """Descarga Excel Master con toda la base operativa (multi-hoja)."""
    content, media_type, filename = export_svc.export_master()
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get("/solo-hoy", response_class=HTMLResponse)
async def page_solo_hoy(
    request: Request,
    insights=Depends(get_insights_service),
):
    data = insights.captura_solo_hoy()
    return templates.TemplateResponse(
        request,
        "solo_hoy.html",
        _ctx(request, captura=data),
    )


@router.get("/api/insights/tendencias")
async def api_tendencias(limit: int = 8, svc=Depends(get_insights_service)):
    return svc.tendencias(limit_semanas=min(max(limit, 3), 16))


@router.get("/api/insights/solo-hoy")
async def api_solo_hoy(svc=Depends(get_insights_service)):
    return svc.captura_solo_hoy()


@router.patch("/api/trabajos/{trabajo_id}")
async def api_patch_trabajo(trabajo_id: int, request: Request):
    from app.db.repository import TrabajosRepo
    form = await request.form()
    data = {}
    for k in ("folio", "modelo", "material", "notas"):
        if k in form:
            data[k] = str(form.get(k) or "").strip() or None
    if "tarifa_gr" in form:
        data["tarifa_gr"] = str(form.get("tarifa_gr") or "").strip()
    if "activo" in form:
        data["activo"] = form.get("activo")
    TrabajosRepo().actualizar_meta(trabajo_id, data)
    return {"ok": True, "id": trabajo_id}


@router.post("/api/trabajos/{trabajo_id}/desactivar")
async def api_desactivar_trabajo(trabajo_id: int):
    from app.db.repository import TrabajosRepo
    TrabajosRepo().set_activo(trabajo_id, False)
    return {"ok": True, "id": trabajo_id, "activo": False}


@router.post("/api/trabajos/{trabajo_id}/activar")
async def api_activar_trabajo(trabajo_id: int):
    from app.db.repository import TrabajosRepo
    TrabajosRepo().set_activo(trabajo_id, True)
    return {"ok": True, "id": trabajo_id, "activo": True}


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
