"""
Repositorios de acceso a datos.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from .connection import Database


class BaseRepo:
    def __init__(self, db: Optional[Database] = None):
        self.db = db or Database()


class TrabajadoresRepo(BaseRepo):
    def listar(self, solo_plt: bool = False, solo_activos: bool = True) -> list[dict]:
        sql = """
            SELECT id, nombre_mostrar, nombre_completo, ubic, tipo, puesto,
                   activo, fecha_incorporacion, notas
            FROM trabajadores
            WHERE 1=1
        """
        params: list[Any] = []
        if solo_activos:
            sql += " AND activo = 1"
        if solo_plt:
            sql += " AND (tipo = 'PLT' OR tipo = 'PLT/PIT' OR tipo = 'Mixto')"
        sql += " ORDER BY nombre_mostrar, ubic"
        cur = self.db.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def agregar(
        self,
        nombre_mostrar: str,
        ubic: int,
        tipo: str = "PLT",
        nombre_completo: str | None = None,
        puesto: str | None = None,
        fecha_incorporacion: date | str | None = None,
        notas: str | None = None,
    ) -> int:
        sql = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion, notas)
            VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
        """
        cur = self.db.cursor()
        cur.execute(
            sql,
            (
                nombre_mostrar,
                nombre_completo or nombre_mostrar,
                ubic,
                tipo,
                puesto,
                fecha_incorporacion,
                notas,
            ),
        )
        new_id = cur.lastrowid
        cur.close()
        return new_id

    def actualizar(self, trabajador_id: int, **kwargs) -> None:
        allowed = {
            "nombre_mostrar", "nombre_completo", "ubic", "tipo",
            "puesto", "activo", "fecha_incorporacion", "notas",
        }
        fields = {k: v for k, v in kwargs.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k} = %s" for k in fields)
        sql = f"UPDATE trabajadores SET {sets} WHERE id = %s"
        cur = self.db.cursor()
        cur.execute(sql, (*fields.values(), trabajador_id))
        cur.close()

    def desactivar(self, trabajador_id: int) -> None:
        self.actualizar(trabajador_id, activo=0)


class SemanasRepo(BaseRepo):
    def listar(self, anio: int | None = None) -> list[dict]:
        sql = "SELECT * FROM semanas"
        params: list[Any] = []
        if anio:
            sql += " WHERE anio = %s"
            params.append(anio)
        sql += " ORDER BY fecha_inicio DESC"
        cur = self.db.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def obtener(self, semana_id: int) -> dict | None:
        cur = self.db.cursor()
        cur.execute("SELECT * FROM semanas WHERE id = %s", (semana_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def crear(
        self,
        codigo: str,
        fecha_inicio: date | str,
        fecha_fin: date | str,
        anio: int = 2026,
        notas: str | None = None,
    ) -> int:
        sql = """
            INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas)
            VALUES (%s, %s, %s, %s, %s)
        """
        cur = self.db.cursor()
        cur.execute(sql, (codigo, fecha_inicio, fecha_fin, anio, notas))
        new_id = cur.lastrowid
        cur.close()
        return new_id


class ProduccionRepo(BaseRepo):
    def listar_por_semana(self, semana_id: int) -> list[dict]:
        sql = """
            SELECT id, semana_id, trabajador_id, nombre, ubic, folio, modelo,
                   material, tarifa_gr,
                   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie,
                   total_gramos, efectivo, firmado, notas
            FROM produccion_plata
            WHERE semana_id = %s
            ORDER BY nombre, ubic, id
        """
        cur = self.db.cursor()
        cur.execute(sql, (semana_id,))
        rows = cur.fetchall()
        cur.close()
        return rows

    def insertar(self, semana_id: int, data: dict) -> int:
        sql = """
            INSERT INTO produccion_plata (
                semana_id, trabajador_id, nombre, ubic, folio, modelo, material, tarifa_gr,
                gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        cur = self.db.cursor()
        cur.execute(
            sql,
            (
                semana_id,
                data.get("trabajador_id"),
                data["nombre"],
                data["ubic"],
                data.get("folio"),
                data.get("modelo"),
                data.get("material"),
                data.get("tarifa_gr"),
                data.get("gm_sab"),
                data.get("gm_dom"),
                data.get("gm_lun"),
                data.get("gm_mar"),
                data.get("gm_mie"),
                data.get("gm_jue"),
                data.get("gm_vie"),
                data.get("notas"),
            ),
        )
        new_id = cur.lastrowid
        cur.close()
        return new_id

    def actualizar(self, prod_id: int, data: dict) -> None:
        allowed = {
            "folio", "modelo", "material", "tarifa_gr",
            "gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie",
            "firmado", "notas", "nombre", "ubic", "trabajador_id",
        }
        fields = {k: v for k, v in data.items() if k in allowed}
        if not fields:
            return
        sets = ", ".join(f"{k} = %s" for k in fields)
        sql = f"UPDATE produccion_plata SET {sets} WHERE id = %s"
        cur = self.db.cursor()
        cur.execute(sql, (*fields.values(), prod_id))
        cur.close()

    def eliminar(self, prod_id: int) -> None:
        cur = self.db.cursor()
        cur.execute("DELETE FROM produccion_plata WHERE id = %s", (prod_id,))
        cur.close()

    def totales_semana(self, semana_id: int) -> dict:
        sql = """
            SELECT
                COUNT(*) AS lineas,
                COALESCE(SUM(total_gramos), 0) AS total_gramos,
                COALESCE(SUM(efectivo), 0) AS total_efectivo
            FROM produccion_plata
            WHERE semana_id = %s
        """
        cur = self.db.cursor()
        cur.execute(sql, (semana_id,))
        row = cur.fetchone()
        cur.close()
        return row or {"lineas": 0, "total_gramos": 0, "total_efectivo": 0}


class ResumenRepo(BaseRepo):
    def listar(self) -> list[dict]:
        sql = """
            SELECT r.*, s.codigo, s.fecha_inicio, s.fecha_fin
            FROM resumen_nominas r
            JOIN semanas s ON s.id = r.semana_id
            ORDER BY s.fecha_inicio DESC
        """
        cur = self.db.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        return rows

    def guardar(
        self,
        semana_id: int,
        nomina_plt: float | Decimal | None = None,
        nomina_pit: float | Decimal | None = None,
        nomina_tll: float | Decimal | None = None,
        notas: str | None = None,
    ) -> None:
        sql = """
            INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nomina_plt = VALUES(nomina_plt),
                nomina_pit = VALUES(nomina_pit),
                nomina_tll = VALUES(nomina_tll),
                notas = VALUES(notas)
        """
        cur = self.db.cursor()
        cur.execute(sql, (semana_id, nomina_plt, nomina_pit, nomina_tll, notas))
        cur.close()
