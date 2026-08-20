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


    def cerrar(self, semana_id: int, usuario: str | None = None) -> None:
        cur = self.db.cursor()
        cur.execute(
            "UPDATE semanas SET cerrada=1, cerrada_en=CURRENT_TIMESTAMP, cerrada_por=%s WHERE id=%s",
            (usuario, semana_id),
        )
        cur.close()

    def reabrir(self, semana_id: int) -> None:
        cur = self.db.cursor()
        cur.execute(
            "UPDATE semanas SET cerrada=0, cerrada_en=NULL, cerrada_por=NULL WHERE id=%s",
            (semana_id,),
        )
        cur.close()

    def esta_cerrada(self, semana_id: int) -> bool:
        cur = self.db.cursor()
        cur.execute("SELECT cerrada FROM semanas WHERE id=%s", (semana_id,))
        row = cur.fetchone()
        cur.close()
        return bool(row and row.get("cerrada"))


class ProduccionRepo(BaseRepo):
    def duplicar_trabajos_a_semana(self, semana_origen_id, semana_destino_id):
        return _duplicar_trabajos_impl(self.db, semana_origen_id, semana_destino_id)



    def listar_por_semana(self, semana_id: int) -> list[dict]:
        sql = """
            SELECT id, semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo,
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
        cur = self.db.cursor()
        cur.execute("SELECT cerrada FROM semanas WHERE id=%s", (semana_id,))
        sem = cur.fetchone()
        if sem and sem.get("cerrada"):
            cur.close()
            raise ValueError("La semana está cerrada; no se puede agregar producción.")
        tid = data.get("trabajador_id")
        if not tid:
            cur.execute(
                "SELECT id FROM trabajadores WHERE nombre_mostrar=%s AND ubic=%s LIMIT 1",
                (data["nombre"], data["ubic"]),
            )
            row = cur.fetchone()
            if not row:
                cur.close()
                raise ValueError(
                    "Trabajador no está en catálogo: %s (ubic %s)" % (data["nombre"], data["ubic"])
                )
            tid = row["id"]
        trabajo_id = data.get("trabajo_id")
        cur.close()
        if not trabajo_id and (data.get("folio") or data.get("modelo")):
            trabajo_id = TrabajosRepo(self.db).asegurar(
                tid, data.get("folio"), data.get("modelo"),
                data.get("material"), data.get("tarifa_gr"), data.get("notas"),
            )
        sql = """
            INSERT INTO produccion_plata (
                semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
                gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        cur = self.db.cursor()
        cur.execute(
            sql,
            (
                semana_id, tid, trabajo_id, data["nombre"], data["ubic"],
                data.get("folio"), data.get("modelo"), data.get("material"), data.get("tarifa_gr"),
                data.get("gm_sab"), data.get("gm_dom"), data.get("gm_lun"),
                data.get("gm_mar"), data.get("gm_mie"), data.get("gm_jue"),
                data.get("gm_vie"), data.get("notas"),
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

    def actualizar_gramos_dia(self, prod_id: int, col: str, gramos) -> None:
        allowed = {"gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"}
        if col not in allowed:
            raise ValueError(f"Columna de día inválida: {col}")
        val = None
        if gramos is not None:
            try:
                f = float(gramos)
                val = None if f == 0 else f
            except (TypeError, ValueError):
                val = None
        cur = self.db.cursor()
        cur.execute(
            f"SELECT semana_id, {col} AS old_v FROM produccion_plata WHERE id=%s",
            (prod_id,),
        )
        row = cur.fetchone()
        if not row:
            cur.close()
            raise ValueError(f"Línea id={prod_id} no existe")
        semana_id = row["semana_id"]
        old_v = row.get("old_v")
        cur.execute("SELECT cerrada FROM semanas WHERE id=%s", (semana_id,))
        sem = cur.fetchone()
        if sem and sem.get("cerrada"):
            cur.close()
            raise ValueError("La semana está cerrada; no se puede editar.")
        cur.execute(f"UPDATE produccion_plata SET {col}=%s WHERE id=%s", (val, prod_id))
        try:
            cur.execute(
                "INSERT INTO historial_produccion "
                "(produccion_id, semana_id, campo, valor_anterior, valor_nuevo, origen) "
                "VALUES (%s,%s,%s,%s,%s,'desktop')",
                (prod_id, semana_id, col, None if old_v is None else str(old_v), None if val is None else str(val)),
            )
        except Exception:
            pass
        cur.close()

    def buscar_linea(
        self,
        semana_id: int,
        nombre: str,
        ubic: int,
        folio: str | None = None,
    ) -> dict | None:
        cur = self.db.cursor()
        if folio:
            cur.execute(
                "SELECT * FROM produccion_plata WHERE semana_id=%s AND nombre=%s AND ubic=%s AND folio=%s LIMIT 1",
                (semana_id, nombre, ubic, folio),
            )
        else:
            cur.execute(
                "SELECT * FROM produccion_plata WHERE semana_id=%s AND nombre=%s AND ubic=%s "
                "AND (folio IS NULL OR folio='') LIMIT 1",
                (semana_id, nombre, ubic),
            )
        row = cur.fetchone()
        cur.close()
        return row

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


class TarifasRepo(BaseRepo):
    def mapa(self) -> dict[str, float]:
        try:
            cur = self.db.cursor()
            cur.execute(
                "SELECT material, tarifa_por_gramo FROM tarifas_material WHERE activo=1"
            )
            rows = cur.fetchall() or []
            cur.close()
            return {
                str(r["material"]).upper(): float(r["tarifa_por_gramo"])
                for r in rows if r.get("material") is not None
            }
        except Exception:
            return {"AG3": 12.0, "AG4": 13.0, "DOL": 13.0, "DLO": 13.0}


class TrabajosRepo(BaseRepo):
    def listar_con_semana(self, semana_id: int, solo_activos: bool = True):
        sql = """
            SELECT
              t.id AS trabajo_id, t.folio, t.modelo, t.material,
              t.tarifa_gr AS tarifa_trabajo, t.activo AS trabajo_activo,
              tr.id AS trabajador_id, tr.nombre_mostrar AS nombre, tr.ubic, tr.tipo,
              p.id AS produccion_id, p.semana_id,
              p.gm_sab, p.gm_dom, p.gm_lun, p.gm_mar, p.gm_mie, p.gm_jue, p.gm_vie,
              p.total_gramos, p.efectivo, p.firmado,
              COALESCE(p.tarifa_gr, t.tarifa_gr) AS tarifa_gr
            FROM trabajos t
            JOIN trabajadores tr ON tr.id = t.trabajador_id
            LEFT JOIN produccion_plata p ON p.trabajo_id = t.id AND p.semana_id = %s
            WHERE 1=1
        """
        params = [semana_id]
        if solo_activos:
            sql += " AND t.activo = 1 AND tr.activo = 1"
        sql += " ORDER BY tr.ubic, tr.nombre_mostrar, t.folio"
        cur = self.db.cursor()
        cur.execute(sql, params)
        rows = list(cur.fetchall() or [])
        cur.close()
        return rows


    def listar(self, solo_activos: bool = True, trabajador_id=None):
        sql = """
            SELECT t.*, tr.nombre_mostrar, tr.ubic, tr.tipo
            FROM trabajos t
            JOIN trabajadores tr ON tr.id = t.trabajador_id
            WHERE 1=1
        """
        params = []
        if solo_activos:
            sql += " AND t.activo = 1 AND tr.activo = 1"
        if trabajador_id is not None:
            sql += " AND t.trabajador_id = %s"
            params.append(trabajador_id)
        sql += " ORDER BY tr.nombre_mostrar, t.folio"
        cur = self.db.cursor()
        cur.execute(sql, params)
        rows = list(cur.fetchall() or [])
        cur.close()
        return rows

    def asegurar(self, trabajador_id, folio=None, modelo=None, material=None, tarifa_gr=None, notas=None):
        cur = self.db.cursor()
        cur.execute(
            "SELECT id FROM trabajos WHERE trabajador_id=%s "
            "AND COALESCE(folio,'')=COALESCE(%s,'') AND COALESCE(material,'')=COALESCE(%s,'') LIMIT 1",
            (trabajador_id, folio, material),
        )
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE trabajos SET modelo=COALESCE(%s,modelo), tarifa_gr=COALESCE(%s,tarifa_gr), activo=1 WHERE id=%s",
                (modelo, tarifa_gr, row["id"]),
            )
            cur.close()
            return int(row["id"])
        cur.execute(
            "INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas) "
            "VALUES (%s,%s,%s,%s,%s,1,%s)",
            (trabajador_id, folio, modelo, material, tarifa_gr, notas),
        )
        new_id = cur.lastrowid
        cur.close()
        return int(new_id)


def _duplicar_trabajos_impl(db, semana_origen_id, semana_destino_id):
    cur = db.cursor()
    cur.execute(
        "SELECT trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr "
        "FROM produccion_plata WHERE semana_id=%s",
        (semana_origen_id,),
    )
    origen = list(cur.fetchall() or [])
    cur.execute(
        "SELECT t.id AS trabajo_id, t.trabajador_id, tr.nombre_mostrar AS nombre, tr.ubic, "
        "t.folio, t.modelo, t.material, t.tarifa_gr FROM trabajos t "
        "JOIN trabajadores tr ON tr.id=t.trabajador_id WHERE t.activo=1 AND tr.activo=1"
    )
    todos = list(cur.fetchall() or [])
    seen = set()
    to_insert = []
    for r in origen + todos:
        key = (r.get("trabajador_id"), r.get("trabajo_id") or r.get("folio"), r.get("material"))
        if key in seen:
            continue
        seen.add(key)
        to_insert.append(r)
    created = skipped = 0
    for r in to_insert:
        cur.execute(
            "SELECT id FROM produccion_plata WHERE semana_id=%s AND trabajador_id=%s "
            "AND COALESCE(folio,'')=COALESCE(%s,'') AND COALESCE(material,'')=COALESCE(%s,'') LIMIT 1",
            (semana_destino_id, r.get("trabajador_id"), r.get("folio"), r.get("material")),
        )
        if cur.fetchone():
            skipped += 1
            continue
        cur.execute(
            "INSERT INTO produccion_plata "
            "(semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                semana_destino_id, r.get("trabajador_id"), r.get("trabajo_id"),
                r.get("nombre"), r.get("ubic"), r.get("folio"), r.get("modelo"),
                r.get("material"), r.get("tarifa_gr"),
            ),
        )
        created += 1
    cur.close()
    return {"created": created, "skipped": skipped, "total_candidates": len(to_insert)}
