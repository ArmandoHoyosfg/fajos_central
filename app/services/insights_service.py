"""
Inteligencia operativa ligera (reglas + estadísticas).

1) Panel «Qué revisar hoy»
2) Sugerencia de último trabajo / folio al capturar
3) Rarezas vs semanas anteriores + checklist pre-export
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.core.calendar_util import encontrar_semana_actual, today
from app.core.dias import DAY_LABELS, col_hoy
from app.core.logging_config import get_logger
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

# Umbral de rareza: ±30 % vs promedio histórico del trabajador
ANOMALY_PCT = 0.30
# Mínimo de semanas previas para comparar
MIN_HIST_WEEKS = 2


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
                "resumen": {"n": len(avisos)},
            }

        sid = int(actual["id"])
        codigo = actual.get("codigo") or str(sid)

        if actual.get("cerrada"):
            avisos.append({
                "nivel": "info",
                "codigo": "semana_cerrada",
                "titulo": f"Semana {codigo} está cerrada",
                "detalle": "Solo consulta/export. No se espera más captura.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Ver semana",
            })

        # Sin gramos de hoy (líneas existentes)
        try:
            lineas = self.prod.listar_por_semana(sid)
        except Exception as e:
            logger.warning("avisos_hoy produccion: %s", e)
            lineas = []

        sin_hoy = []
        sin_firma = []
        for r in lineas:
            try:
                g = float(r.get(col) or 0)
            except (TypeError, ValueError):
                g = 0.0
            if g <= 0:
                sin_hoy.append(r)
            if not r.get("firmado"):
                sin_firma.append(r)

        if sin_hoy and not actual.get("cerrada"):
            avisos.append({
                "nivel": "warn",
                "codigo": "sin_gramos_hoy",
                "titulo": f"{len(sin_hoy)} línea(s) sin gramos de {label}",
                "detalle": "Captura con «＋ Un día» o edita la celda del día.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Capturar hoy",
                "count": len(sin_hoy),
            })

        if sin_firma:
            avisos.append({
                "nivel": "info",
                "codigo": "sin_firma",
                "titulo": f"{len(sin_firma)} línea(s) Plata sin firmar",
                "detalle": "Marca firma cuando el trabajador cobró / firmó papel.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Ver firmas",
                "count": len(sin_firma),
            })

        # Activos PLT sin línea esta semana
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
        if faltan and not actual.get("cerrada"):
            avisos.append({
                "nivel": "info",
                "codigo": "plt_sin_linea",
                "titulo": f"{len(faltan)} trabajador(es) PLT sin línea esta semana",
                "detalle": "Pueden no trabajar esta semana o faltan por agregar.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Revisar Plata",
                "count": len(faltan),
            })

        # Cierre de día
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

        if not avisos:
            avisos.append({
                "nivel": "ok",
                "codigo": "todo_bien",
                "titulo": "Todo en orden por ahora",
                "detalle": f"Semana {codigo} · día {label}.",
                "href": f"/produccion?semana_id={sid}",
                "accion": "Ir a Plata",
            })

        return {
            "fecha": ref.isoformat(),
            "col_hoy": col,
            "col_hoy_label": label,
            "semana": {"id": sid, "codigo": codigo, "cerrada": bool(actual.get("cerrada"))},
            "avisos": avisos,
            "resumen": {
                "n": len([a for a in avisos if a["codigo"] != "todo_bien"]),
                "sin_gramos_hoy": len(sin_hoy),
                "sin_firma": len(sin_firma),
                "plt_sin_linea": len(faltan),
            },
        }

    # ---------------------------------------------------------- 2) Autocompletar
    def sugerir_trabajo(self, trabajador_id: int | None = None,
                        nombre: str | None = None,
                        ubic: int | None = None) -> dict[str, Any]:
        """
        Último trabajo activo o última línea de producción del trabajador.
        """
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

        # 1) trabajo activo
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

        # 2) última línea de producción
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

    # ---------------------------------------------------------- 3) Rarezas + checklist
    def rarezas_semana(self, semana_id: int, pct: float = ANOMALY_PCT) -> dict[str, Any]:
        """Compara efectivo/gramos vs promedio de semanas previas del mismo trabajador."""
        alertas: list[dict] = []
        try:
            lineas = self.prod.listar_por_semana(semana_id)
        except Exception as e:
            logger.warning("rarezas: %s", e)
            return {"semana_id": semana_id, "alertas": [], "error": str(e)}

        # promedios por trabajador_id
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
            try:
                gr = float(r.get("total_gramos") or 0)
                ef = float(r.get("efectivo") or 0)
                avg_gr = float(h.get("avg_gr") or 0)
                avg_ef = float(h.get("avg_ef") or 0)
            except (TypeError, ValueError):
                continue
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
                        "valor": gr,
                        "promedio": round(avg_gr, 2),
                        "ratio": round(ratio, 2),
                        "msg": (
                            f"{r.get('nombre')} (ubic {r.get('ubic')}): "
                            f"{gr:.1f} g vs promedio {avg_gr:.1f} g"
                        ),
                    })

        # Pita outliers simples
        try:
            for r in self.pita.listar_por_semana(semana_id):
                try:
                    ef = float(r.get("efectivo") or 0)
                except (TypeError, ValueError):
                    ef = 0
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
        """Checklist antes de imprimir/exportar formal."""
        items: list[dict] = []
        try:
            lineas = self.prod.listar_por_semana(semana_id)
        except Exception as e:
            return {"semana_id": semana_id, "items": [], "ok": False, "error": str(e)}

        con_gramos = [
            r for r in lineas
            if float(r.get("total_gramos") or 0) > 0
        ]
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
            "detalle": [a.get("msg") for a in rarezas.get("alertas") or []][:8],
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

        ok = all(i.get("ok") for i in items if i["id"] in ("lineas_con_gramos",))
        return {
            "semana_id": semana_id,
            "items": items,
            "ok": ok,
            "puede_exportar": len(con_gramos) > 0,
        }
