"""
Repositorios de acceso a datos.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db

logger = get_logger(__name__)


class BaseRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()


class TrabajadoresRepo(BaseRepo):
    def listar(
        self,
        solo_plt: bool = False,
        solo_activos: bool = True,
        busqueda: str | None = None,
    ) -> list[dict]:
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
            sql += " AND (tipo IN ('PLT','PLT/PIT','Mixto'))"
        if busqueda:
            sql += " AND (nombre_mostrar LIKE %s OR nombre_completo LIKE %s OR CAST(ubic AS CHAR) LIKE %s)"
            like = f"%{busqueda}%"
            params.extend([like, like, like])
        sql += " ORDER BY nombre_mostrar, ubic"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return list(cur.fetchall())

    def obtener(self, trabajador_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM trabajadores WHERE id = %s", (trabajador_id,))
            row = cur.fetchone()
        if not row:
            raise NotFoundError(
                f"Trabajador id={trabajador_id} no existe.",
                details={"trabajador_id": trabajador_id},
            )
        return row

    def agregar(self, data: dict) -> int:
        if not data.get("nombre_mostrar"):
            raise ValidationAppError(
                "El nombre es obligatorio.",
                details={"field": "nombre_mostrar"},
            )
        if not data.get("ubic"):
            raise ValidationAppError(
                "La ubicación es obligatoria.",
                details={"field": "ubic"},
            )
        sql = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion, notas)
            VALUES (%s, %s, %s, %s, %s, 1, %s, %s)
        """
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        data["nombre_mostrar"],
                        data.get("nombre_completo") or data["nombre_mostrar"],
                        data["ubic"],
                        data.get("tipo") or "PLT",
                        data.get("puesto"),
                        data.get("fecha_incorporacion"),
                        data.get("notas"),
                    ),
                )
                new_id = cur.lastrowid
            logger.info("Trabajador creado id=%s nombre=%s", new_id, data["nombre_mostrar"])
            return new_id
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError("No se pudo agregar el trabajador.", cause=e) from e

    def desactivar(self, trabajador_id: int) -> None:
        self.obtener(trabajador_id)  # valida existencia
        with self.db.cursor() as cur:
            cur.execute("UPDATE trabajadores SET activo = 0 WHERE id = %s", (trabajador_id,))
        logger.info("Trabajador desactivado id=%s", trabajador_id)


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


class ProduccionRepo(BaseRepo):
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
        with self.db.cursor() as cur:
            cur.execute(sql, (semana_id,))
            return list(cur.fetchall())

    def insertar(self, semana_id: int, data: dict) -> int:
        from app.services.audit_service import AuditService
        AuditService(self.db).assert_semana_abierta(semana_id)
        if not data.get("nombre"):
            raise ValidationAppError("El nombre es obligatorio.", details={"field": "nombre"})
        if data.get("ubic") is None:
            raise ValidationAppError("La ubicación es obligatoria.", details={"field": "ubic"})

        trabajador_id = data.get("trabajador_id")
        if not trabajador_id:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT id FROM trabajadores WHERE nombre_mostrar=%s AND ubic=%s LIMIT 1",
                    (data["nombre"], data["ubic"]),
                )
                row = cur.fetchone()
            if not row:
                raise ValidationAppError(
                    f"No hay trabajador en catálogo: {data['nombre']} (ubic {data['ubic']}). "
                    "Agrégalo primero en Trabajadores.",
                    details={"nombre": data["nombre"], "ubic": data["ubic"]},
                )
            trabajador_id = int(row["id"])

        trabajo_id = data.get("trabajo_id")
        if not trabajo_id and (data.get("folio") or data.get("modelo") or data.get("material")):
            trabajo_id = TrabajosRepo(self.db).asegurar(
                trabajador_id,
                folio=data.get("folio"),
                modelo=data.get("modelo"),
                material=data.get("material"),
                tarifa_gr=data.get("tarifa_gr"),
                notas=data.get("notas"),
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
        with self.db.cursor() as cur:
            cur.execute(
                sql,
                (
                    semana_id,
                    trabajador_id,
                    trabajo_id,
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
            return cur.lastrowid

    def set_firmado(self, prod_id: int, firmado: bool) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE produccion_plata SET firmado = %s WHERE id = %s",
                (1 if firmado else 0, prod_id),
            )
            if cur.rowcount == 0:
                raise NotFoundError(
                    f"Línea de producción id={prod_id} no existe.",
                    details={"produccion_id": prod_id},
                )

    def eliminar(self, prod_id: int) -> None:

        with self.db.cursor() as cur:
            cur.execute("DELETE FROM produccion_plata WHERE id = %s", (prod_id,))
            if cur.rowcount == 0:
                raise NotFoundError(
                    f"Línea de producción id={prod_id} no existe.",
                    details={"produccion_id": prod_id},
                )


    DAY_COLS = {
        "sab": "gm_sab", "dom": "gm_dom", "lun": "gm_lun",
        "mar": "gm_mar", "mie": "gm_mie", "jue": "gm_jue", "vie": "gm_vie",
        "gm_sab": "gm_sab", "gm_dom": "gm_dom", "gm_lun": "gm_lun",
        "gm_mar": "gm_mar", "gm_mie": "gm_mie", "gm_jue": "gm_jue", "gm_vie": "gm_vie",
    }

    def actualizar_gramos_dia(self, prod_id: int, dia: str, gramos: float | None) -> None:
        """Actualiza un solo día de una línea existente (None o 0 = vacío)."""
        from app.services.audit_service import AuditService
        audit = AuditService(self.db)
        col = self.DAY_COLS.get((dia or "").strip().lower())
        if not col:
            raise ValidationAppError(
                f"Día no válido: {dia}. Use sab/dom/lun/mar/mie/jue/vie.",
                details={"dia": dia},
            )
        val = None
        if gramos is not None:
            try:
                f = float(gramos)
                val = None if f == 0 else f
            except (TypeError, ValueError):
                raise ValidationAppError("Gramos inválidos.", details={"gramos": gramos})
        with self.db.cursor() as cur:
            cur.execute(
                f"SELECT semana_id, {col} AS old_v FROM produccion_plata WHERE id = %s",
                (prod_id,),
            )
            row = cur.fetchone()
            if not row:
                raise NotFoundError(
                    f"Línea de producción id={prod_id} no existe.",
                    details={"produccion_id": prod_id},
                )
            semana_id = int(row["semana_id"])
            old_v = row.get("old_v")
            audit.assert_semana_abierta(semana_id)
            cur.execute(
                f"UPDATE produccion_plata SET {col} = %s WHERE id = %s",
                (val, prod_id),
            )
        audit.registrar(
            produccion_id=prod_id,
            semana_id=semana_id,
            campo=col,
            valor_anterior=old_v,
            valor_nuevo=val,
            origen="app",
        )
        logger.info("Producción id=%s día %s = %s", prod_id, col, val)

    def totales_semana(self, semana_id: int) -> dict:
        sql = """
            SELECT
                COUNT(*) AS lineas,
                COALESCE(SUM(total_gramos), 0) AS total_gramos,
                COALESCE(SUM(efectivo), 0) AS total_efectivo
            FROM produccion_plata
            WHERE semana_id = %s
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (semana_id,))
            row = cur.fetchone()
        return row or {"lineas": 0, "total_gramos": Decimal("0"), "total_efectivo": Decimal("0")}




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
        sql = """
            SELECT s.id, s.codigo, s.fecha_inicio, s.fecha_fin,
                   COALESCE(r.nomina_plt, 0) AS nomina_plt,
                   COALESCE(r.nomina_pit, 0) AS nomina_pit,
                   COALESCE(r.nomina_tll, 0) AS nomina_tll,
                   COALESCE(r.total_semana, 0) AS total_semana
            FROM semanas s
            LEFT JOIN resumen_nominas r ON r.semana_id = s.id
            ORDER BY s.fecha_inicio DESC
            LIMIT %s
        """
        with self.db.cursor() as cur:
            cur.execute(sql, (limit,))
            return list(cur.fetchall())
