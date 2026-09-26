"""Router: produccion."""
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



@router.post("/api/produccion/linea/{prod_id}/duplicar")
async def api_duplicar_linea(
    prod_id: int,
    material: str = Form("DOL"),
    repo: ProduccionRepo = Depends(get_produccion_repo),
):
    """
    Duplica una línea de Plata con otro material (p. ej. DOL).
    Copia folio/modelo/trabajador; gramos en blanco; tarifa del catálogo si existe.
    Si ya hay fila activa misma semana+trabajador+folio+material → la reutiliza.
    """
    from fastapi.responses import JSONResponse
    from app.core.normalize import canonical_name

    src = repo.obtener(prod_id)
    if not src:
        return JSONResponse({"ok": False, "error": "Línea no encontrada"}, status_code=404)

    material = (material or "DOL").strip().upper() or "DOL"
    semana_id = int(src["semana_id"])
    nombre = canonical_name(src.get("nombre") or "")
    try:
        ubic = int(src.get("ubic") or 0)
    except (TypeError, ValueError):
        ubic = 0
    folio = (src.get("folio") or "").strip() or None
    modelo = src.get("modelo")
    trabajador_id = src.get("trabajador_id")

    # Tarifa: catálogo de materiales → historial → tarifa origen
    tarifa = None
    try:
        from app.db.repository import CatalogosRepo
        mats = CatalogosRepo().listar_materiales(solo_activos=True)
        for m in mats or []:
            if str(m.get("material") or "").strip().upper() == material:
                tarifa = float(m.get("tarifa_por_gramo") or m.get("tarifa_gr") or 0) or None
                break
    except Exception:
        pass
    if tarifa is None:
        try:
            from app.db.repository import HistorialPreciosRepo
            sug = HistorialPreciosRepo().sugerir(material, modelo)
            if sug is not None:
                tarifa = float(sug)
        except Exception:
            pass
    if tarifa is None:
        try:
            tarifa = float(src.get("tarifa_gr") or 12)
        except (TypeError, ValueError):
            tarifa = 12.0

    # ¿Ya existe misma combinación?
    existing = None
    try:
        for row in repo.listar_por_semana(semana_id, incluir_terminados=True):
            same_t = (
                (trabajador_id and row.get("trabajador_id") == trabajador_id)
                or (
                    str(row.get("nombre") or "").strip().upper() == nombre.upper()
                    and int(row.get("ubic") or -1) == ubic
                )
            )
            same_f = str(row.get("folio") or "").strip().upper() == str(folio or "").strip().upper()
            same_m = str(row.get("material") or "").strip().upper() == material
            if same_t and same_f and same_m:
                existing = row
                break
    except Exception:
        existing = None

    if existing:
        pid = int(existing["id"])
        try:
            repo.reabrir_linea_si_terminada(pid)
        except Exception:
            pass
        # Actualizar tarifa si venía vacía
        try:
            if existing.get("tarifa_gr") in (None, "", 0) and tarifa:
                repo.actualizar_linea(pid, {"tarifa_gr": tarifa, "material": material})
        except Exception:
            pass
        return {
            "ok": True,
            "id": pid,
            "reused": True,
            "material": material,
            "message": f"Ya existía en {material}; se reactivó/reutilizó.",
        }

    # No clonar trabajo_id (material distinto = línea distinta)
    new_id = repo.insertar(semana_id, {
        "nombre": nombre,
        "ubic": ubic,
        "folio": folio,
        "modelo": modelo,
        "material": material,
        "tarifa_gr": tarifa,
        "trabajador_id": trabajador_id,
        "trabajo_id": None,
        "gm_sab": None, "gm_dom": None, "gm_lun": None,
        "gm_mar": None, "gm_mie": None, "gm_jue": None, "gm_vie": None,
    })
    try:
        from app.db.repository import HistorialPreciosRepo
        HistorialPreciosRepo().registrar(
            material, tarifa, modelo, fuente="duplicar_material",
            semana_id=semana_id, prod_id=new_id,
        )
    except Exception:
        pass
    return {
        "ok": True,
        "id": new_id,
        "reused": False,
        "material": material,
        "tarifa_gr": tarifa,
        "message": f"Fila duplicada en {material}.",
    }




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



@router.post("/api/trabajos/{trabajo_id}/terminar")
async def api_terminar_trabajo(
    trabajo_id: int,
    terminar: int = Form(1),
    repo: TrabajosRepo = Depends(get_trabajos_repo),
):
    """Pregunta de negocio: ¿ya terminó el folio? terminar=1 sí, 0 reabrir."""
    row = repo.marcar_terminado(trabajo_id, terminado=bool(int(terminar)))
    return {"ok": True, "trabajo": row, "terminado": bool(int(terminar))}




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


