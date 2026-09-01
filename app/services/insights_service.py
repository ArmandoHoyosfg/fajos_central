"""
Inteligencia operativa ligera (reglas + estadísticas).

1) Panel «Qué revisar hoy» (+ día anterior, cierre de semana)
2) Sugerencia de último trabajo / folio al capturar
3) Rarezas vs semanas anteriores + checklist pre-export
4) Pronóstico de cierre de semana (Plata)
5) Duplicar líneas a la semana siguiente (PLT + PIT + TLL)
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from app.core.calendar_util import encontrar_semana_actual, parse_db_date, today
from app.core.dias import DAY_BY_WEEKDAY, DAY_LABELS, ORDERED_DAYS, col_hoy
from app.core.logging_config import get_logger
from app.core.ops_settings import get_anomaly_pct
from app.db.connection import get_db
from app.db.repository import (
    NominaTallerRepo,
    ProduccionPitaRepo,
    ProduccionRepo,
    SemanasRepo,
    TrabajadoresRepo,
    TrabajosRepo,
)

logger = get_logger(__name__)

ANOMALY_PCT = 0.30
MIN_HIST_WEEKS = 2


def _col_for_date(d: date) -> str:
    return DAY_BY_WEEKDAY.get(d.weekday(), "gm_lun")


def _safe_float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return default


class InsightsService:
    def __init__(self, db=None) -> None:
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.prod = ProduccionRepo(self.db)
        self.pita = ProduccionPitaRepo(self.db)
        self.taller = NominaTallerRepo(self.db)
        self.trab = TrabajadoresRepo(self.db)
        self.trabajos = TrabajosRepo(self.db)

    # ------------------------------------------------------------------ 1) Hoy
    def avisos_hoy(self, ref: date | None = None) -> dict[str, Any]:
        """Lista de avisos accionables para el día."""
        ref = ref or today()
        col = col_hoy(ref)
        label = DAY_LABELS.get(col, col)
        avisos: list[dict] = []
        semanas = self.semanas.listar()
        actual = encontrar_semana_actual(semanas, ref)

        if not actual:
            avisos.append({
                "nivel": "warn",
                "codigo": "sin_semana",
                "titulo": "La semana actual no está creada",
                "detalle": "Crea la semana de nómina para empezar a capturar.",
                "href": "/produccion",
                "accion": "Ir a Plata",
            })
            return {
                "fecha": ref.isoformat(),
                "col_hoy": col,
                "col_hoy_label": label,
                "semana": None,
                "avisos": avisos,
                "pronostico": None,
                "resumen": {"n": len(avisos)},
            }

        sid = int(actual["id"])
        codigo = actual.get("codigo") or str(sid)
        fi = parse_db_date(actual.get("fecha_inicio"))
        ff = parse_db_date(actual.get("fecha_fin"))
        cerrada = bool(actual.get("cerrada"))

        if cerrada:
            avisos.append({
                "nivel": "info",
                "codigo": "semana_cerrada",
                "titulo": f"Semana {codigo} está cerrada",
                "detalle": "Solo consulta/export. No se espera más captura.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Ver semana",
            })
        else:
            # ¿Conviene cerrar la semana?
            if ff and ref > ff:
                avisos.append({
                    "nivel": "warn",
                    "codigo": "cerrar_semana",
                    "titulo": f"Semana {codigo} ya terminó ({ff.isoformat()}) y sigue abierta",
                    "detalle": "Revisa totales, exporta formales y cierra la semana para no mezclar capturas.",
                    "href": f"/produccion?semana_id={sid}",
                    "accion": "Revisar y cerrar",
                })
            elif ff and ref == ff:
                avisos.append({
                    "nivel": "info",
                    "codigo": "ultimo_dia_semana",
                    "titulo": f"Último día de la semana {codigo}",
                    "detalle": "Al terminar la captura conviene exportar y cerrar la semana.",
                    "href": f"/produccion?semana_id={sid}",
                    "accion": "Ir a Plata",
                })
            elif ff and ref == ff + timedelta(days=1):
                avisos.append({
                    "nivel": "warn",
                    "codigo": "cerrar_semana",
                    "titulo": f"Semana {codigo} debería cerrarse",
                    "detalle": "Empezó un nuevo periodo. Cierra la semana anterior antes de capturar de más.",
                    "href": f"/produccion?semana_id={sid}",
                    "accion": "Revisar",
                })

        try:
            lineas = self.prod.listar_por_semana(sid)
        except Exception as e:
            logger.warning("avisos_hoy produccion: %s", e)
            lineas = []

        # Día anterior (solo si cae dentro de la misma semana de nómina)
        ayer = ref - timedelta(days=1)
        col_ayer = _col_for_date(ayer)
        label_ayer = DAY_LABELS.get(col_ayer, col_ayer)
        if fi and ff and fi <= ayer <= ff and not cerrada and lineas:
            con_ayer = 0
            sin_ayer = 0
            for r in lineas:
                g = _safe_float(r.get(col_ayer))
                if g > 0:
                    con_ayer += 1
                else:
                    sin_ayer += 1
            if con_ayer == 0:
                avisos.append({
                    "nivel": "warn",
                    "codigo": "dia_anterior_vacio",
                    "titulo": f"Ayer ({label_ayer}) no tiene gramos en Plata",
                    "detalle": f"Ninguna de las {len(lineas)} línea(s) tiene captura de {label_ayer}.",
                    "href": f"/produccion?semana_id={sid}&dia={col_ayer}&filtro=sin_dia",
                    "accion": "Completar ayer",
                    "count": len(lineas),
                })
            elif sin_ayer > 0 and con_ayer > 0:
                avisos.append({
                    "nivel": "info",
                    "codigo": "dia_anterior_parcial",
                    "titulo": f"Ayer ({label_ayer}): {con_ayer} con gramos, {sin_ayer} sin captura",
                    "detalle": "Revisa si faltó anotar a alguien.",
                    "href": f"/produccion?semana_id={sid}&dia={col_ayer}&filtro=sin_dia",
                    "accion": "Revisar",
                    "count": sin_ayer,
                })

        sin_hoy = []
        sin_firma = []
        for r in lineas:
            g = _safe_float(r.get(col))
            if g <= 0:
                sin_hoy.append(r)
            if not r.get("firmado"):
                sin_firma.append(r)

        if sin_hoy and not cerrada:
            avisos.append({
                "nivel": "warn",
                "codigo": "sin_gramos_hoy",
                "titulo": f"{len(sin_hoy)} línea(s) sin gramos de {label}",
                "detalle": "Captura con «＋ Un día» o edita la celda del día.",
                "href": f"/produccion?semana_id={sid}&filtro=sin_hoy",
                "accion": "Capturar hoy",
                "count": len(sin_hoy),
            })

        if sin_firma:
            avisos.append({
                "nivel": "info",
                "codigo": "sin_firma",
                "titulo": f"{len(sin_firma)} línea(s) Plata sin firmar",
                "detalle": "Marca firma cuando el trabajador cobró / firmó papel.",
                "href": f"/produccion?semana_id={sid}&filtro=sin_firma",
                "accion": "Ver firmas",
                "count": len(sin_firma),
            })

        try:
            activos = self.trab.listar(solo_activos=True)
        except Exception:
            activos = []
        plt = [t for t in activos if (t.get("tipo") or "PLT") == "PLT"]
        en_semana = {
            (str(r.get("nombre") or "").strip().lower(), int(r.get("ubic") or 0))
            for r in lineas
        }
        faltan = [
            t for t in plt
            if (str(t.get("nombre_mostrar") or "").strip().lower(), int(t.get("ubic") or 0))
            not in en_semana
        ]
        if faltan and not cerrada:
            avisos.append({
                "nivel": "info",
                "codigo": "plt_sin_linea",
                "titulo": f"{len(faltan)} trabajador(es) PLT sin línea esta semana",
                "detalle": "Pueden no trabajar esta semana o faltan por agregar.",
                "href": f"/produccion?semana_id={sid}&filtro=todos",
                "accion": "Revisar Plata",
                "count": len(faltan),
            })

        try:
            from app.services.dia_service import DiaService
            if DiaService(self.db).esta_cerrado(ref):
                avisos.append({
                    "nivel": "ok",
                    "codigo": "dia_cerrado",
                    "titulo": f"{label} ya fue cerrado",
                    "detalle": "No se espera más captura de este día.",
                    "href": f"/produccion?semana_id={sid}",
                    "accion": "Ver",
                })
        except Exception:
            pass

        pronostico = None
        try:
            pronostico = self.pronostico_semana(sid, ref=ref)
            if pronostico and pronostico.get("dias_restantes", 0) > 0 and not cerrada:
                avisos.append({
                    "nivel": "info",
                    "codigo": "pronostico",
                    "titulo": (
                        f"Pronóstico cierre Plata ≈ ${pronostico['estimado_efectivo']:.2f} "
                        f"({pronostico['estimado_gramos']:.1f} g)"
                    ),
                    "detalle": (
                        f"Con {pronostico['dias_con_captura']} día(s) de captura; "
                        f"faltan {pronostico['dias_restantes']} día(s) de la semana."
                    ),
                    "href": f"/produccion?semana_id={sid}",
                    "accion": "Ver Plata",
                })
        except Exception as e:
            logger.warning("pronostico en avisos: %s", e)

        if not avisos:
            avisos.append({
                "nivel": "ok",
                "codigo": "todo_bien",
                "titulo": "Todo en orden por ahora",
                "detalle": f"Semana {codigo} · día {label}.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Ir a Plata",
            })


        try:
            from app.services.aprendizaje_service import AprendizajeService
            for fx in AprendizajeService(self.db).detectar_folios_inactivos(sid)[:8]:
                hint = fx.get("hint") or ""
                if hint == "posible_reasignacion":
                    tit = "Folio posiblemente reasignado"
                elif hint == "posible_finalizado":
                    tit = "Folio posiblemente terminado"
                else:
                    tit = "Folio sin avance"
                folio_q = str(fx.get("folio") or "").strip()
                from urllib.parse import quote
                avisos.append({
                    "nivel": "info",
                    "codigo": "folio_inactivo",
                    "titulo": f"{tit}: {fx.get('folio')}",
                    "detalle": f"{fx.get('nombre')} (ubic {fx.get('ubic')})",
                    "href": f"/produccion?semana_id={sid}&q={quote(folio_q)}&highlight=folio",
                    "accion": "Ver folio",
                })
        except Exception:
            pass

        return {
            "fecha": ref.isoformat(),
            "col_hoy": col,
            "col_hoy_label": label,
            "semana": {
                "id": sid,
                "codigo": codigo,
                "cerrada": cerrada,
                "fecha_inicio": fi.isoformat() if fi else None,
                "fecha_fin": ff.isoformat() if ff else None,
            },
            "avisos": avisos,
            "pronostico": pronostico,
            "resumen": {
                "n": len([a for a in avisos if a["codigo"] not in ("todo_bien", "pronostico")]),
                "sin_gramos_hoy": len(sin_hoy),
                "sin_firma": len(sin_firma),
                "plt_sin_linea": len(faltan),
            },
        }

    # ---------------------------------------------------------- 4) Pronóstico
    def pronostico_semana(self, semana_id: int, ref: date | None = None) -> dict[str, Any]:
        """
        Estima gramos y $ al cierre de la semana Plata.
        Usa promedio diario de días que ya tienen alguna captura > 0.
        """
        ref = ref or today()
        sem = self.semanas.obtener(semana_id)
        if not sem:
            return {"ok": False, "error": "semana no encontrada"}

        fi = parse_db_date(sem.get("fecha_inicio"))
        ff = parse_db_date(sem.get("fecha_fin"))
        lineas = self.prod.listar_por_semana(semana_id)

        # Días de la semana de nómina en orden
        dias_semana: list[tuple[date, str]] = []
        if fi and ff:
            d = fi
            while d <= ff:
                dias_semana.append((d, _col_for_date(d)))
                d += timedelta(days=1)
        else:
            dias_semana = [(ref, c) for c in ORDERED_DAYS]

        # Gramos por columna (suma de todas las líneas)
        por_dia: dict[str, float] = {c: 0.0 for c in ORDERED_DAYS}
        efectivo_actual = 0.0
        gramos_actual = 0.0
        for r in lineas:
            gramos_actual += _safe_float(r.get("total_gramos"))
            efectivo_actual += _safe_float(r.get("efectivo"))
            for c in ORDERED_DAYS:
                por_dia[c] += _safe_float(r.get(c))

        dias_con_captura = [c for c in ORDERED_DAYS if por_dia.get(c, 0) > 0]
        n_captura = len(dias_con_captura)
        suma_captura = sum(por_dia[c] for c in dias_con_captura)
        promedio_diario = (suma_captura / n_captura) if n_captura else 0.0

        # Días restantes: columnas de la semana cuya fecha es >= hoy y aún sin captura fuerte
        # Mejor: días del rango fecha que son > ref (futuros) o == ref sin captura completa
        dias_restantes = 0
        if fi and ff:
            d = ref
            while d <= ff:
                # contar días laborables de nómina (todos sáb-vie del rango)
                dias_restantes += 1
                d += timedelta(days=1)
            # el día de hoy ya cuenta en "restantes" solo si aún se puede capturar
            # para estimación: restantes = días desde mañana hasta fin + fracción hoy
            dias_restantes = 0
            d = ref + timedelta(days=1)
            while d <= ff:
                dias_restantes += 1
                d += timedelta(days=1)
        else:
            # fallback: columnas después de hoy en ORDERED_DAYS
            try:
                idx = ORDERED_DAYS.index(col_hoy(ref))
                dias_restantes = max(0, len(ORDERED_DAYS) - idx - 1)
            except ValueError:
                dias_restantes = 0

        estimado_gramos = gramos_actual + promedio_diario * dias_restantes
        # tarifa media ponderada
        tarifa_media = 0.0
        if gramos_actual > 0:
            tarifa_media = efectivo_actual / gramos_actual
        else:
            tarifas = [_safe_float(r.get("tarifa_gr"), 12) for r in lineas]
            tarifa_media = (sum(tarifas) / len(tarifas)) if tarifas else 12.0
        estimado_efectivo = estimado_gramos * tarifa_media

        return {
            "ok": True,
            "semana_id": semana_id,
            "codigo": sem.get("codigo"),
            "gramos_actual": round(gramos_actual, 2),
            "efectivo_actual": round(efectivo_actual, 2),
            "promedio_diario_g": round(promedio_diario, 2),
            "dias_con_captura": n_captura,
            "dias_restantes": dias_restantes,
            "estimado_gramos": round(estimado_gramos, 2),
            "estimado_efectivo": round(estimado_efectivo, 2),
            "tarifa_media": round(tarifa_media, 4),
            "por_dia": {k: round(v, 2) for k, v in por_dia.items()},
        }

    # ---------------------------------------------------------- 2) Autocompletar
    def sugerir_trabajo(
        self,
        trabajador_id: int | None = None,
        nombre: str | None = None,
        ubic: int | None = None,
    ) -> dict[str, Any]:
        tid = trabajador_id
        if not tid and nombre is not None and ubic is not None:
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM trabajadores WHERE nombre_mostrar=%s AND ubic=%s LIMIT 1",
                        (nombre, int(ubic)),
                    )
                    row = cur.fetchone()
                    if row:
                        tid = int(row["id"])
            except Exception as e:
                logger.warning("sugerir_trabajo lookup: %s", e)

        if not tid:
            return {"ok": False, "sugerencia": None}

        try:
            trabajos = self.trabajos.listar(solo_activos=True, trabajador_id=int(tid))
        except Exception:
            trabajos = []
        if trabajos:
            t = trabajos[0]
            return {
                "ok": True,
                "fuente": "trabajo_activo",
                "sugerencia": {
                    "trabajador_id": int(tid),
                    "folio": t.get("folio"),
                    "modelo": t.get("modelo"),
                    "material": t.get("material") or "AG3",
                    "tarifa_gr": float(t.get("tarifa_gr") or 12),
                    "trabajo_id": t.get("id"),
                },
            }

        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT folio, modelo, material, tarifa_gr, trabajo_id
                    FROM produccion_plata
                    WHERE trabajador_id = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (int(tid),),
                )
                row = cur.fetchone()
        except Exception as e:
            logger.warning("sugerir_trabajo prod: %s", e)
            row = None

        if row:
            return {
                "ok": True,
                "fuente": "ultima_produccion",
                "sugerencia": {
                    "trabajador_id": int(tid),
                    "folio": row.get("folio"),
                    "modelo": row.get("modelo"),
                    "material": row.get("material") or "AG3",
                    "tarifa_gr": float(row.get("tarifa_gr") or 12),
                    "trabajo_id": row.get("trabajo_id"),
                },
            }

        return {
            "ok": True,
            "fuente": "default",
            "sugerencia": {
                "trabajador_id": int(tid),
                "folio": None,
                "modelo": None,
                "material": "AG3",
                "tarifa_gr": 12.0,
                "trabajo_id": None,
            },
        }

    # ---------------------------------------------------------- 5) Duplicar 3 áreas
    def _asegurar_semana_destino(self, semana_origen_id: int, destino_id: int | None) -> int:
        from app.services.dia_service import siguiente_rango_semana

        origen = self.semanas.obtener(semana_origen_id)
        if not origen:
            from app.core.exceptions import ValidationAppError
            raise ValidationAppError("Semana origen no encontrada")
        if destino_id:
            return int(destino_id)
        ff = parse_db_date(origen.get("fecha_fin"))
        if not ff:
            from app.core.exceptions import ValidationAppError
            raise ValidationAppError("Semana origen sin fecha_fin")
        codigo, sab, vie = siguiente_rango_semana(ff)
        from app.core.calendar_util import encontrar_semana_por_rango
        existentes = self.semanas.listar()
        dest = encontrar_semana_por_rango(existentes, sab, vie)
        if not dest:
            # fallback por código exacto en el mismo año
            dest = next(
                (
                    s for s in existentes
                    if s.get("codigo") == codigo
                    and int(s.get("anio") or 0) in (0, sab.year, vie.year)
                ),
                None,
            )
        if dest:
            return int(dest["id"])
        return int(self.semanas.crear({
            "codigo": codigo,
            "fecha_inicio": sab.isoformat(),
            "fecha_fin": vie.isoformat(),
            "anio": sab.year,
            "notas": f"Duplicada desde {origen.get('codigo')}",
        }))

    def _conteo_area(self, semana_id: int, area: str) -> int:
        try:
            if area == "plt":
                return len(self.prod.listar_por_semana(semana_id))
            if area == "pit":
                return len(self.pita.listar_por_semana(semana_id))
            if area == "tll":
                return len(self.taller.listar_por_semana(semana_id))
        except Exception:
            return 0
        return 0

    def duplicar_a_siguiente(
        self,
        semana_origen_id: int,
        destino_id: int | None = None,
        areas: list[str] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """
        Copia estructuras de captura a la semana siguiente (sin montos/gramos).
        Si el destino ya tiene líneas en las áreas pedidas y force=False,
        no vuelve a insertar: responde ya_duplicada.
        """
        areas = areas or ["plt", "pit", "tll"]
        dest_id = self._asegurar_semana_destino(semana_origen_id, destino_id)
        dest = self.semanas.obtener(dest_id)
        result: dict[str, Any] = {
            "ok": True,
            "origen_id": semana_origen_id,
            "destino_id": dest_id,
            "destino_codigo": dest.get("codigo") if dest else None,
            "plt": {"created": 0, "skipped": 0},
            "pit": {"created": 0, "skipped": 0},
            "tll": {"created": 0, "skipped": 0},
            "ya_duplicada": False,
            "force": bool(force),
        }

        # ¿El destino ya tiene datos de estas áreas?
        prev = {a: self._conteo_area(dest_id, a) for a in areas}
        result["destino_prev"] = prev
        if not force and any(prev.get(a, 0) > 0 for a in areas):
            # Ejecutar en seco: solo contar skips potenciales no insertar... 
            # Mejor: intentar copia real pero las filas existentes se saltan;
            # si al final created total == 0 → ya_duplicada
            pass

        if "plt" in areas:
            try:
                r = self.prod.duplicar_trabajos_a_semana(semana_origen_id, dest_id)
                result["plt"] = {
                    "created": int(r.get("created") or 0),
                    "skipped": int(r.get("skipped") or 0),
                }
            except Exception as e:
                logger.exception("duplicar plt")
                result["plt"] = {"created": 0, "skipped": 0, "error": str(e)}

        if "pit" in areas:
            result["pit"] = self._duplicar_pita(semana_origen_id, dest_id)

        if "tll" in areas:
            result["tll"] = self._duplicar_taller(semana_origen_id, dest_id)

        result["ok"] = True
        result["total_created"] = (
            result["plt"].get("created", 0)
            + result["pit"].get("created", 0)
            + result["tll"].get("created", 0)
        )
        result["total_skipped"] = (
            result["plt"].get("skipped", 0)
            + result["pit"].get("skipped", 0)
            + result["tll"].get("skipped", 0)
        )
        # Si no se creó nada y el destino ya tenía datos → ya estaba duplicada
        if result["total_created"] == 0 and any(
            (result.get("destino_prev") or {}).get(a, 0) > 0 for a in areas
        ):
            result["ya_duplicada"] = True
            result["mensaje"] = (
                f"La semana {result.get('destino_codigo') or dest_id} ya tenía "
                "las líneas de estas áreas. No se duplicó de nuevo."
            )
        elif result["total_created"] == 0:
            result["mensaje"] = (
                "No había líneas nuevas que copiar (origen vacío o todo ya existía)."
            )
        else:
            result["mensaje"] = (
                f"Se crearon {result['total_created']} línea(s) en "
                f"{result.get('destino_codigo') or dest_id}."
            )
        return result

    def _duplicar_pita(self, origen_id: int, destino_id: int) -> dict:
        created = skipped = 0
        try:
            lineas = self.pita.listar_por_semana(origen_id)
        except Exception as e:
            return {"created": 0, "skipped": 0, "error": str(e)}
        existentes = {
            (
                str(r.get("nombre") or "").lower(),
                int(r.get("ubic") or 0),
                str(r.get("folio") or ""),
                str(r.get("modelo") or ""),
            )
            for r in self.pita.listar_por_semana(destino_id)
        }
        for r in lineas:
            key = (
                str(r.get("nombre") or "").lower(),
                int(r.get("ubic") or 0),
                str(r.get("folio") or ""),
                str(r.get("modelo") or ""),
            )
            if key in existentes:
                skipped += 1
                continue
            try:
                self.pita.insertar(destino_id, {
                    "trabajador_id": r.get("trabajador_id"),
                    "nombre": r.get("nombre"),
                    "ubic": r.get("ubic"),
                    "modelo": r.get("modelo"),
                    "folio": r.get("folio"),
                    "material": r.get("material") or "PITA 6X6",
                    "producto": r.get("producto") or "Cinturón",
                    "pitas": None,
                    "efectivo": 0,
                    "firmado": 0,
                    "notas": r.get("notas"),
                })
                created += 1
                existentes.add(key)
            except Exception as e:
                logger.warning("dup pita: %s", e)
                skipped += 1
        return {"created": created, "skipped": skipped}

    def _duplicar_taller(self, origen_id: int, destino_id: int) -> dict:
        """
        Copia filas de taller.
        fijo → sueldo desde sueldo_base o valor anterior; extras=0
        variable → sueldo 0 (en blanco para capturar)
        """
        created = skipped = 0
        fijos = variables = 0
        try:
            lineas = self.taller.listar_por_semana(origen_id)
        except Exception as e:
            return {"created": 0, "skipped": 0, "error": str(e)}
        existentes = {
            (str(r.get("nombre") or "").lower(), int(r.get("ubic") or 0))
            for r in self.taller.listar_por_semana(destino_id)
        }
        from app.db.repository import TrabajadoresRepo
        tr_repo = TrabajadoresRepo(self.taller.db)
        for r in lineas:
            key = (str(r.get("nombre") or "").lower(), int(r.get("ubic") or 0))
            if key in existentes:
                skipped += 1
                continue
            tid = r.get("trabajador_id")
            modo = str(r.get("sueldo_modo") or "variable").lower()
            base = r.get("sueldo_base")
            if tid:
                try:
                    t = tr_repo.obtener(int(tid))
                    modo = str(t.get("sueldo_modo") or modo).lower()
                    if t.get("sueldo_base") is not None:
                        base = t.get("sueldo_base")
                except Exception:
                    pass
            if modo == "fijo":
                sueldo = _safe_float(base) if base not in (None, "") else _safe_float(r.get("sueldo"))
                fijos += 1
            else:
                sueldo = 0.0
                variables += 1
            try:
                self.taller.insertar(destino_id, {
                    "trabajador_id": tid,
                    "nombre": r.get("nombre"),
                    "ubic": r.get("ubic"),
                    "puesto": r.get("puesto"),
                    "sueldo": sueldo,
                    "extras": 0,
                    "firmado": 0,
                    "notas": r.get("notas"),
                })
                created += 1
                existentes.add(key)
            except Exception as e:
                logger.warning("dup taller: %s", e)
                skipped += 1
        return {
            "created": created,
            "skipped": skipped,
            "fijos_copiados": fijos,
            "variables_en_blanco": variables,
        }

    def tendencias(self, limit_semanas: int = 8) -> dict[str, Any]:
        """
        Serie temporal de totales (Plata/Pita/Taller) + comparación semana actual vs anterior.
        """
        semanas = self.semanas.listar()
        # orden por fecha_inicio asc para sparkline
        def _key(s):
            d = parse_db_date(s.get("fecha_inicio"))
            return d or date.min

        ordered = sorted(semanas, key=_key)
        if len(ordered) > limit_semanas:
            ordered = ordered[-limit_semanas:]

        serie = []
        for s in ordered:
            sid = int(s["id"])
            try:
                t_plt = self.prod.totales_semana(sid)
                t_pit = self.pita.totales(sid)
                t_tll = self.taller.totales(sid)
            except Exception as e:
                logger.warning("tendencias semana %s: %s", sid, e)
                t_plt, t_pit, t_tll = {}, {}, {}
            plt_e = _safe_float(t_plt.get("total_efectivo"))
            pit_e = _safe_float(t_pit.get("total"))
            tll_e = _safe_float(t_tll.get("total"))
            serie.append({
                "id": sid,
                "codigo": s.get("codigo"),
                "fecha_inicio": str(s.get("fecha_inicio") or ""),
                "plt": round(plt_e, 2),
                "pit": round(pit_e, 2),
                "tll": round(tll_e, 2),
                "total": round(plt_e + pit_e + tll_e, 2),
                "gramos": round(_safe_float(t_plt.get("total_gramos")), 2),
            })

        actual = encontrar_semana_actual(semanas, today())
        actual_id = int(actual["id"]) if actual else None
        idx = next((i for i, x in enumerate(serie) if x["id"] == actual_id), None)
        prev = serie[idx - 1] if idx is not None and idx > 0 else None
        cur = serie[idx] if idx is not None else (serie[-1] if serie else None)

        def delta(a, b):
            if b is None or b == 0:
                return None
            return round(((a - b) / b) * 100, 1)

        comparacion = None
        if cur and prev:
            comparacion = {
                "actual_codigo": cur["codigo"],
                "prev_codigo": prev["codigo"],
                "plt_pct": delta(cur["plt"], prev["plt"]),
                "pit_pct": delta(cur["pit"], prev["pit"]),
                "tll_pct": delta(cur["tll"], prev["tll"]),
                "total_pct": delta(cur["total"], prev["total"]),
                "gramos_pct": delta(cur["gramos"], prev["gramos"]),
                "actual": cur,
                "prev": prev,
            }

        # top materiales semana actual
        top_materiales = []
        if actual_id:
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(material,'—') AS material,
                               SUM(total_gramos) AS gramos,
                               SUM(efectivo) AS efectivo
                        FROM produccion_plata
                        WHERE semana_id = %s
                        GROUP BY COALESCE(material,'—')
                        ORDER BY SUM(efectivo) DESC
                        LIMIT 6
                        """,
                        (actual_id,),
                    )
                    top_materiales = [
                        {
                            "material": r["material"],
                            "gramos": round(_safe_float(r.get("gramos")), 2),
                            "efectivo": round(_safe_float(r.get("efectivo")), 2),
                        }
                        for r in (cur.fetchall() or [])
                    ]
            except Exception as e:
                logger.warning("top materiales: %s", e)

        return {
            "serie": serie,
            "comparacion": comparacion,
            "top_materiales": top_materiales,
        }

    def captura_solo_hoy(self, ref: date | None = None) -> dict[str, Any]:
        """Vista reducida: trabajos/líneas de la semana actual + gramos del día."""
        ref = ref or today()
        col = col_hoy(ref)
        label = DAY_LABELS.get(col, col)
        semanas = self.semanas.listar()
        actual = encontrar_semana_actual(semanas, ref)
        if not actual:
            return {
                "ok": False,
                "fecha": ref.isoformat(),
                "col_hoy": col,
                "label": label,
                "semana": None,
                "lineas": [],
                "capturados": 0,
                "pendientes": 0,
            }
        sid = int(actual["id"])
        lineas = self.prod.listar_por_semana(sid)
        rows = []
        capturados = pendientes = 0
        for r in lineas:
            g = _safe_float(r.get(col))
            if g > 0:
                capturados += 1
            else:
                pendientes += 1
            rows.append({
                "id": r.get("id"),
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "folio": r.get("folio"),
                "modelo": r.get("modelo"),
                "material": r.get("material"),
                "tarifa_gr": _safe_float(r.get("tarifa_gr"), 12),
                "gramos_hoy": g if g > 0 else None,
                "total_gramos": _safe_float(r.get("total_gramos")),
            })
        # orden: pendientes primero, luego nombre
        rows.sort(key=lambda x: (0 if not x.get("gramos_hoy") else 1, str(x.get("nombre") or "")))
        return {
            "ok": True,
            "fecha": ref.isoformat(),
            "col_hoy": col,
            "label": label,
            "semana": {
                "id": sid,
                "codigo": actual.get("codigo"),
                "cerrada": bool(actual.get("cerrada")),
            },
            "lineas": rows,
            "capturados": capturados,
            "pendientes": pendientes,
            "total": len(rows),
        }


    def rarezas_semana(self, semana_id: int, pct: float | None = None) -> dict[str, Any]:
        if pct is None:
            pct = get_anomaly_pct()
        alertas: list[dict] = []
        try:
            lineas = self.prod.listar_por_semana(semana_id)
        except Exception as e:
            logger.warning("rarezas: %s", e)
            return {"semana_id": semana_id, "alertas": [], "error": str(e)}

        hist: dict[int, dict] = {}
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT trabajador_id,
                           COUNT(*) AS n_sem,
                           AVG(total_gramos) AS avg_gr,
                           AVG(efectivo) AS avg_ef
                    FROM produccion_plata
                    WHERE semana_id <> %s
                      AND trabajador_id IS NOT NULL
                      AND total_gramos > 0
                    GROUP BY trabajador_id
                    HAVING COUNT(*) >= %s
                    """,
                    (semana_id, MIN_HIST_WEEKS),
                )
                for row in cur.fetchall() or []:
                    hist[int(row["trabajador_id"])] = row
        except Exception as e:
            logger.warning("rarezas hist: %s", e)

        for r in lineas:
            tid = r.get("trabajador_id")
            if not tid or int(tid) not in hist:
                continue
            h = hist[int(tid)]
            gr = _safe_float(r.get("total_gramos"))
            ef = _safe_float(r.get("efectivo"))
            avg_gr = _safe_float(h.get("avg_gr"))
            avg_ef = _safe_float(h.get("avg_ef"))
            if avg_ef > 0 and ef > 0:
                ratio = ef / avg_ef
                if ratio >= 1 + pct or ratio <= 1 - pct:
                    alertas.append({
                        "tipo": "efectivo",
                        "nivel": "warn" if ratio >= 1 + pct else "info",
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "valor": ef,
                        "promedio": round(avg_ef, 2),
                        "ratio": round(ratio, 2),
                        "msg": (
                            f"{r.get('nombre')} (ubic {r.get('ubic')}): "
                            f"${ef:.2f} vs promedio ${avg_ef:.2f} "
                            f"({'+' if ratio >= 1 else ''}{int((ratio-1)*100)}%)"
                        ),
                    })
            elif avg_gr > 0 and gr > 0:
                ratio = gr / avg_gr
                if ratio >= 1 + pct or ratio <= 1 - pct:
                    alertas.append({
                        "tipo": "gramos",
                        "nivel": "warn" if ratio >= 1 + pct else "info",
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "msg": (
                            f"{r.get('nombre')} (ubic {r.get('ubic')}): "
                            f"{gr:.1f} g vs promedio {avg_gr:.1f} g"
                        ),
                    })

        try:
            for r in self.pita.listar_por_semana(semana_id):
                ef = _safe_float(r.get("efectivo"))
                if ef <= 0 and (r.get("folio") or r.get("modelo")):
                    alertas.append({
                        "tipo": "pita_cero",
                        "nivel": "info",
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "msg": f"Pita: {r.get('nombre')} tiene folio/modelo pero efectivo $0",
                    })
        except Exception:
            pass

        return {
            "semana_id": semana_id,
            "umbral_pct": int(pct * 100),
            "alertas": alertas,
            "n": len(alertas),
        }

    def checklist_export(self, semana_id: int) -> dict[str, Any]:
        items: list[dict] = []
        try:
            lineas = self.prod.listar_por_semana(semana_id)
        except Exception as e:
            return {"semana_id": semana_id, "items": [], "ok": False, "error": str(e)}

        con_gramos = [r for r in lineas if _safe_float(r.get("total_gramos")) > 0]
        sin_gramos = len(lineas) - len(con_gramos)
        sin_firma = sum(1 for r in con_gramos if not r.get("firmado"))

        items.append({
            "id": "lineas_con_gramos",
            "ok": len(con_gramos) > 0,
            "texto": f"{len(con_gramos)} línea(s) con gramos (salen en formal)",
        })
        items.append({
            "id": "omitidas",
            "ok": True,
            "texto": f"{sin_gramos} sin gramos se omiten al exportar",
        })
        items.append({
            "id": "firmas",
            "ok": sin_firma == 0,
            "texto": (
                "Todas las líneas con gramos están firmadas"
                if sin_firma == 0
                else f"{sin_firma} con gramos aún sin firmar"
            ),
        })

        rarezas = self.rarezas_semana(semana_id)
        n_r = rarezas.get("n") or 0
        items.append({
            "id": "rarezas",
            "ok": n_r == 0,
            "texto": (
                "Sin rarezas vs historial"
                if n_r == 0
                else f"{n_r} posible(s) rareza(s) a revisar"
            ),
            "detalle": [a.get("msg") for a in (rarezas.get("alertas") or [])][:8],
        })

        try:
            t_plt = self.prod.totales_semana(semana_id)
            t_pit = self.pita.totales(semana_id)
            t_tll = self.taller.totales(semana_id)
            items.append({
                "id": "totales",
                "ok": True,
                "texto": (
                    f"Plata ${float(t_plt.get('total_efectivo') or 0):.2f} · "
                    f"Pita ${float(t_pit.get('total') or 0):.2f} · "
                    f"Taller ${float(t_tll.get('total') or 0):.2f}"
                ),
            })
        except Exception:
            pass

        try:
            pr = self.pronostico_semana(semana_id)
            if pr.get("ok"):
                items.append({
                    "id": "pronostico",
                    "ok": True,
                    "texto": (
                        f"Pronóstico cierre ≈ ${pr['estimado_efectivo']:.2f} "
                        f"({pr['estimado_gramos']:.1f} g)"
                    ),
                })
        except Exception:
            pass

        return {
            "semana_id": semana_id,
            "items": items,
            "ok": len(con_gramos) > 0,
            "puede_exportar": len(con_gramos) > 0,
        }
