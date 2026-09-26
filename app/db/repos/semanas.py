"""Repositorio: SemanasRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class SemanasRepo(BaseRepo):
    def listar(self, anio: int | None = None) -> list[dict]:
        sql = "SELECT * FROM semanas"
        params: list[Any] = []
        if anio:
            sql += " WHERE anio = %s"
            params.append(anio)
        sql += " ORDER BY fecha_inicio DESC"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def obtener(self, semana_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM semanas WHERE id = %s", (semana_id,))
            row = cur.fetchone()
        if not row:
            raise NotFoundError(
                f"Semana id={semana_id} no existe.",
                details={"semana_id": semana_id},
            )
        return row

    def crear(self, data: dict) -> int:
        required = ["codigo", "fecha_inicio", "fecha_fin"]
        for f in required:
            if not data.get(f):
                raise ValidationAppError(f"Campo obligatorio: {f}", details={"field": f})
        sql = """
            INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas)
            VALUES (%s, %s, %s, %s, %s)
        """
        anio = data.get("anio") or date.today().year
        with self.db.cursor() as cur:
            cur.execute(
                sql,
                (data["codigo"], data["fecha_inicio"], data["fecha_fin"], anio, data.get("notas")),
            )
            return cur.lastrowid



    def cerrar(self, semana_id: int, usuario: str | None = None) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE semanas
                SET cerrada = 1, cerrada_en = CURRENT_TIMESTAMP, cerrada_por = %s
                WHERE id = %s
                """,
                (usuario, semana_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Semana id={semana_id} no existe.", details={"semana_id": semana_id})

    def actualizar(self, semana_id: int, data: dict) -> None:
        fields = []
        vals = []
        for key in ("codigo", "fecha_inicio", "fecha_fin", "anio", "notas"):
            if key in data and data[key] is not None:
                fields.append(f"{key}=%s")
                vals.append(data[key])
        if not fields:
            return
        vals.append(semana_id)
        with self.db.cursor() as cur:
            cur.execute(
                f"UPDATE semanas SET {', '.join(fields)} WHERE id=%s",
                tuple(vals),
            )


    def conteo_uso(self, semana_id: int) -> dict:
        """Cuántas líneas hay en cada área (para impedir borrar semanas con datos)."""
        out = {"plt": 0, "pit": 0, "tll": 0, "total": 0}
        with self.db.cursor() as cur:
            for key, table in (
                ("plt", "produccion_plata"),
                ("pit", "produccion_pita"),
                ("tll", "nomina_taller"),
            ):
                try:
                    cur.execute(
                        f"SELECT COUNT(*) AS n FROM {table} WHERE semana_id=%s",
                        (semana_id,),
                    )
                    out[key] = int((cur.fetchone() or {}).get("n") or 0)
                except Exception:
                    out[key] = 0
        out["total"] = out["plt"] + out["pit"] + out["tll"]
        return out

    def eliminar(self, semana_id: int, *, force: bool = False) -> dict:
        """
        Elimina la semana. Por defecto solo si no tiene líneas.
        force=True borra también líneas (peligroso).
        """
        from app.core.exceptions import ValidationAppError
        uso = self.conteo_uso(semana_id)
        if uso["total"] > 0 and not force:
            raise ValidationAppError(
                "La semana tiene datos (Plata/Pita/Taller). "
                "No se puede eliminar. Corrige fechas o usa force solo si estás seguro.",
                details=uso,
            )
        with self.db.cursor() as cur:
            if force and uso["total"] > 0:
                for table in ("produccion_plata", "produccion_pita", "nomina_taller", "resumen_nominas"):
                    try:
                        cur.execute(f"DELETE FROM {table} WHERE semana_id=%s", (semana_id,))
                    except Exception:
                        pass
            cur.execute("DELETE FROM semanas WHERE id=%s", (semana_id,))
        return {"ok": True, "eliminada": semana_id, "uso_previo": uso}

    def reabrir(self, semana_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE semanas
                SET cerrada = 0, cerrada_en = NULL, cerrada_por = NULL
                WHERE id = %s
                """,
                (semana_id,),
            )
            if cur.rowcount == 0:
                raise NotFoundError(f"Semana id={semana_id} no existe.", details={"semana_id": semana_id})

    def esta_cerrada(self, semana_id: int) -> bool:
        with self.db.cursor() as cur:
            cur.execute("SELECT cerrada FROM semanas WHERE id = %s", (semana_id,))
            row = cur.fetchone()
        return bool(row and row.get("cerrada"))


