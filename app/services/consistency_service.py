"""Motor de consistencia: detecta y repara desfaces entre captura, resumen y catálogo."""
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

    def revisar(self, *, auto_repair: bool = False, limit_semanas: int = 12) -> dict:
        avisos: list[dict] = []
        reparados = 0
        detalles_repair: list[str] = []

        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, codigo FROM semanas
                ORDER BY fecha_inicio DESC LIMIT %s
                """,
                (max(1, int(limit_semanas)),),
            )
            semanas = list(cur.fetchall() or [])
        semana_ids = [int(s["id"]) for s in semanas]
        codigo_by_id = {int(s["id"]): (s.get("codigo") or str(s["id"])) for s in semanas}

        # 1) Resumen vs captura viva (reparable)
        for s in semanas:
            sid = int(s["id"])
            codigo = codigo_by_id[sid]
            vivos = self.resumen.totales_vivos(sid)
            guardado = {"nomina_plt": 0.0, "nomina_pit": 0.0, "nomina_tll": 0.0}
            tiene_fila = False
            try:
                with self.db.cursor() as cur:
                    cur.execute(
                        "SELECT nomina_plt, nomina_pit, nomina_tll FROM resumen_nominas WHERE semana_id=%s",
                        (sid,),
                    )
                    row = cur.fetchone()
                    if row:
                        tiene_fila = True
                        guardado = {
                            "nomina_plt": float(row.get("nomina_plt") or 0),
                            "nomina_pit": float(row.get("nomina_pit") or 0),
                            "nomina_tll": float(row.get("nomina_tll") or 0),
                        }
            except Exception as e:
                logger.warning("consistency resumen read: %s", e)

            desfase = abs(vivos["total_semana"] - sum(guardado.values())) > 0.05
            falta = (not tiene_fila) and vivos["total_semana"] > 0.05

            if falta or desfase:
                if auto_repair:
                    try:
                        self.resumen.recalcular(sid, notas="Auto-reparado por motor de consistencia")
                        reparados += 1
                        detalles_repair.append(f"Resumen {codigo} actualizado → ${vivos['total_semana']:.2f}")
                        continue  # ya no avisar
                    except Exception as e:
                        logger.warning("repair resumen %s: %s", sid, e)
                for key, label in (
                    ("nomina_plt", "Plata"),
                    ("nomina_pit", "Pita"),
                    ("nomina_tll", "Taller"),
                ):
                    a = float(vivos.get(key) or 0)
                    b = float(guardado.get(key) or 0)
                    if abs(a - b) > 0.05 or (falta and a > 0):
                        avisos.append({
                            "nivel": "aviso",
                            "codigo": "resumen_desfasado" if desfase else "resumen_faltante",
                            "titulo": f"Semana {codigo}: {label} desfasado",
                            "detalle": f"Captura ${a:.2f} vs resumen ${b:.2f}. Se corrige con «Recalcular totales».",
                            "semana_id": sid,
                            "reparable": True,
                            "area": label,
                        })

        # 2) Enlazar trabajador_id faltante (reparable)
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT p.id, p.nombre, p.ubic, t.id AS tid
                    FROM produccion_plata p
                    INNER JOIN trabajadores t
                      ON t.nombre_mostrar = p.nombre AND t.ubic = p.ubic
                    WHERE p.trabajador_id IS NULL OR p.trabajador_id = 0
                    LIMIT 500
                    """
                )
                huérfanos = list(cur.fetchall() or [])
            if huérfanos:
                if auto_repair:
                    linked = 0
                    with self.db.cursor() as cur:
                        for row in huérfanos:
                            try:
                                cur.execute(
                                    "UPDATE produccion_plata SET trabajador_id=%s WHERE id=%s AND (trabajador_id IS NULL OR trabajador_id=0)",
                                    (int(row["tid"]), int(row["id"])),
                                )
                                linked += 1
                            except Exception:
                                pass
                    reparados += linked
                    if linked:
                        detalles_repair.append(f"Enlazadas {linked} líneas Plata → trabajador")
                else:
                    avisos.append({
                        "nivel": "info",
                        "codigo": "plt_sin_link",
                        "titulo": f"{len(huérfanos)} línea(s) Plata sin trabajador_id (hay match por nombre+ubic)",
                        "detalle": "Se corrige con «Recalcular totales».",
                        "reparable": True,
                    })
        except Exception as e:
            logger.warning("consistency link: %s", e)

        # 3) Folios repetidos solo en semanas recientes (NO auto-reparable)
        if semana_ids:
            try:
                placeholders = ",".join(["%s"] * len(semana_ids))
                with self.db.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT p.semana_id, p.folio,
                               COUNT(*) AS n_filas,
                               COUNT(DISTINCT COALESCE(
                                   CAST(p.trabajador_id AS CHAR),
                                   CONCAT(COALESCE(p.nombre,''), '#', COALESCE(p.ubic,0))
                               )) AS n_personas
                        FROM produccion_plata p
                        WHERE p.semana_id IN ({placeholders})
                          AND p.folio IS NOT NULL AND TRIM(p.folio) <> ''
                          AND COALESCE(p.total_gramos, 0) > 0
                        GROUP BY p.semana_id, p.folio
                        HAVING n_personas > 1
                        ORDER BY p.semana_id DESC
                        LIMIT 15
                        """,
                        tuple(semana_ids),
                    )
                    for row in cur.fetchall() or []:
                        sid = int(row["semana_id"])
                        codigo = codigo_by_id.get(sid, str(sid))
                        from urllib.parse import quote
                        folio_q = str(row.get("folio") or "").strip()
                        avisos.append({
                            "nivel": "alerta",
                            "codigo": "folio_duplicado",
                            "titulo": f"Folio {row.get('folio')} en {row.get('n_personas')} personas (semana {codigo})",
                            "detalle": "Requiere revisión manual en Plata (no se borra al recalcular).",
                            "semana_id": sid,
                            "reparable": False,
                            "href": f"/produccion?semana_id={sid}&q={quote(folio_q)}&highlight=folio",
                            "accion": "Ver folio",
                        })
            except Exception as e:
                logger.warning("consistency folios: %s", e)

        reparables = sum(1 for a in avisos if a.get("reparable"))
        manuales = len(avisos) - reparables

        return {
            "ok": True,
            "n_avisos": len(avisos),
            "n_reparables": reparables,
            "n_manuales": manuales,
            "avisos": avisos,
            "reparados": reparados,
            "detalles_repair": detalles_repair,
            "auto_repair": auto_repair,
        }
