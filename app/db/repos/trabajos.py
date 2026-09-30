"""Repositorio: TrabajosRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class TrabajosRepo(BaseRepo):
    """Trabajos en progreso: folio/modelo/material ligados a trabajador."""

    def listar(self, solo_activos: bool = True, trabajador_id: int | None = None) -> list[dict]:
        sql = """
            SELECT t.*, tr.nombre_mostrar, tr.ubic, tr.tipo
            FROM trabajos t
            JOIN trabajadores tr ON tr.id = t.trabajador_id
            WHERE 1=1
        """
        params: list = []
        if solo_activos:
            sql += " AND t.activo = 1 AND tr.activo = 1"
        if trabajador_id is not None:
            sql += " AND t.trabajador_id = %s"
            params.append(trabajador_id)
        sql += " ORDER BY tr.nombre_mostrar, tr.ubic, t.folio"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall() or [])

    def asegurar(
        self,
        trabajador_id: int,
        folio: str | None = None,
        modelo: str | None = None,
        material: str | None = None,
        tarifa_gr: float | None = None,
        notas: str | None = None,
    ) -> int:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM trabajos
                WHERE trabajador_id = %s
                  AND COALESCE(folio,'') = COALESCE(%s,'')
                  AND COALESCE(material,'') = COALESCE(%s,'')
                LIMIT 1
                """,
                (trabajador_id, folio, material),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    """
                    UPDATE trabajos SET
                      modelo = COALESCE(%s, modelo),
                      tarifa_gr = COALESCE(%s, tarifa_gr),
                      activo = 1,
                      notas = COALESCE(%s, notas)
                    WHERE id = %s
                    """,
                    (modelo, tarifa_gr, notas, row["id"]),
                )
                return int(row["id"])
            cur.execute(
                """
                INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
                VALUES (%s, %s, %s, %s, %s, 1, %s)
                """,
                (trabajador_id, folio, modelo, material, tarifa_gr, notas),
            )
            return int(cur.lastrowid)



    def set_activo(self, trabajo_id: int, activo: bool) -> None:
        with self.db.cursor() as cur:
            try:
                if activo:
                    cur.execute(
                        "UPDATE trabajos SET activo = 1, terminado_en = NULL WHERE id = %s",
                        (trabajo_id,),
                    )
                else:
                    cur.execute(
                        "UPDATE trabajos SET activo = 0, "
                        "terminado_en = COALESCE(terminado_en, CURRENT_TIMESTAMP) WHERE id = %s",
                        (trabajo_id,),
                    )
            except Exception:
                # Sin columna terminado_en (pre-migración 003)
                cur.execute(
                    "UPDATE trabajos SET activo = %s WHERE id = %s",
                    (1 if activo else 0, trabajo_id),
                )

    def marcar_terminado(self, trabajo_id: int, terminado: bool = True) -> dict:
        """Marca folio terminado (activo=0) o lo reabre."""
        self.set_activo(trabajo_id, activo=not terminado)
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT t.*, tr.nombre_mostrar, tr.ubic
                FROM trabajos t
                JOIN trabajadores tr ON tr.id = t.trabajador_id
                WHERE t.id = %s
                """,
                (trabajo_id,),
            )
            row = cur.fetchone()
        return row or {"id": trabajo_id}

    def desempeno_trabajador(self, trabajador_id: int) -> dict:
        """Resumen de folios y gramos por trabajador."""
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT t.id, t.folio, t.modelo, t.material, t.activo, t.terminado_en,
                           t.tarifa_gr, t.creado_en
                    FROM trabajos t
                    WHERE t.trabajador_id = %s
                    ORDER BY t.activo DESC, t.creado_en DESC
                    """,
                    (trabajador_id,),
                )
            except Exception:
                cur.execute(
                    """
                    SELECT t.id, t.folio, t.modelo, t.material, t.activo,
                           t.tarifa_gr, t.creado_en
                    FROM trabajos t
                    WHERE t.trabajador_id = %s
                    ORDER BY t.activo DESC, t.creado_en DESC
                    """,
                    (trabajador_id,),
                )
            trabajos = list(cur.fetchall() or [])
            for t in trabajos:
                t.setdefault("terminado_en", None)
            try:
                cur.execute(
                    """
                    SELECT p.trabajo_id, p.folio, p.modelo, p.material, p.semana_id,
                           s.codigo AS semana_codigo,
                           COALESCE(p.gm_sab,0)+COALESCE(p.gm_dom,0)+COALESCE(p.gm_lun,0)
                           +COALESCE(p.gm_mar,0)+COALESCE(p.gm_mie,0)+COALESCE(p.gm_jue,0)
                           +COALESCE(p.gm_vie,0) AS total_g
                    FROM produccion_plata p
                    LEFT JOIN semanas s ON s.id = p.semana_id
                    WHERE p.trabajador_id = %s
                    ORDER BY p.semana_id DESC, p.id DESC
                    LIMIT 80
                    """,
                    (trabajador_id,),
                )
                lineas = list(cur.fetchall() or [])
            except Exception:
                lineas = []
        abiertos = sum(1 for t in trabajos if t.get("activo"))
        cerrados = sum(1 for t in trabajos if not t.get("activo"))
        total_g = sum(float(x.get("total_g") or 0) for x in lineas)
        return {
            "trabajador_id": trabajador_id,
            "trabajos": trabajos,
            "lineas_recientes": lineas,
            "folios_abiertos": abiertos,
            "folios_terminados": cerrados,
            "gramos_registrados": total_g,
        }


    def actualizar_meta(self, trabajo_id: int, data: dict) -> None:
        fields, params = [], []
        for k in ("folio", "modelo", "material", "tarifa_gr", "notas", "activo"):
            if k not in data:
                continue
            v = data[k]
            if k == "tarifa_gr":
                try:
                    v = float(v) if v is not None and str(v).strip() != "" else None
                except (TypeError, ValueError):
                    raise ValidationAppError("Tarifa inválida")
            elif k == "activo":
                v = 1 if v in (1, True, "1", "true") else 0
            elif k in ("folio", "modelo", "material", "notas"):
                v = (str(v).strip() if v is not None else "") or None
            fields.append(f"{k}=%s")
            params.append(v)
        if not fields:
            return
        params.append(trabajo_id)
        with self.db.cursor() as cur:
            cur.execute(
                f"UPDATE trabajos SET {', '.join(fields)} WHERE id=%s",
                params,
            )

    def listar_con_semana(self, semana_id: int, solo_activos: bool = True) -> list[dict]:
        """
        Trabajos activos con la línea de producción de la semana (si existe).
        Una fila por trabajo; si no hay producción aún, gramos en NULL.
        """
        sql = """
            SELECT
              t.id AS trabajo_id,
              t.folio, t.modelo, t.material, t.tarifa_gr AS tarifa_trabajo,
              t.activo AS trabajo_activo,
              tr.id AS trabajador_id, tr.nombre_mostrar AS nombre, tr.ubic, tr.tipo,
              p.id AS produccion_id, p.semana_id,
              p.gm_sab, p.gm_dom, p.gm_lun, p.gm_mar, p.gm_mie, p.gm_jue, p.gm_vie,
              p.total_gramos, p.efectivo, p.firmado,
              COALESCE(p.tarifa_gr, t.tarifa_gr) AS tarifa_gr
            FROM trabajos t
            JOIN trabajadores tr ON tr.id = t.trabajador_id
            LEFT JOIN produccion_plata p
              ON p.trabajo_id = t.id AND p.semana_id = %s
            WHERE 1=1
        """
        params: list = [semana_id]
        if solo_activos:
            sql += " AND t.activo = 1 AND tr.activo = 1"
        sql += " ORDER BY tr.ubic, tr.nombre_mostrar, t.folio"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall() or [])


