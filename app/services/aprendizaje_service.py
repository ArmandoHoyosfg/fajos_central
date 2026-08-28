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
        Folios activos (no terminados) con 0 g en la semana actual
        y que tuvieron gramos en la semana anterior → posible finalizado / reasignado.
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
        # semana anterior por fecha
        prev = None
        fi = parse_db_date(actual.get("fecha_inicio"))
        if fi:
            prev_ref = fi - timedelta(days=1)
            prev = encontrar_semana_actual(semanas, prev_ref)

        prev_map: dict[str, dict] = {}
        if prev:
            for r in self.prod.listar_por_semana(int(prev["id"])):
                folio = (r.get("folio") or "").strip()
                if not folio:
                    continue
                key = folio.upper()
                g = self._gramos_linea(r)
                if g > 0:
                    prev_map[key] = {
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "trabajador_id": r.get("trabajador_id"),
                        "gramos": g,
                        "semana": prev.get("codigo"),
                    }

        out: list[dict] = []
        for r in lineas:
            folio = (r.get("folio") or "").strip()
            if not folio:
                continue
            g = self._gramos_linea(r)
            if g > 0:
                continue
            key = folio.upper()
            prev_info = prev_map.get(key)
            # también: folio en trabajos activos sin gramos esta semana
            hint = "sin_avance_esta_semana"
            if prev_info:
                if prev_info.get("trabajador_id") and r.get("trabajador_id"):
                    if int(prev_info["trabajador_id"]) != int(r["trabajador_id"]):
                        hint = "posible_reasignacion"
                    else:
                        hint = "posible_finalizado"
                else:
                    same = (
                        str(prev_info.get("nombre") or "").lower()
                        == str(r.get("nombre") or "").lower()
                    )
                    hint = "posible_finalizado" if same else "posible_reasignacion"
            out.append({
                "prod_id": r.get("id"),
                "folio": folio,
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "trabajador_id": r.get("trabajador_id"),
                "hint": hint,
                "prev": prev_info,
                "semana_id": sid,
            })
        return out

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
            out["candidatos_dup"] = self.candidatos_duplicados_trabajadores()[:30]
        except Exception:
            logger.exception("resumen_aprendizaje")
        return out
