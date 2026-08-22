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


    def actualizar(self, trabajador_id: int, data: dict) -> dict:
        self.obtener(trabajador_id)
        fields = []
        params: list[Any] = []
        mapping = {
            "nombre_mostrar": "nombre_mostrar",
            "nombre_completo": "nombre_completo",
            "ubic": "ubic",
            "tipo": "tipo",
            "puesto": "puesto",
            "fecha_incorporacion": "fecha_incorporacion",
            "notas": "notas",
            "activo": "activo",
        }
        for key, col in mapping.items():
            if key in data and data[key] is not None:
                fields.append(f"{col} = %s")
                params.append(data[key])
        if not fields:
            return self.obtener(trabajador_id)
        # nombre_completo default if only nombre_mostrar
        if "nombre_mostrar" in data and "nombre_completo" not in data:
            fields.append("nombre_completo = %s")
            params.append(data["nombre_mostrar"])
        params.append(trabajador_id)
        sql = f"UPDATE trabajadores SET {', '.join(fields)} WHERE id = %s"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
        logger.info("Trabajador actualizado id=%s", trabajador_id)
        return self.obtener(trabajador_id)

    def activar(self, trabajador_id: int) -> None:
        self.obtener(trabajador_id)
        with self.db.cursor() as cur:
            cur.execute("UPDATE trabajadores SET activo = 1 WHERE id = %s", (trabajador_id,))
        logger.info("Trabajador reactivado id=%s", trabajador_id)

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


    def duplicar_trabajos_a_semana(self, semana_origen_id: int, semana_destino_id: int) -> dict:
        """
        Copia trabajos activos con línea de producción (folio/modelo/material) a otra semana.
        No copia gramos. Reutiliza trabajo_id existentes.
        """
        from app.services.audit_service import AuditService
        AuditService(self.db).assert_semana_abierta(semana_destino_id)
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT p.trabajador_id, p.trabajo_id, p.nombre, p.ubic, p.folio, p.modelo,
                       p.material, p.tarifa_gr
                FROM produccion_plata p
                WHERE p.semana_id = %s
                """,
                (semana_origen_id,),
            )
            origen = list(cur.fetchall() or [])
            # también trabajos activos sin línea esta semana
            cur.execute(
                """
                SELECT t.id AS trabajo_id, t.trabajador_id, tr.nombre_mostrar AS nombre, tr.ubic,
                       t.folio, t.modelo, t.material, t.tarifa_gr
                FROM trabajos t
                JOIN trabajadores tr ON tr.id = t.trabajador_id
                WHERE t.activo = 1 AND tr.activo = 1
                """
            )
            todos = list(cur.fetchall() or [])
        # prefer origen lines; supplement with active trabajos
        seen = set()
        to_insert = []
        for r in origen:
            key = (r.get("trabajador_id"), r.get("trabajo_id") or r.get("folio"), r.get("material"))
            if key in seen:
                continue
            seen.add(key)
            to_insert.append(r)
        for r in todos:
            key = (r.get("trabajador_id"), r.get("trabajo_id") or r.get("folio"), r.get("material"))
            if key in seen:
                continue
            seen.add(key)
            to_insert.append(r)
        created = 0
        skipped = 0
        for r in to_insert:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id FROM produccion_plata
                    WHERE semana_id=%s AND trabajador_id=%s
                      AND COALESCE(folio,'')=COALESCE(%s,'')
                      AND COALESCE(material,'')=COALESCE(%s,'')
                    LIMIT 1
                    """,
                    (semana_destino_id, r.get("trabajador_id"), r.get("folio"), r.get("material")),
                )
                if cur.fetchone():
                    skipped += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO produccion_plata
                      (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        semana_destino_id,
                        r.get("trabajador_id"),
                        r.get("trabajo_id"),
                        r.get("nombre"),
                        r.get("ubic"),
                        r.get("folio"),
                        r.get("modelo"),
                        r.get("material"),
                        r.get("tarifa_gr"),
                    ),
                )
                created += 1
        return {"created": created, "skipped": skipped, "total_candidates": len(to_insert)}


    def buscar_linea(
        self,
        semana_id: int,
        nombre: str,
        ubic: int,
        folio: str | None = None,
    ) -> dict | None:
        with self.db.cursor() as cur:
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
            return cur.fetchone()

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



    def actualizar_linea(self, prod_id: int, data: dict) -> None:
        """Actualiza metadatos y/o gramos de una línea Plata (popup fila completa)."""
        from app.services.audit_service import AuditService
        audit = AuditService(self.db)
        allowed = {
            "folio", "modelo", "material", "tarifa_gr", "firmado", "notas",
            "gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie",
        }
        fields = []
        params: list = []
        with self.db.cursor() as cur:
            cur.execute("SELECT semana_id FROM produccion_plata WHERE id=%s", (prod_id,))
            row = cur.fetchone()
            if not row:
                raise NotFoundError(
                    f"Línea de producción id={prod_id} no existe.",
                    details={"produccion_id": prod_id},
                )
            audit.assert_semana_abierta(int(row["semana_id"]))
            for k, v in data.items():
                if k not in allowed:
                    continue
                if k == "tarifa_gr":
                    try:
                        v = float(v) if v is not None and str(v).strip() != "" else None
                    except (TypeError, ValueError):
                        raise ValidationAppError("Tarifa inválida.", details={"tarifa_gr": v})
                elif k.startswith("gm_"):
                    try:
                        if v is None or str(v).strip() == "":
                            v = None
                        else:
                            f = float(v)
                            v = None if f == 0 else f
                    except (TypeError, ValueError):
                        raise ValidationAppError(f"Gramos inválidos en {k}.", details={k: v})
                elif k == "firmado":
                    v = 1 if v in (1, "1", True, "true", "on") else 0
                elif k in ("folio", "modelo", "material", "notas"):
                    v = (str(v).strip() if v is not None else "") or None
                fields.append(f"{k}=%s")
                params.append(v)
            if not fields:
                return
            params.append(prod_id)
            cur.execute(
                f"UPDATE produccion_plata SET {', '.join(fields)} WHERE id=%s",
                params,
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



class NominaTallerRepo(BaseRepo):
    """Nómina de taller: sueldo + extras por semana."""

    def listar_por_semana(self, semana_id: int) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, semana_id, trabajador_id, nombre, ubic, puesto,
                       sueldo, extras, total, firmado, notas
                FROM nomina_taller
                WHERE semana_id = %s
                ORDER BY ubic, nombre
                """,
                (semana_id,),
            )
            return list(cur.fetchall() or [])

    def totales(self, semana_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS lineas,
                       COALESCE(SUM(sueldo),0) AS sum_sueldo,
                       COALESCE(SUM(extras),0) AS sum_extras,
                       COALESCE(SUM(total),0) AS total
                FROM nomina_taller WHERE semana_id = %s
                """,
                (semana_id,),
            )
            return cur.fetchone() or {}

    def insertar(self, semana_id: int, data: dict) -> int:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nomina_taller
                  (semana_id, trabajador_id, nombre, ubic, puesto, sueldo, extras, firmado, notas)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    semana_id,
                    data.get("trabajador_id"),
                    data["nombre"],
                    data["ubic"],
                    data.get("puesto"),
                    float(data.get("sueldo") or 0),
                    float(data.get("extras") or 0),
                    1 if data.get("firmado") else 0,
                    data.get("notas"),
                ),
            )
            return cur.lastrowid

    def actualizar(self, row_id: int, data: dict) -> None:
        fields = []
        params: list = []
        for k in ("nombre", "ubic", "puesto", "sueldo", "extras", "firmado", "notas", "trabajador_id"):
            if k in data:
                fields.append(f"{k}=%s")
                params.append(data[k])
        if not fields:
            return
        params.append(row_id)
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE nomina_taller SET {', '.join(fields)} WHERE id=%s", params)

    def eliminar(self, row_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM nomina_taller WHERE id=%s", (row_id,))


class ProduccionPitaRepo(BaseRepo):
    """Nómina Pita: modelo/folio/material PITA NxN + efectivo."""

    def listar_por_semana(self, semana_id: int) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, semana_id, trabajador_id, nombre, ubic, modelo, folio,
                       material, producto, pitas, efectivo, firmado, notas
                FROM produccion_pita
                WHERE semana_id = %s
                ORDER BY ubic, nombre
                """,
                (semana_id,),
            )
            return list(cur.fetchall() or [])

    def totales(self, semana_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS lineas,
                       COALESCE(SUM(pitas),0) AS sum_pitas,
                       COALESCE(SUM(efectivo),0) AS total
                FROM produccion_pita WHERE semana_id = %s
                """,
                (semana_id,),
            )
            return cur.fetchone() or {}

    def insertar(self, semana_id: int, data: dict) -> int:
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO produccion_pita
                  (semana_id, trabajador_id, nombre, ubic, modelo, folio, material,
                   producto, pitas, efectivo, firmado, notas)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    semana_id,
                    data.get("trabajador_id"),
                    data["nombre"],
                    data["ubic"],
                    data.get("modelo"),
                    data.get("folio"),
                    data.get("material"),
                    data.get("producto") or "Cinturón",
                    data.get("pitas"),
                    float(data.get("efectivo") or 0),
                    1 if data.get("firmado") else 0,
                    data.get("notas"),
                ),
            )
            return cur.lastrowid

    def actualizar(self, row_id: int, data: dict) -> None:
        fields = []
        params: list = []
        for k in (
            "nombre", "ubic", "modelo", "folio", "material", "producto",
            "pitas", "efectivo", "firmado", "notas", "trabajador_id",
        ):
            if k in data:
                fields.append(f"{k}=%s")
                params.append(data[k])
        if not fields:
            return
        params.append(row_id)
        with self.db.cursor() as cur:
            cur.execute(f"UPDATE produccion_pita SET {', '.join(fields)} WHERE id=%s", params)

    def eliminar(self, row_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM produccion_pita WHERE id=%s", (row_id,))
