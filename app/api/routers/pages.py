"""Router: pages."""
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




@router.get("/buscar", response_class=HTMLResponse)
async def page_buscar(
    request: Request,
    q: str | None = None,
    svc: DashboardService = Depends(get_dashboard_service),
):
    q = (q or "").strip()
    data = svc.buscar(q)
    return templates.TemplateResponse(
        request,
        "buscar.html",
        _ctx(
            request,
            q=q,
            trabajadores=data.get("trabajadores") or [],
            semanas=data.get("semanas") or [],
            folios=data.get("folios") or [],
        ),
    )



@router.get("/estadisticas", response_class=HTMLResponse)
async def page_estadisticas(
    request: Request,
    vista: str = Query("trabajador"),
    q: str = Query(""),
):
    from app.services.stats_service import StatsService
    form_ids = request.query_params.getlist("semana_id")
    selected_ids = [int(x) for x in form_ids if str(x).isdigit()]
    svc = StatsService()
    semanas = svc.listar_semanas()
    if vista == "folio":
        rows = svc.stats_folio(q=q, semana_ids=selected_ids or None)
    else:
        vista = "trabajador"
        rows = svc.stats_trabajador(q=q, semana_ids=selected_ids or None)
    return templates.TemplateResponse(
        request,
        "estadisticas.html",
        _ctx(
            request,
            vista=vista,
            q=q,
            rows=rows,
            semanas=semanas,
            selected_ids=set(selected_ids),
        ),
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


