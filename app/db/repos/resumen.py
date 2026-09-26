"""Repositorio: ResumenRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class ResumenRepo(BaseRepo):
    def listar(self) -> list[dict]:
        sql = """
            SELECT r.*, s.codigo, s.fecha_inicio, s.fecha_fin
            FROM resumen_nominas r
            JOIN semanas s ON s.id = r.semana_id
            ORDER BY s.fecha_inicio DESC
        """
        with self.db.cursor() as cur:
            cur.execute(sql)
            return list(cur.fetchall())

    def guardar(self, semana_id: int, data: dict) -> None:
        sql = """
            INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nomina_plt = VALUES(nomina_plt),
                nomina_pit = VALUES(nomina_pit),
                nomina_tll = VALUES(nomina_tll),
                notas = VALUES(notas)
        """
        with self.db.cursor() as cur:
            cur.execute(
                sql,
                (
                    semana_id,
                    data.get("nomina_plt"),
                    data.get("nomina_pit"),
                    data.get("nomina_tll"),
                    data.get("notas"),
                ),
            )

    def totales_vivos(self, semana_id: int) -> dict:
        """Totales reales desde tablas de captura (fuente de verdad)."""
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(efectivo),0) AS v FROM produccion_plata WHERE semana_id=%s",
                (semana_id,),
            )
            plt = float((cur.fetchone() or {}).get("v") or 0)
            try:
                cur.execute(
                    "SELECT COALESCE(SUM(efectivo),0) AS v FROM produccion_pita WHERE semana_id=%s",
                    (semana_id,),
                )
                pit = float((cur.fetchone() or {}).get("v") or 0)
            except Exception:
                pit = 0.0
            try:
                cur.execute(
                    "SELECT COALESCE(SUM(total),0) AS v FROM nomina_taller WHERE semana_id=%s",
                    (semana_id,),
                )
                tll = float((cur.fetchone() or {}).get("v") or 0)
            except Exception:
                tll = 0.0
        return {
            "nomina_plt": plt,
            "nomina_pit": pit,
            "nomina_tll": tll,
            "total_semana": plt + pit + tll,
        }

    def recalcular(self, semana_id: int, notas: str | None = None) -> dict:
        """Sincroniza resumen_nominas con los totales vivos de la semana."""
        vivos = self.totales_vivos(semana_id)
        self.guardar(
            semana_id,
            {
                "nomina_plt": vivos["nomina_plt"],
                "nomina_pit": vivos["nomina_pit"],
                "nomina_tll": vivos["nomina_tll"],
                "notas": notas or "Recalculado desde captura",
            },
        )
        return vivos

    def recalcular_todas(self, limit: int = 52) -> dict:
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT id FROM semanas ORDER BY fecha_inicio DESC LIMIT %s",
                (limit,),
            )
            ids = [int(r["id"]) for r in (cur.fetchall() or [])]
        ok = 0
        for sid in ids:
            try:
                self.recalcular(sid)
                ok += 1
            except Exception:
                pass
        return {"ok": True, "semanas": ok}


