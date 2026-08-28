"""
Aprendizaje ligero: registra uso, detecta folios inactivos/reasignados
y acumula estadísticas simples (sin ML pesado).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.core.calendar_util import encontrar_semana_actual, parse_db_date, today
from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repository import ProduccionRepo, SemanasRepo, TrabajadoresRepo, TrabajosRepo

logger = get_logger(__name__)


class AprendizajeService:
    def __init__(self, db=None) -> None:
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.prod = ProduccionRepo(self.db)
        self.trab = TrabajadoresRepo(self.db)
        self.trabajos = TrabajosRepo(self.db)

    def registrar(
        self,
        tipo: str,
        *,
        entidad: str | None = None,
        entidad_id: int | None = None,
        semana_id: int | None = None,
        payload: dict | None = None,
        peso: float = 1.0,
    ) -> None:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO aprendizaje_eventos
                      (tipo, entidad, entidad_id, semana_id, payload_json, peso)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tipo[:40],
                        entidad,
                        entidad_id,
                        semana_id,
                        json.dumps(payload, default=str) if payload else None,
                        peso,
                    ),
                )
        except Exception:
            # Tabla puede no existir aún (migración 004)
            logger.debug("No se pudo registrar aprendizaje (%s)", tipo, exc_info=True)

    def bump_stat(self, clave: str, valor_num: float | None = None, valor_txt: str | None = None) -> None:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO aprendizaje_stats (clave, valor_num, valor_txt, muestras)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                      valor_num = CASE
                        WHEN VALUES(valor_num) IS NULL THEN valor_num
                        WHEN valor_num IS NULL THEN VALUES(valor_num)
                        ELSE (valor_num * muestras + VALUES(valor_num)) / (muestras + 1)
                      END,
                      valor_txt = COALESCE(VALUES(valor_txt), valor_txt),
                      muestras = muestras + 1
                    """,
                    (clave[:80], valor_num, valor_txt),
                )
        except Exception:
            logger.debug("No se pudo bump_stat %s", clave, exc_info=True)

    def _gramos_linea(self, row: dict) -> float:
        try:
            return float(row.get("total_gramos") or 0)
        except (TypeError, ValueError):
            return 0.0


    def detectar_folios_inactivos(self, semana_id: int | None = None) -> list[dict]:
        """
        Folios con 0 g esta semana.
        Si la semana previa tuvo gramos → posible_finalizado o posible_reasignacion.
        """
        semanas = self.semanas.listar()
        actual = None
        if semana_id:
            for s in semanas:
                if int(s["id"]) == int(semana_id):
                    actual = s
                    break
        if not actual:
            actual = encontrar_semana_actual(semanas, today())
        if not actual:
            return []

        sid = int(actual["id"])
        lineas = self.prod.listar_por_semana(sid)
        prev = None
        fi = parse_db_date(actual.get("fecha_inicio"))
        if fi:
            prev = encontrar_semana_actual(semanas, fi - timedelta(days=1))

        prev_by_folio: dict[str, list[dict]] = {}
        if prev:
            for r in self.prod.listar_por_semana(int(prev["id"])):
                folio = (r.get("folio") or "").strip()
                if not folio:
                    continue
                g = self._gramos_linea(r)
                if g <= 0:
                    continue
                prev_by_folio.setdefault(folio.upper(), []).append({
                    "nombre": r.get("nombre"),
                    "ubic": r.get("ubic"),
                    "trabajador_id": r.get("trabajador_id"),
                    "gramos": g,
                    "semana": prev.get("codigo"),
                    "prod_id": r.get("id"),
                })

        out: list[dict] = []
        for r in lineas:
            folio = (r.get("folio") or "").strip()
            if not folio:
                continue
            if self._gramos_linea(r) > 0:
                continue
            key = folio.upper()
            prev_list = prev_by_folio.get(key) or []
            hint = "sin_avance_esta_semana"
            prev_info = prev_list[0] if prev_list else None
            if prev_info:
                tid_now = r.get("trabajador_id")
                tid_prev = prev_info.get("trabajador_id")
                same_person = False
                if tid_now and tid_prev:
                    same_person = int(tid_now) == int(tid_prev)
                else:
                    same_person = (
                        str(prev_info.get("nombre") or "").lower()
                        == str(r.get("nombre") or "").lower()
                    )
                hint = "posible_finalizado" if same_person else "posible_reasignacion"
            out.append({
                "prod_id": r.get("id"),
                "folio": folio,
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "trabajador_id": r.get("trabajador_id"),
                "hint": hint,
                "prev": prev_info,
                "semana_id": sid,
                "accion_sugerida": (
                    "marcar_terminado" if hint == "posible_finalizado"
                    else "revisar_reasignacion" if hint == "posible_reasignacion"
                    else "revisar"
                ),
            })
        return out

    def detectar_reasignaciones(self, semana_id: int | None = None) -> list[dict]:
        """
        Folio con avance esta semana en trabajador B, y la semana previa
        el mismo folio tenía avance en trabajador A (A != B).
        """
        semanas = self.semanas.listar()
        actual = None
        if semana_id:
            for s in semanas:
                if int(s["id"]) == int(semana_id):
                    actual = s
                    break
        if not actual:
            actual = encontrar_semana_actual(semanas, today())
        if not actual:
            return []
        sid = int(actual["id"])
        fi = parse_db_date(actual.get("fecha_inicio"))
        prev = encontrar_semana_actual(semanas, fi - timedelta(days=1)) if fi else None
        if not prev:
            return []

        prev_owners: dict[str, list[dict]] = {}
        for r in self.prod.listar_por_semana(int(prev["id"])):
            folio = (r.get("folio") or "").strip()
            if not folio or self._gramos_linea(r) <= 0:
                continue
            prev_owners.setdefault(folio.upper(), []).append({
                "trabajador_id": r.get("trabajador_id"),
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "gramos": self._gramos_linea(r),
                "semana": prev.get("codigo"),
            })

        out = []
        for r in self.prod.listar_por_semana(sid):
            folio = (r.get("folio") or "").strip()
            if not folio or self._gramos_linea(r) <= 0:
                continue
            key = folio.upper()
            prevs = prev_owners.get(key) or []
            tid = r.get("trabajador_id")
            for p in prevs:
                ptid = p.get("trabajador_id")
                if tid and ptid and int(tid) != int(ptid):
                    out.append({
                        "folio": folio,
                        "de": p,
                        "a": {
                            "trabajador_id": tid,
                            "nombre": r.get("nombre"),
                            "ubic": r.get("ubic"),
                            "gramos": self._gramos_linea(r),
                            "prod_id": r.get("id"),
                            "semana": actual.get("codigo"),
                        },
                        "semana_id": sid,
                        "mensaje": (
                            f"El folio {folio} pasó de {p.get('nombre')} (ubic {p.get('ubic')}) "
                            f"a {r.get('nombre')} (ubic {r.get('ubic')})"
                        ),
                    })
                elif not tid or not ptid:
                    # fallback por nombre
                    if str(p.get("nombre") or "").lower() != str(r.get("nombre") or "").lower():
                        out.append({
                            "folio": folio,
                            "de": p,
                            "a": {
                                "trabajador_id": tid,
                                "nombre": r.get("nombre"),
                                "ubic": r.get("ubic"),
                                "gramos": self._gramos_linea(r),
                                "prod_id": r.get("id"),
                                "semana": actual.get("codigo"),
                            },
                            "semana_id": sid,
                            "mensaje": (
                                f"El folio {folio} cambió de persona: "
                                f"{p.get('nombre')} → {r.get('nombre')}"
                            ),
                        })
        return out

    def marcar_folio_terminado(self, prod_id: int | None = None, trabajo_id: int | None = None) -> dict:
        """Marca el trabajo como terminado. Si la línea no tiene trabajo_id, lo busca por folio."""
        folio = None
        with self.db.cursor() as cur:
            tid = trabajo_id
            trab_id = None
            if not tid and prod_id:
                cur.execute(
                    "SELECT trabajo_id, folio, trabajador_id FROM produccion_plata WHERE id=%s",
                    (prod_id,),
                )
                row = cur.fetchone() or {}
                tid = row.get("trabajo_id")
                folio = row.get("folio")
                trab_id = row.get("trabajador_id")
                if not tid and folio and trab_id:
                    try:
                        cur.execute(
                            """
                            SELECT id FROM trabajos
                             WHERE trabajador_id=%s AND folio=%s
                             ORDER BY id DESC LIMIT 1
                            """,
                            (trab_id, folio),
                        )
                        tw = cur.fetchone()
                        if tw:
                            tid = tw["id"]
                            cur.execute(
                                "UPDATE produccion_plata SET trabajo_id=%s WHERE id=%s",
                                (tid, prod_id),
                            )
                    except Exception:
                        tid = None
            if not tid:
                return {
                    "ok": False,
                    "error": (
                        "Esta línea no tiene un trabajo ligado. "
                        "Edita el folio en Plata o márcalo desde Folios."
                    ),
                }
            try:
                cur.execute(
                    "UPDATE trabajos SET terminado_en = COALESCE(terminado_en, NOW()), activo = 0 WHERE id = %s",
                    (tid,),
                )
            except Exception:
                try:
                    cur.execute(
                        "UPDATE trabajos SET terminado_en = COALESCE(terminado_en, NOW()) WHERE id = %s",
                        (tid,),
                    )
                except Exception as e2:
                    return {"ok": False, "error": str(e2)}
            if prod_id:
                try:
                    cur.execute(
                        """
                        UPDATE produccion_plata
                           SET notas = TRIM(CONCAT(COALESCE(notas,''), ' [terminado]'))
                         WHERE id = %s AND (notas IS NULL OR notas NOT LIKE %s)
                        """,
                        (prod_id, "%[terminado]%"),
                    )
                except Exception:
                    pass
            try:
                self.db.connect().commit()
            except Exception:
                pass
        self.registrar(
            "folio_terminado",
            entidad="trabajo",
            entidad_id=int(tid),
            payload={"prod_id": prod_id, "folio": folio},
        )
        return {"ok": True, "trabajo_id": tid, "folio": folio, "prod_id": prod_id}



    def reactivar_folio(self, prod_id: int | None = None, trabajo_id: int | None = None) -> dict:
        """Reabre un folio terminado (activo=1, limpia marca en notas)."""
        with self.db.cursor() as cur:
            tid = trabajo_id
            folio = None
            if prod_id:
                cur.execute(
                    "SELECT trabajo_id, folio, notas FROM produccion_plata WHERE id=%s",
                    (prod_id,),
                )
                row = cur.fetchone() or {}
                if not tid:
                    tid = row.get("trabajo_id")
                folio = row.get("folio")
                notas = str(row.get("notas") or "").replace("[terminado]", "").strip()
                cur.execute(
                    "UPDATE produccion_plata SET notas = %s WHERE id = %s",
                    (notas or None, prod_id),
                )
            if not tid:
                return {"ok": False, "error": "No se encontró el trabajo para reactivar."}
            try:
                cur.execute(
                    "UPDATE trabajos SET activo = 1, terminado_en = NULL WHERE id = %s",
                    (tid,),
                )
            except Exception:
                cur.execute("UPDATE trabajos SET activo = 1 WHERE id = %s", (tid,))
            try:
                self.db.connect().commit()
            except Exception:
                pass
        self.registrar(
            "folio_reactivado",
            entidad="trabajo",
            entidad_id=int(tid),
            payload={"prod_id": prod_id, "folio": folio},
        )
        return {"ok": True, "trabajo_id": tid, "folio": folio, "prod_id": prod_id}

    def purgar_terminados(self, dias: int = 7) -> dict:
        """Elimina trabajos terminados tras N días. Historial de nómina se conserva."""
        dias = max(1, min(int(dias or 7), 90))
        deleted = 0
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    DELETE FROM trabajos
                     WHERE activo = 0
                       AND terminado_en IS NOT NULL
                       AND terminado_en < (NOW() - INTERVAL %s DAY)
                    """,
                    (dias,),
                )
                deleted = max(0, cur.rowcount or 0)
            except Exception as e:
                logger.warning("purgar_terminados: %s", e)
                return {"ok": False, "error": str(e), "eliminados": 0, "dias": dias}
            try:
                self.db.connect().commit()
            except Exception:
                pass
        if deleted:
            self.registrar(
                "purga_terminados",
                entidad="app",
                payload={"eliminados": deleted, "dias": dias},
            )
        return {"ok": True, "eliminados": deleted, "dias": dias}

    def candidatos_duplicados_trabajadores(self) -> list[dict]:
        """
        Posibles duplicados:
        - mismo nombre_mostrar con distinta ubic
        - nombre_completo casi igual
        """
        rows = self.trab.listar(solo_activos=False)
        by_name: dict[str, list] = {}
        for r in rows:
            k = (r.get("nombre_mostrar") or "").strip().lower()
            if not k:
                continue
            by_name.setdefault(k, []).append(r)
        cands = []
        for name, group in by_name.items():
            if len(group) < 2:
                continue
            activos = [g for g in group if g.get("activo")]
            if len(group) >= 2:
                cands.append({
                    "nombre": name,
                    "n": len(group),
                    "ids": [int(g["id"]) for g in group],
                    "detalle": [
                        {
                            "id": int(g["id"]),
                            "nombre_mostrar": g.get("nombre_mostrar"),
                            "ubic": g.get("ubic"),
                            "tipo": g.get("tipo"),
                            "activo": bool(g.get("activo")),
                        }
                        for g in group
                    ],
                })
        return cands

    def fusionar_trabajadores(self, id_keep: int, id_merge: int) -> dict:
        """
        Reasigna producción/pita/taller/trabajos de id_merge → id_keep
        y desactiva id_merge. Actualiza nombre/ubic denormalizados del survivor.
        """
        if int(id_keep) == int(id_merge):
            return {"ok": False, "error": "ids iguales"}
        keep = self.trab.obtener(id_keep)
        merge = self.trab.obtener(id_merge)
        counts = {"plata": 0, "pita": 0, "taller": 0, "trabajos": 0}
        with self.db.cursor() as cur:
            for table, key in (
                ("produccion_plata", "plata"),
                ("produccion_pita", "pita"),
                ("nomina_taller", "taller"),
                ("trabajos", "trabajos"),
            ):
                try:
                    cur.execute(
                        f"UPDATE {table} SET trabajador_id = %s WHERE trabajador_id = %s",
                        (id_keep, id_merge),
                    )
                    counts[key] = max(0, cur.rowcount or 0)
                except Exception as e:
                    logger.warning("merge %s: %s", table, e)
            # desactivar el fusionado
            cur.execute(
                "UPDATE trabajadores SET activo = 0, notas = CONCAT(COALESCE(notas,''), %s) WHERE id = %s",
                (f" [fusionado→{id_keep}]", id_merge),
            )
            try:
                self.db.connect().commit()
            except Exception:
                pass
        # sync denormalizados del que se queda
        try:
            self.trab.sincronizar_denormalizados(id_keep)
        except Exception:
            pass
        self.registrar(
            "merge",
            entidad="trabajador",
            entidad_id=id_keep,
            payload={"merged": id_merge, "counts": counts, "keep": keep.get("nombre_mostrar"), "from": merge.get("nombre_mostrar")},
        )
        return {"ok": True, "keep": id_keep, "merged": id_merge, "counts": counts}

    def resumen_aprendizaje(self) -> dict:
        """KPIs simples para panel Dev."""
        out: dict[str, Any] = {
            "eventos_7d": 0,
            "stats": [],
            "folios_inactivos": [],
            "candidatos_dup": [],
            "tabla_ok": True,
        }
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS n FROM aprendizaje_eventos
                    WHERE creado_en >= (NOW() - INTERVAL 7 DAY)
                    """
                )
                out["eventos_7d"] = int((cur.fetchone() or {}).get("n") or 0)
                cur.execute(
                    "SELECT clave, valor_num, valor_txt, muestras FROM aprendizaje_stats ORDER BY actualizado_en DESC LIMIT 30"
                )
                out["stats"] = [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            out["tabla_ok"] = False
        try:
            out["folios_inactivos"] = self.detectar_folios_inactivos()[:40]
            out["reasignaciones"] = self.detectar_reasignaciones()[:40]
            out["candidatos_dup"] = self.candidatos_duplicados_trabajadores()[:30]
        except Exception:
            logger.exception("resumen_aprendizaje")
        return out
