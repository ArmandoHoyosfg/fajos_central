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
        """Líneas y gramos/efectivo por área (para UI de borrado y avisos)."""
        out = {
            "plt": 0, "pit": 0, "tll": 0, "total": 0,
            "gramos_plt": 0.0, "solo_estructura": False,
        }
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) AS n,
                           COALESCE(SUM(total_gramos), 0) AS g
                    FROM produccion_plata WHERE semana_id=%s
                    """,
                    (semana_id,),
                )
                row = cur.fetchone() or {}
                out["plt"] = int(row.get("n") or 0)
                out["gramos_plt"] = float(row.get("g") or 0)
            except Exception:
                out["plt"] = 0
            try:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM produccion_pita WHERE semana_id=%s",
                    (semana_id,),
                )
                out["pit"] = int((cur.fetchone() or {}).get("n") or 0)
            except Exception:
                out["pit"] = 0
            try:
                cur.execute(
                    "SELECT COUNT(*) AS n FROM nomina_taller WHERE semana_id=%s",
                    (semana_id,),
                )
                out["tll"] = int((cur.fetchone() or {}).get("n") or 0)
            except Exception:
                out["tll"] = 0
        out["total"] = out["plt"] + out["pit"] + out["tll"]
        # Duplicar semana crea líneas con 0g: no es "vacía" pero sí solo estructura
        out["solo_estructura"] = out["total"] > 0 and out["gramos_plt"] <= 0.001
        return out

    def eliminar(self, semana_id: int, *, force: bool = False) -> dict:
        """
        Elimina la semana.
        - Sin líneas: borra siempre.
        - Con líneas: requiere force=True (borra en cascada Plata/Pita/Taller).
        """
        from app.core.exceptions import ValidationAppError, NotFoundError
        sem = self.obtener(semana_id) if hasattr(self, "obtener") else None
        if sem is None:
            with self.db.cursor() as cur:
                cur.execute("SELECT id, codigo FROM semanas WHERE id=%s", (semana_id,))
                sem = cur.fetchone()
            if not sem:
                raise NotFoundError(f"Semana id={semana_id} no existe.", details={"semana_id": semana_id})
        uso = self.conteo_uso(semana_id)
        if uso["total"] > 0 and not force:
            msg = (
                f"La semana tiene {uso['total']} línea(s) "
                f"(Plata {uso['plt']}, Pita {uso['pit']}, Taller {uso['tll']})"
            )
            if uso.get("solo_estructura"):
                msg += " — parecen copiadas al duplicar (sin gramos en Plata)."
            msg += " Confirma el borrado forzado para eliminarlas junto con la semana."
            raise ValidationAppError(msg, details=uso)
        with self.db.cursor() as cur:
            if uso["total"] > 0:
                for table in (
                    "produccion_plata",
                    "produccion_pita",
                    "nomina_taller",
                    "resumen_nominas",
                ):
                    try:
                        cur.execute(f"DELETE FROM {table} WHERE semana_id=%s", (semana_id,))
                    except Exception:
                        pass
            cur.execute("DELETE FROM semanas WHERE id=%s", (semana_id,))
            if cur.rowcount == 0:
                raise NotFoundError(f"Semana id={semana_id} no existe.", details={"semana_id": semana_id})
        return {
            "ok": True,
            "eliminada": semana_id,
            "codigo": (sem or {}).get("codigo"),
            "uso_previo": uso,
            "force": bool(force),
        }

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


