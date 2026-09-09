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
    get_trabajos_repo,
)
from app.core.exceptions import AppError
from app.db.repository import ProduccionRepo, ProduccionPitaRepo, NominaTallerRepo, SemanasRepo, TrabajadoresRepo, TrabajosRepo, CatalogosRepo
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

def get_catalogos_repo():
    from app.db.repository import CatalogosRepo
    return CatalogosRepo()


from app.web.context import build_template_context, to_template_value

def _ctx(request: Request, **kwargs):
    return build_template_context(request, **kwargs)


def _dev_page_payload(repo: TrabajadoresRepo, *, action_result=None, sync_result=None, error=None):
    from app.web.debug_pages import render_debug_page
    from app.services.dashboard_service import check_db
    from app import __version__
    data: dict = {
        "mismatches": [], "sample_vela": [], "columns": [], "counts": {},
        "orphans": [], "migrations": [], "folios_duplicados": [], "semana_actual": {},
    }
    try:
        data = repo.diagnostico_sync()
    except Exception as e:
        if error is None:
            error = str(e)
    lan = "—"
    try:
        from app.core.network import lan_urls
        from app.core.config import get_settings
        s = get_settings()
        port = int(getattr(s, "app_port", 8000) or 8000)
        urls = lan_urls(port=port)
        lan = f"{urls.get('ip')}:{port}"
    except Exception:
        pass
    apr = {}
    try:
        from app.services.aprendizaje_service import AprendizajeService
        apr = AprendizajeService().resumen_aprendizaje()
    except Exception as e:
        apr = {"tabla_ok": False, "error": str(e), "folios_inactivos": [], "candidatos_dup": []}
    return render_debug_page(
        db_ok=check_db(),
        columns=data.get("columns") or [],
        mismatches=data.get("mismatches") or [],
        sample_vela=data.get("sample_vela") or [],
        meta={"version": __version__, "lan": lan},
        counts=data.get("counts") or {},
        orphans=data.get("orphans") or [],
        migrations=data.get("migrations") or [],
        folios_dup=data.get("folios_duplicados") or [],
        semana_actual=data.get("semana_actual") or {},
        aprendizaje=apr,
        sync_result=sync_result,
        action_result=action_result,
        error=error,
    )




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
        from app.services.consistency_service import ConsistencyService
        from app.db.repository import ResumenRepo
        # Sincroniza resumen con captura (evita $0 en dashboard tras cerrar)
        try:
            ResumenRepo().recalcular_todas(12)
        except Exception:
            pass
        cons = ConsistencyService().revisar(auto_repair=False, limit_semanas=12)
    except Exception:
        cons = {"avisos": [], "n_avisos": 0}
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
            consistencia=cons,
            semanas=semanas,
            insights=avisos,
            tendencias=tendencias,
            db_ok=data.get("db_ok", True),
        ),
    )




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


@router.post("/api/trabajadores/merge")
async def api_merge_trabajadores(
    id_keep: int = Form(...),
    id_merge: int = Form(...),
):
    from app.services.aprendizaje_service import AprendizajeService
    return AprendizajeService().fusionar_trabajadores(id_keep, id_merge)


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


@router.post("/api/produccion/linea/{prod_id}/terminar")
async def api_linea_terminar(prod_id: int):
    from fastapi.responses import JSONResponse
    from app.services.aprendizaje_service import AprendizajeService
    try:
        result = AprendizajeService().marcar_folio_terminado(prod_id=prod_id)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result




@router.post("/api/produccion/terminar-lote")
async def api_terminar_lote(request: Request):
    """Termina folios sin avance (≥ min_semanas). Opcional: solo prod_ids seleccionados."""
    from fastapi.responses import JSONResponse
    from app.services.aprendizaje_service import AprendizajeService
    form = await request.form()
    semana_id = form.get("semana_id")
    try:
        semana_id = int(semana_id) if semana_id not in (None, "") else None
    except (TypeError, ValueError):
        semana_id = None
    try:
        min_semanas = int(form.get("min_semanas") or 2)
    except (TypeError, ValueError):
        min_semanas = 2
    prod_ids: list[int] = []
    # prod_ids, prod_ids[], o lista separada por comas
    raw_list = form.getlist("prod_ids") if hasattr(form, "getlist") else []
    if not raw_list:
        raw_list = form.getlist("prod_ids[]") if hasattr(form, "getlist") else []
    for item in raw_list:
        for part in str(item).split(","):
            part = part.strip()
            if part.isdigit():
                prod_ids.append(int(part))
    single = form.get("prod_ids")
    if single and not prod_ids:
        for part in str(single).split(","):
            part = part.strip()
            if part.isdigit():
                prod_ids.append(int(part))
    try:
        result = AprendizajeService().marcar_folios_terminados_lote(
            semana_id=semana_id,
            min_semanas=min_semanas,
            prod_ids=prod_ids or None,
        )
        return result
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)

@router.post("/api/produccion/linea/{prod_id}/reactivar")
async def api_linea_reactivar(prod_id: int):
    from fastapi.responses import JSONResponse
    from app.services.aprendizaje_service import AprendizajeService
    try:
        result = AprendizajeService().reactivar_folio(prod_id=prod_id)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
    if not result.get("ok"):
        return JSONResponse(result, status_code=400)
    return result



@router.get("/api/produccion/folio-meta")
async def api_folio_meta(
    folio: str,
    semana_id: int | None = None,
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """Características canónicas de un folio (modelo, material, tarifa)."""
    folio = (folio or "").strip()
    if not folio:
        return {"ok": False, "error": "folio vacío"}
    meta = repo.meta_por_folio(folio, semana_id=semana_id) or {}
    if not meta.get("tarifa_gr") and meta.get("material"):
        try:
            from app.db.repository import HistorialPreciosRepo
            sug = HistorialPreciosRepo().sugerir(meta.get("material"), meta.get("modelo"))
            if sug is not None:
                meta["tarifa_gr"] = sug
                meta["tarifa_fuente"] = "historial"
        except Exception:
            pass
    return {"ok": True, "folio": folio, **meta}


@router.post("/api/produccion/folio-sync")
async def api_folio_sync(
    folio: str = Form(...),
    modelo: str | None = Form(None),
    material: str | None = Form(None),
    tarifa_gr: float | None = Form(None),
    semana_id: int | None = Form(None),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """Aplica modelo/material/tarifa a todas las líneas con el mismo folio."""
    n = repo.sincronizar_folio(
        folio=folio,
        modelo=modelo,
        material=material,
        tarifa_gr=tarifa_gr,
        semana_id=semana_id,
    )
    return {"ok": True, "actualizadas": n, "folio": folio}


@router.get("/api/aprendizaje/resumen")
async def api_aprendizaje_resumen():
    from app.services.aprendizaje_service import AprendizajeService
    return AprendizajeService().resumen_aprendizaje()



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


@router.get("/asistente", response_class=HTMLResponse)
async def page_asistente(request: Request):
    """Asistente guiado para usuarios no técnicos."""
    from app.services.aprendizaje_service import AprendizajeService
    from app.services.dashboard_service import check_db
    from app import __version__
    apr = {}
    try:
        apr = AprendizajeService().resumen_aprendizaje()
    except Exception as e:
        apr = {"error": str(e), "candidatos_dup": [], "folios_inactivos": [], "reasignaciones": []}
    n_dup = len(apr.get("candidatos_dup") or [])
    n_fi = len(apr.get("folios_inactivos") or [])
    n_re = len(apr.get("reasignaciones") or [])
    html = f"""<!DOCTYPE html>
<html lang="es" data-theme="oscuro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Asistente — Fajos Central</title>
  <link rel="stylesheet" href="/static/app.css">
  <style>
    .wiz-steps {{ display:flex; gap:0.5rem; flex-wrap:wrap; margin:1rem 0; }}
    .wiz-step {{ padding:0.4rem 0.75rem; border-radius:999px; border:1px solid var(--border); font-size:0.85rem; }}
    .wiz-step.on {{ background: var(--accent); color:#1e1e2e; border-color:transparent; font-weight:600; }}
    .wiz-card {{ background:var(--surface); border:1px solid var(--border); border-radius:12px; padding:1.25rem; margin:1rem 0; }}
    .wiz-card h2 {{ margin-top:0; font-size:1.15rem; }}
    .wiz-num {{ display:inline-flex; width:1.6rem; height:1.6rem; align-items:center; justify-content:center;
                border-radius:50%; background:var(--accent); color:#1e1e2e; font-weight:700; margin-right:0.4rem; }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span>Fajos Piteados Central</span></a>
    <span class="version-badge">v{__version__}</span>
    <a class="dev-badge" href="/dev">Dev</a>
  </header>
  <main class="container page-enter">
    <div class="page-head">
      <div>
        <h1>Asistente de revisión</h1>
        <p class="muted">Pasos simples para limpiar duplicados y folios raros. No hace falta saber de bases de datos.</p>
      </div>
      <a class="btn btn-secondary" href="/">← Inicio</a>
    </div>

    <div class="wiz-steps">
      <span class="wiz-step on">1 · Resumen</span>
      <span class="wiz-step">2 · Duplicados</span>
      <span class="wiz-step">3 · Folios</span>
      <span class="wiz-step">4 · Listo</span>
    </div>

    <div class="wiz-card">
      <h2><span class="wiz-num">1</span> ¿Qué encontró el sistema?</h2>
      <ul>
        <li><strong>{n_dup}</strong> nombre(s) con más de una ficha (posibles duplicados)</li>
        <li><strong>{n_fi}</strong> folio(s) sin gramos esta semana</li>
        <li><strong>{n_re}</strong> folio(s) que cambiaron de persona vs la semana pasada</li>
      </ul>
      <p class="muted">BD: {"OK" if check_db() else "sin conexión"}</p>
    </div>

    <div class="wiz-card">
      <h2><span class="wiz-num">2</span> Unir personas duplicadas</h2>
      <p>Si la misma persona aparece dos veces (mismo nombre, distinta ubicación o ficha),
      hay que <strong>elegir cuál se queda</strong> y la otra se da de baja moviendo sus nóminas.</p>
      <a class="btn" href="/dev#dup">Ir a unir fichas (en Dev)</a>
    </div>

    <div class="wiz-card">
      <h2><span class="wiz-num">3</span> Revisar folios</h2>
      <p><strong>Sin avance:</strong> puede que el trabajo ya terminó → marca «terminado» o corrige en Plata.</p>
      <p><strong>Cambiaron de persona:</strong> confirma si el folio se reasignó o es un error de captura.</p>
      <a class="btn btn-secondary" href="/dev#folios">Ver folios en Dev</a>
      <a class="btn btn-secondary" href="/produccion">Abrir Plata</a>
    </div>

    <div class="wiz-card">
      <h2><span class="wiz-num">4</span> Captura del día</h2>
      <p>Cuando los datos estén limpios, usa <strong>Plata → + Un día</strong> para registrar gramos de hoy.</p>
      <a class="btn" href="/produccion">Ir a captura</a>
    </div>
  </main>
</body>
</html>"""
    return HTMLResponse(html)



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
    terminados_semana: list = []
    if semana_id:
        try:
            terminados_semana = prod_repo.listar_terminados_semana(semana_id)
        except Exception:
            terminados_semana = []
        try:
            from app.services.aprendizaje_service import AprendizajeService
            AprendizajeService().purgar_terminados(dias=7)
        except Exception:
            pass
    totales = prod_repo.totales_semana(semana_id) if semana_id else {}
    trabajadores = trab_repo.listar(solo_plt=False, solo_activos=True)
    folios_dup_set: set = set()
    try:
        for d in trab_repo.folios_duplicados(semana_id if semana_id else None):
            if d.get("folio"):
                folios_dup_set.add(str(d["folio"]).strip())
    except Exception:
        pass
    folio_inactivos: list = []
    reasignaciones: list = []
    folio_inact_ids: set = set()
    try:
        from app.services.aprendizaje_service import AprendizajeService
        apr = AprendizajeService()
        folio_inactivos = apr.detectar_folios_inactivos(semana_id)
        reasignaciones = apr.detectar_reasignaciones(semana_id)
        for x in folio_inactivos:
            if x.get("prod_id"):
                folio_inact_ids.add(int(x["prod_id"]))
    except Exception:
        folio_inactivos = []
        reasignaciones = []
        folio_inact_ids = set()
    materiales: list = []
    modelos: list = []
    try:
        from app.db.repository import CatalogosRepo
        _cat = CatalogosRepo()
        materiales = _cat.listar_materiales(solo_activos=True) or []
        # Modelos de Plata (PLT) + sin tipo / todos como sugerencia
        todos_mod = _cat.listar_modelos() or []
        modelos = [
            m for m in todos_mod
            if str(m.get("tipo") or "PLT").upper() in ("PLT", "PLATA", "")
        ] or todos_mod
    except Exception:
        materiales = []
        modelos = []
    # Precalcular lote (evita filtros Jinja frágiles)
    n_lote_inactivos = 0
    try:
        n_lote_inactivos = sum(
            1
            for x in folio_inactivos
            if int(x.get("semanas_inactivo") or 0) >= 2 and x.get("prod_id")
        )
    except Exception:
        n_lote_inactivos = 0
    return templates.TemplateResponse(
        request,
        "produccion.html",
        _ctx(
            request,
            semanas=semanas,
            semana_id=semana_id,
            lineas=lineas,
            totales=totales or {},
            trabajadores=trabajadores or [],
            materiales=materiales,
            modelos=modelos,
            semana_cerrada=bool(
                next((s for s in semanas if s.get("id") == semana_id), {}).get("cerrada")
            ) if semana_id else False,
            col_hoy=__import__("app.core.dias", fromlist=["col_hoy"]).col_hoy(),
            day_cols=["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"],
            folios_dup_set=list(folios_dup_set) if folios_dup_set else [],
            folio_inactivos=folio_inactivos or [],
            reasignaciones=reasignaciones or [],
            folio_inact_ids=list(folio_inact_ids) if folio_inact_ids else [],
            terminados_semana=terminados_semana or [],
            n_lote_inactivos=n_lote_inactivos,
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
        from app.core.calendar_util import encontrar_semana_por_rango
        existentes = sem_repo.listar()
        dest = encontrar_semana_por_rango(existentes, sab, vie)
        if not dest:
            dest = next(
                (s for s in existentes if s.get("codigo") == codigo and int(s.get("anio") or 0) in (0, sab.year, vie.year)),
                None,
            )
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
async def api_export_suministro(
    semana_id: int | None = None,
    extras: int = Query(2, ge=0, le=5),
    avances: int = Query(4, ge=2, le=10),
    papel: str = Query("letter"),
    tema: str = Query("material"),
    fuente: str = Query("normal"),
    modelo: int = Query(1, ge=0, le=1),
    mat: int = Query(1, ge=0, le=1),
    obs: int = Query(1, ge=0, le=1),
    folio: int = Query(1, ge=0, le=1),
    generico: int = Query(0, ge=0, le=1),
    reps: int = Query(3, ge=1, le=12),
    prod_repo: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    """
    Excel de suministro diario (vertical). generico=1: solo ubic+nombre, N reps.
    """
    avances = max(2, min(int(avances or 4), 10))
    from app.services.dia_service import DiaService
    from app.services.export_service import ExportService
    from app.core.calendar_util import encontrar_semana_actual, today
    from fastapi.responses import Response

    st = DiaService().estado_hoy()
    if semana_id is None:
        semanas = sem_repo.listar()
        actual = encontrar_semana_actual(semanas, today())
        semana_id = int(actual["id"]) if actual else (semanas[0]["id"] if semanas else None)
    lineas: list = []
    codigo = ""
    if semana_id:
        lineas = prod_repo.listar_por_semana(int(semana_id), incluir_terminados=False) or []
        sem = next((s for s in sem_repo.listar() if s.get("id") == semana_id), None) or {}
        codigo = sem.get("codigo") or ""
    # Si no hay líneas de semana, usar trabajos del día
    if not lineas:
        lineas = st.get("trabajos") or []
    content, media, filename = ExportService().export_suministro_diario(
        lineas,
        fecha_iso=st.get("fecha") or "",
        label_dia=st.get("label_dia") or "",
        codigo_semana=codigo,
        filas_extra_por_trabajador=extras,
        n_avances=avances,
        papel=papel,
        tema=tema,
        fuente=fuente,
        mostrar_modelo=bool(modelo),
        mostrar_mat=bool(mat),
        mostrar_obs=bool(obs),
        mostrar_folio=bool(folio),
        generico=bool(generico),
        reps_por_trabajador=reps,
    )
    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/suministro", response_class=HTMLResponse)
async def page_suministro(
    request: Request,
    semana_id: int | None = None,
    extras: int = Query(2, ge=0, le=5),
    avances: int = Query(4, ge=2, le=10),
    papel: str = Query("letter"),
    tema: str = Query("material"),
    fuente: str = Query("normal"),
    modelo: int = Query(1, ge=0, le=1),
    mat: int = Query(1, ge=0, le=1),
    obs: int = Query(1, ge=0, le=1),
    folio: int = Query(1, ge=0, le=1),
    generico: int = Query(0, ge=0, le=1),
    reps: int = Query(3, ge=1, le=12),
    prod_repo: ProduccionRepo = Depends(get_produccion_repo),
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
):
    """Vista imprimible del suministro del día (navegador → Imprimir)."""
    from app.services.dia_service import DiaService
    from app.core.calendar_util import encontrar_semana_actual, today
    from collections import OrderedDict
    avances = max(2, min(int(avances or 4), 10))
    generico_b = bool(generico)
    reps = max(1, min(12, int(reps or 3)))

    st = DiaService().estado_hoy()
    if semana_id is None:
        semanas = sem_repo.listar()
        actual = encontrar_semana_actual(semanas, today())
        semana_id = int(actual["id"]) if actual else (semanas[0]["id"] if semanas else None)
    lineas: list = []
    codigo = ""
    if semana_id:
        lineas = prod_repo.listar_por_semana(int(semana_id), incluir_terminados=False) or []
        sem = next((s for s in sem_repo.listar() if s.get("id") == semana_id), None) or {}
        codigo = sem.get("codigo") or ""
    if not lineas:
        lineas = st.get("trabajos") or []

    def _pk(r):
        try:
            u = int(float(r.get("ubic") or 0))
        except (TypeError, ValueError):
            u = 0
        return (u, str(r.get("nombre") or "").upper(), str(r.get("folio") or "").upper())

    lineas = sorted(lineas, key=_pk)
    groups: OrderedDict = OrderedDict()
    for r in lineas:
        try:
            u = int(float(r.get("ubic") or 0))
        except (TypeError, ValueError):
            u = 0
        key = (str(r.get("nombre") or "").strip().upper(), u)
        groups.setdefault(key, []).append(r)

    rows_out = []
    for (nk, ubic), items in groups.items():
        nombre = items[0].get("nombre") or nk
        if generico_b:
            for _ in range(reps):
                rows_out.append({
                    "nombre": nombre, "ubic": ubic,
                    "folio": "", "modelo": "", "material": "",
                    "blank": False,
                })
        else:
            for it in items:
                rows_out.append({
                    "nombre": nombre, "ubic": ubic,
                    "folio": it.get("folio") or "",
                    "modelo": it.get("modelo") or "",
                    "material": it.get("material") or "",
                    "blank": False,
                })
            for _ in range(max(0, extras)):
                rows_out.append({
                    "nombre": nombre, "ubic": ubic,
                    "folio": "", "modelo": "", "material": "",
                    "blank": True,
                })

    return templates.TemplateResponse(
        request,
        "suministro.html",
        _ctx(
            request,
            rows=rows_out,
            fecha=st.get("fecha"),
            label_dia=st.get("label_dia"),
            codigo_semana=codigo,
            semana_id=semana_id,
            extras=extras,
            avances=avances,
            papel=papel,
            tema=tema,
            fuente=fuente,
            mostrar_modelo=bool(modelo),
            mostrar_mat=bool(mat),
            mostrar_obs=bool(obs),
            mostrar_folio=bool(folio),
            generico=generico_b,
            reps=reps,
            total_lineas=len(lineas),
            n_avances=avances,
        ),
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
        prod = ProduccionRepo().listar_por_semana(actual["id"], incluir_terminados=True)
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


@router.get("/m/t/{trabajador_id}", response_class=HTMLResponse)
async def page_movil_trabajador(
    request: Request,
    trabajador_id: int,
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
    trabajos_repo: TrabajosRepo = Depends(get_trabajos_repo),
):
    from app.web.qr_pages import response_movil_trabajador
    t = None
    des = None
    try:
        t = repo.obtener(trabajador_id)
    except Exception:
        pass
    try:
        des = trabajos_repo.desempeno_trabajador(trabajador_id)
    except Exception:
        des = {}
    return response_movil_trabajador(
        trabajador_id, t if isinstance(t, dict) else None, des
    )


@router.post("/api/trabajos/{trabajo_id}/terminar")
async def api_terminar_trabajo(
    trabajo_id: int,
    terminar: int = Form(1),
    repo: TrabajosRepo = Depends(get_trabajos_repo),
):
    """Pregunta de negocio: ¿ya terminó el folio? terminar=1 sí, 0 reabrir."""
    row = repo.marcar_terminado(trabajo_id, terminado=bool(int(terminar)))
    return {"ok": True, "trabajo": row, "terminado": bool(int(terminar))}



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
        "lineas": repo.listar_por_semana(semana_id, incluir_terminados=True),
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
    """Alta de fila. Si ya existe (incluso terminada) la reabre y actualiza."""
    from app.core.normalize import canonical_name
    nombre_c = canonical_name(nombre)
    payload = {
        "nombre": nombre_c,
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
    }
    existing = None
    try:
        existing = repo.buscar_linea(
            semana_id,
            nombre_c,
            int(ubic),
            folio=folio,
            material=material,
            trabajador_id=trabajador_id,
            prefer_visibles=False,  # incluir terminadas para reabrir
        )
    except Exception:
        existing = None
    if existing is None and folio:
        # Fallback: mismo trabajador+folio en semana (cualquier material)
        try:
            for row in repo.listar_por_semana(semana_id, incluir_terminados=True):
                same_t = (
                    (trabajador_id and row.get("trabajador_id") == trabajador_id)
                    or (
                        str(row.get("nombre") or "").strip().upper() == nombre_c.upper()
                        and int(row.get("ubic") or -1) == int(ubic)
                    )
                )
                same_f = str(row.get("folio") or "").strip().upper() == str(folio or "").strip().upper()
                if same_t and same_f:
                    existing = row
                    break
        except Exception:
            pass
    if existing:
        pid = int(existing["id"])
        try:
            repo.reabrir_linea_si_terminada(pid)
        except Exception:
            pass
        upd = {
            k: payload[k]
            for k in ("folio", "modelo", "material", "tarifa_gr",
                      "gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie")
            if payload.get(k) is not None and str(payload.get(k)).strip() != ""
        }
        if upd:
            try:
                repo.actualizar_linea(pid, upd)
            except Exception:
                # gramos día a día si falla bloque
                for d in ("gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"):
                    if d in upd and upd[d] is not None:
                        try:
                            repo.actualizar_gramos_dia(pid, d, float(upd[d]))
                        except Exception:
                            pass
        try:
            from app.db.repository import HistorialPreciosRepo
            HistorialPreciosRepo().registrar(
                payload.get("material") or "",
                payload.get("tarifa_gr") or 0,
                payload.get("modelo"),
                fuente="reabrir_fila",
                semana_id=semana_id,
                prod_id=pid,
            )
        except Exception:
            pass
        return {
            "id": pid,
            "ok": True,
            "reopened": True,
            "message": "Fila existente reabierta/actualizada (folio antes cerrado o duplicado).",
        }
    new_id = repo.insertar(semana_id, payload)
    try:
        from app.db.repository import HistorialPreciosRepo
        HistorialPreciosRepo().registrar(
            payload.get("material") or "",
            payload.get("tarifa_gr") or 0,
            payload.get("modelo"),
            fuente="alta_fila",
            semana_id=semana_id,
            prod_id=new_id,
        )
    except Exception:
        pass
    return {"id": new_id, "ok": True, "reopened": False}




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
    existing = None
    try:
        existing = repo.buscar_linea(
            semana_id,
            nombre_c,
            int(ubic),
            folio=folio,
            material=material,
            trabajador_id=trabajador_id,
            prefer_visibles=True,
        )
    except Exception:
        existing = None
    if existing is None and trabajo_id:
        try:
            for row in repo.listar_por_semana(semana_id, incluir_terminados=True):
                if row.get("trabajo_id") == trabajo_id:
                    existing = row
                    break
        except Exception:
            pass
    if existing:
        pid = int(existing["id"])
        # Si estaba terminada/oculta, reabrir para que se vea en la tabla
        try:
            repo.reabrir_linea_si_terminada(pid)
        except Exception:
            pass
        # Valor previo del día (para respuesta clara)
        prev = None
        try:
            full = repo.obtener(pid) or existing
            prev = full.get(col)
        except Exception:
            prev = existing.get(col)
        repo.actualizar_gramos_dia(pid, col, gramos)
        row = repo.obtener(pid) or {}
        return {
            "id": pid,
            "ok": True,
            "dia": dia,
            "gramos": gramos,
            "gramos_previos": float(prev) if prev not in (None, "") else 0,
            "updated": True,
            "total_gramos": float(row.get("total_gramos") or 0) if row else None,
            "visible": True,
        }
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
    row = repo.obtener(new_id) or {}
    return {
        "id": new_id,
        "ok": True,
        "dia": dia,
        "gramos": gramos,
        "updated": False,
        "total_gramos": float(row.get("total_gramos") or 0) if row else None,
        "visible": True,
    }




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



@router.get("/api/export/produccion/{semana_id}/captura-manual")
async def api_export_captura_manual(
    semana_id: int,
    sem_repo: SemanasRepo = Depends(get_semanas_repo),
    prod_repo: ProduccionRepo = Depends(get_produccion_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Nómina en blanco para captura manual: sin precios, total gramos, fila extra por trabajador."""
    semana = sem_repo.obtener(semana_id)
    if not semana:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Semana no encontrada")
    # Activas (también sin gramos); excluye folios terminados/cerrados
    lineas = prod_repo.listar_por_semana(semana_id, incluir_terminados=False)
    content, media_type, filename = export_svc.export_captura_manual(
        lineas,
        codigo_semana=str(semana.get("codigo") or ""),
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@router.get("/api/export/trabajadores")
async def api_export_trabajadores(
    activos: int | None = Query(None, description="1=solo activos, 0=solo bajas, omitir=todos"),
    q: str | None = Query(None),
    repo: TrabajadoresRepo = Depends(get_trabajadores_repo),
    export_svc: ExportService = Depends(get_export_service),
):
    """Excel del catálogo de trabajadores."""
    solo_activos = True if activos == 1 else (False if activos == 0 else False)
    # listar: solo_activos True filtra activos; False lista todos
    if activos is None:
        rows = repo.listar(solo_activos=False, busqueda=q)
        flag = None
        stem = "trabajadores_todos"
    elif activos == 1:
        rows = repo.listar(solo_activos=True, busqueda=q)
        flag = True
        stem = "trabajadores_activos"
    else:
        rows = [r for r in repo.listar(solo_activos=False, busqueda=q) if not r.get("activo")]
        flag = False
        stem = "trabajadores_bajas"
    data, media, fname = export_svc.export_trabajadores(rows, filename_stem=stem, solo_activos=flag)
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


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
    # Activas + con gramos; folios terminados fuera de cualquier export
    lineas = prod_repo.listar_por_semana(semana_id, incluir_terminados=False)
    from app.services.export_service import filtrar_lineas_export
    lineas = filtrar_lineas_export(lineas, solo_con_gramos=True)
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
    # Regla fija: no exportar filas en 0 (solo líneas con sueldo/extras/total > 0)
    todas = list(repo.listar_por_semana(semana_id))
    lineas = [
        r for r in todas
        if float(r.get("total") or 0) > 0
        or float(r.get("sueldo") or 0) > 0
        or float(r.get("extras") or 0) > 0
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


@router.get("/api/export/nomina-pita/{semana_id}/preview")
async def api_export_pita_preview(
    semana_id: int,
    repo: ProduccionPitaRepo = Depends(get_produccion_pita_repo),
):
    """Cuenta filas totales vs exportables (efectivo > 0)."""
    todas = list(repo.listar_por_semana(semana_id))
    exportables = [r for r in todas if float(r.get("efectivo") or 0) > 0]
    return {
        "ok": True,
        "total": len(todas),
        "exportables": len(exportables),
        "omitidas": len(todas) - len(exportables),
        "regla": "Solo filas con efectivo > 0",
    }


@router.get("/api/export/nomina-taller/{semana_id}/preview")
async def api_export_taller_preview(
    semana_id: int,
    repo: NominaTallerRepo = Depends(get_nomina_taller_repo),
):
    """Cuenta filas totales vs exportables (monto > 0)."""
    todas = list(repo.listar_por_semana(semana_id))
    exportables = [
        r for r in todas
        if float(r.get("total") or 0) > 0
        or float(r.get("sueldo") or 0) > 0
        or float(r.get("extras") or 0) > 0
    ]
    return {
        "ok": True,
        "total": len(todas),
        "exportables": len(exportables),
        "omitidas": len(todas) - len(exportables),
        "regla": "Solo filas con sueldo/extras/total > 0",
    }


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
    # Regla fija: no exportar filas con efectivo en 0 (solo lo ya liquidado/llenado)
    todas = list(repo.listar_por_semana(semana_id))
    lineas = [
        r for r in todas
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


@router.get("/catalogos", response_class=HTMLResponse)
async def page_catalogos(request: Request):
    from app.db.repository import CatalogosRepo
    cat = CatalogosRepo()
    materiales = cat.listar_materiales(solo_activos=False)
    modelos = cat.listar_modelos()
    return templates.TemplateResponse(
        request,
        "catalogos.html",
        _ctx(request, materiales=materiales, modelos=modelos),
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
