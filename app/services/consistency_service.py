"""Motor de consistencia: detecta desfaces entre captura, resumen y catálogo."""
from __future__ import annotations

from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repository import ResumenRepo, SemanasRepo

logger = get_logger(__name__)


class ConsistencyService:
    """Revisa periódicamente (o bajo demanda) inconsistencias de datos."""

    def __init__(self) -> None:
        self.db = get_db()
        self.resumen = ResumenRepo()
        self.semanas = SemanasRepo()

    def revisar(self, *, auto_repair: bool = False, limit_semanas: int = 16) -> dict:
        avisos: list[dict] = []
        reparados = 0

        # 1) Resumen vs captura viva
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, codigo FROM semanas
                ORDER BY fecha_inicio DESC LIMIT %s
                """,
                (limit_semanas,),
            )
            semanas = list(cur.fetchall() or [])

        for s in semanas:
            sid = int(s["id"])
            codigo = s.get("codigo") or str(sid)
            vivos = self.resumen.totales_vivos(sid)
            guardado = {"nomina_plt": 0.0, "nomina_pit": 0.0, "nomina_tll": 0.0}
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "SELECT nomina_plt, nomina_pit, nomina_tll FROM resumen_nominas WHERE semana_id=%s",
                        (sid,),
                    )
                    row = cur.fetchone()
                    if row:
                        guardado = {
                            "nomina_plt": float(row.get("nomina_plt") or 0),
                            "nomina_pit": float(row.get("nomina_pit") or 0),
                            "nomina_tll": float(row.get("nomina_tll") or 0),
                        }
                    elif vivos["total_semana"] > 0:
                        avisos.append({
                            "nivel": "aviso",
                            "codigo": "resumen_faltante",
                            "titulo": f"Semana {codigo}: sin fila en resumen_nominas",
                            "detalle": f"Captura tiene ${vivos['total_semana']:.2f} pero no hay resumen guardado.",
                            "semana_id": sid,
                        })
            except Exception as e:
                logger.warning("consistency resumen: %s", e)

            for key, label in (
                ("nomina_plt", "Plata"),
                ("nomina_pit", "Pita"),
                ("nomina_tll", "Taller"),
            ):
                a = float(vivos.get(key) or 0)
                b = float(guardado.get(key) or 0)
                if abs(a - b) > 0.05:
                    avisos.append({
                        "nivel": "aviso",
                        "codigo": "resumen_desfasado",
                        "titulo": f"Semana {codigo}: {label} desfasado",
                        "detalle": f"Captura ${a:.2f} vs resumen ${b:.2f}",
                        "semana_id": sid,
                        "area": label,
                    })
            if auto_repair and (
                abs(vivos["total_semana"] - sum(guardado.values())) > 0.05
                or (vivos["total_semana"] > 0 and sum(guardado.values()) == 0)
            ):
                try:
                    self.resumen.recalcular(sid, notas="Auto-reparado por motor de consistencia")
                    reparados += 1
                except Exception as e:
                    logger.warning("repair resumen %s: %s", sid, e)

        # 2) Líneas de producción sin trabajador_id enlazable
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS n FROM produccion_plata p
                    WHERE p.trabajador_id IS NULL
                      AND EXISTS (
                        SELECT 1 FROM trabajadores t
                        WHERE t.nombre_mostrar = p.nombre AND t.ubic = p.ubic
                      )
                    """
                )
                n = int((cur.fetchone() or {}).get("n") or 0)
                if n:
                    avisos.append({
                        "nivel": "info",
                        "codigo": "plt_sin_link",
                        "titulo": f"{n} línea(s) Plata sin trabajador_id (sí hay match por nombre+ubic)",
                        "detalle": "Usa Sincronizar nóminas en Trabajadores o el botón de reparación en Dev.",
                    })
        except Exception:
            pass

        # 3) Folios repetidos activos en misma semana
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.semana_id, p.folio, COUNT(DISTINCT p.trabajador_id) AS n
                    FROM produccion_plata p
                    WHERE p.folio IS NOT NULL AND TRIM(p.folio) <> ''
                    GROUP BY p.semana_id, p.folio
                    HAVING n > 1
                    LIMIT 20
                    """
                )
                for row in cur.fetchall() or []:
                    avisos.append({
                        "nivel": "alerta",
                        "codigo": "folio_duplicado",
                        "titulo": f"Folio {row.get('folio')} en {row.get('n')} trabajadores (semana {row.get('semana_id')})",
                        "detalle": "Revisa en Plata o Dev → folios repetidos.",
                        "semana_id": int(row["semana_id"]) if row.get("semana_id") else None,
                    })
        except Exception:
            pass

        # 4) Semana cerrada con captura en 0 y resumen > 0 (raro) o viceversa ya cubierto

        return {
            "ok": True,
            "n_avisos": len(avisos),
            "avisos": avisos,
            "reparados": reparados,
            "auto_repair": auto_repair,
        }
