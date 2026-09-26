"""Repositorio: DashboardRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class DashboardRepo(BaseRepo):
    """Consultas agregadas para el dashboard."""

    def resumen_general(self) -> dict:
        with self.db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM trabajadores WHERE activo = 1")
            activos = cur.fetchone()["n"]

            cur.execute(
                "SELECT COUNT(*) AS n FROM trabajadores WHERE activo = 1 "
                "AND tipo IN ('PLT','PLT/PIT','Mixto')"
            )
            plt_activos = cur.fetchone()["n"]

            cur.execute("SELECT COUNT(*) AS n FROM semanas")
            total_semanas = cur.fetchone()["n"]

            cur.execute(
                """
                SELECT COALESCE(SUM(total_gramos),0) AS gramos,
                       COALESCE(SUM(efectivo),0) AS efectivo
                FROM produccion_plata
                """
            )
            prod = cur.fetchone()

            cur.execute(
                """
                SELECT COALESCE(SUM(nomina_plt),0) AS plt,
                       COALESCE(SUM(nomina_pit),0) AS pit,
                       COALESCE(SUM(nomina_tll),0) AS tll,
                       COALESCE(SUM(total_semana),0) AS total
                FROM resumen_nominas
                """
            )
            nom = cur.fetchone()

        return {
            "trabajadores_activos": activos,
            "trabajadores_plt": plt_activos,
            "total_semanas": total_semanas,
            "total_gramos_historico": prod["gramos"],
            "total_efectivo_historico": prod["efectivo"],
            "nomina_plt_acumulada": nom["plt"],
            "nomina_pit_acumulada": nom["pit"],
            "nomina_tll_acumulada": nom["tll"],
            "nomina_total_acumulada": nom["total"],
        }

    def ultimas_semanas(self, limit: int = 8) -> list[dict]:
        """Totales desde captura en vivo (no depende de resumen desactualizado)."""
        sql = """
            SELECT s.id, s.codigo, s.fecha_inicio, s.fecha_fin,
                   COALESCE(s.cerrada, 0) AS cerrada,
                   COALESCE((
                       SELECT SUM(p.efectivo) FROM produccion_plata p WHERE p.semana_id = s.id
                   ), 0) AS nomina_plt,
                   COALESCE((
                       SELECT SUM(pi.efectivo) FROM produccion_pita pi WHERE pi.semana_id = s.id
                   ), 0) AS nomina_pit,
                   COALESCE((
                       SELECT SUM(t.total) FROM nomina_taller t WHERE t.semana_id = s.id
                   ), 0) AS nomina_tll
            FROM semanas s
            ORDER BY s.fecha_inicio DESC
            LIMIT %s
        """
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, (limit,))
                rows = list(cur.fetchall() or [])
            except Exception:
                # fallback sin subconsultas / sin cerrada
                cur.execute(
                    """
                    SELECT s.id, s.codigo, s.fecha_inicio, s.fecha_fin,
                           COALESCE(r.nomina_plt, 0) AS nomina_plt,
                           COALESCE(r.nomina_pit, 0) AS nomina_pit,
                           COALESCE(r.nomina_tll, 0) AS nomina_tll,
                           COALESCE(r.total_semana, 0) AS total_semana
                    FROM semanas s
                    LEFT JOIN resumen_nominas r ON r.semana_id = s.id
                    ORDER BY s.fecha_inicio DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                rows = list(cur.fetchall() or [])
            for r in rows:
                plt = float(r.get("nomina_plt") or 0)
                pit = float(r.get("nomina_pit") or 0)
                tll = float(r.get("nomina_tll") or 0)
                r["nomina_plt"] = plt
                r["nomina_pit"] = pit
                r["nomina_tll"] = tll
                r["total_semana"] = plt + pit + tll
            return rows



