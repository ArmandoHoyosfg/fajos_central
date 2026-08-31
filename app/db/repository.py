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
                   sueldo_modo, sueldo_base, activo, fecha_incorporacion, notas, codigo_qr
            FROM trabajadores
            WHERE 1=1
        """
        sql_legacy = """
            SELECT id, nombre_mostrar, nombre_completo, ubic, tipo, puesto,
                   activo, fecha_incorporacion, notas
            FROM trabajadores
            WHERE 1=1
        """
        params: list[Any] = []
        if solo_activos:
            sql += " AND activo = 1"
            sql_legacy += " AND activo = 1"
        if solo_plt:
            sql += " AND (tipo IN ('PLT','PLT/PIT','Mixto'))"
            sql_legacy += " AND (tipo IN ('PLT','PLT/PIT','Mixto'))"
        if busqueda:
            like_clause = " AND (nombre_mostrar LIKE %s OR nombre_completo LIKE %s OR CAST(ubic AS CHAR) LIKE %s)"
            sql += like_clause
            sql_legacy += like_clause
            like = f"%{busqueda}%"
            params.extend([like, like, like])
        sql += " ORDER BY nombre_mostrar, ubic"
        sql_legacy += " ORDER BY nombre_mostrar, ubic"
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = list(cur.fetchall())
            except Exception as e:
                logger.warning("listar trabajadores: columnas 3.17 ausentes (%s); usa SQL legado", e)
                cur.execute(sql_legacy, params)
                rows = list(cur.fetchall())
                for r in rows:
                    r.setdefault("sueldo_modo", "variable")
                    r.setdefault("sueldo_base", None)
                    r.setdefault("codigo_qr", None)
            return rows

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
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, sueldo_modo, sueldo_base,
                 activo, fecha_incorporacion, notas, codigo_qr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s)
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
                        (str(data.get("sueldo_modo") or "variable").lower()
                         if str(data.get("sueldo_modo") or "variable").lower() in ("fijo", "variable")
                         else "variable"),
                        (float(data["sueldo_base"])
                         if data.get("sueldo_base") not in (None, "")
                         else None),
                        data.get("fecha_incorporacion"),
                        data.get("notas"),
                        data.get("codigo_qr"),
                    ),
                )
                new_id = cur.lastrowid
            logger.info("Trabajador creado id=%s nombre=%s", new_id, data["nombre_mostrar"])
            try:
                with self.db.cursor() as cur2:
                    cur2.execute(
                        "UPDATE trabajadores SET codigo_qr = CONCAT('FC', LPAD(id, 6, '0')) "
                        "WHERE id = %s AND (codigo_qr IS NULL OR codigo_qr = '')",
                        (new_id,),
                    )
            except Exception:
                pass
            return new_id
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError("No se pudo agregar el trabajador.", cause=e) from e


    def actualizar(self, trabajador_id: int, data: dict) -> dict:
        """Actualiza catálogo y propaga nombre/ubic/puesto a nóminas denormalizadas."""
        antes = self.obtener(trabajador_id)
        fields = []
        params: list[Any] = []
        mapping = {
            "nombre_mostrar": "nombre_mostrar",
            "nombre_completo": "nombre_completo",
            "ubic": "ubic",
            "tipo": "tipo",
            "puesto": "puesto",
            "sueldo_modo": "sueldo_modo",
            "sueldo_base": "sueldo_base",
            "fecha_incorporacion": "fecha_incorporacion",
            "notas": "notas",
            "activo": "activo",
            "codigo_qr": "codigo_qr",
        }
        for key, col in mapping.items():
            if key not in data:
                continue
            # permitir None en sueldo_base / notas / puesto / fecha
            if data[key] is None and key not in (
                "sueldo_base", "notas", "puesto", "fecha_incorporacion", "nombre_completo"
            ):
                continue
            fields.append(f"{col} = %s")
            params.append(data[key])
        if not fields:
            return self.obtener(trabajador_id)
        if "nombre_mostrar" in data and "nombre_completo" not in data:
            fields.append("nombre_completo = %s")
            params.append(data["nombre_mostrar"])
        params.append(trabajador_id)
        sql = f"UPDATE trabajadores SET {', '.join(fields)} WHERE id = %s"
        with self.db.cursor() as cur:
            cur.execute(sql, params)
        logger.info("Trabajador actualizado id=%s", trabajador_id)
        # Propagar a Plata / Pita / Taller (copias denormalizadas)
        try:
            sync = self.sincronizar_denormalizados(
                trabajador_id,
                nombre_ant=antes.get("nombre_mostrar"),
                ubic_ant=antes.get("ubic"),
            )
            logger.info("Sync denormalizado id=%s %s", trabajador_id, sync)
        except Exception:
            logger.exception("No se pudo sincronizar denormalizados id=%s", trabajador_id)
        return self.obtener(trabajador_id)

    def sincronizar_denormalizados(
        self,
        trabajador_id: int,
        *,
        nombre_ant: str | None = None,
        ubic_ant: int | None = None,
    ) -> dict:
        """
        Copia nombre_mostrar/ubic del catálogo a Plata, Pita y Taller.
        Actualiza por trabajador_id y también por nombre exacto (mismo trabajador).
        """
        t = self.obtener(trabajador_id)
        nombre = t.get("nombre_mostrar")
        ubic = t.get("ubic")
        puesto = t.get("puesto")
        counts = {"plata": 0, "pita": 0, "taller": 0, "orphans": 0, "by_name": 0}
        with self.db.cursor() as cur:
            # --- Plata por id ---
            cur.execute(
                """
                UPDATE produccion_plata
                   SET nombre = %s, ubic = %s
                 WHERE trabajador_id = %s
                   AND (nombre <> %s OR ubic <> %s OR nombre IS NULL OR ubic IS NULL)
                """,
                (nombre, ubic, trabajador_id, nombre, ubic),
            )
            counts["plata"] = max(0, cur.rowcount or 0)

            # --- Plata por nombre exacto (corrige filas con id incorrecto o desfasado) ---
            # Solo si el nombre_mostrar es único en catálogo
            cur.execute(
                "SELECT COUNT(*) AS n FROM trabajadores WHERE nombre_mostrar = %s AND activo = 1",
                (nombre,),
            )
            n_name = int((cur.fetchone() or {}).get("n") or 0)
            if n_name == 1 and nombre:
                cur.execute(
                    """
                    UPDATE produccion_plata
                       SET nombre = %s, ubic = %s, trabajador_id = %s
                     WHERE nombre = %s
                       AND (trabajador_id IS NULL OR trabajador_id = 0 OR trabajador_id = %s
                            OR ubic <> %s)
                    """,
                    (nombre, ubic, trabajador_id, nombre, trabajador_id, ubic),
                )
                counts["by_name"] += max(0, cur.rowcount or 0)

            # --- Pita ---
            cur.execute(
                """
                UPDATE produccion_pita
                   SET nombre = %s, ubic = %s
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, trabajador_id),
            )
            counts["pita"] = max(0, cur.rowcount or 0)
            if n_name == 1 and nombre:
                cur.execute(
                    """
                    UPDATE produccion_pita
                       SET nombre = %s, ubic = %s, trabajador_id = %s
                     WHERE nombre = %s
                       AND (trabajador_id IS NULL OR trabajador_id = 0 OR trabajador_id = %s
                            OR ubic <> %s)
                    """,
                    (nombre, ubic, trabajador_id, nombre, trabajador_id, ubic),
                )
                counts["by_name"] += max(0, cur.rowcount or 0)

            # --- Taller ---
            cur.execute(
                """
                UPDATE nomina_taller
                   SET nombre = %s, ubic = %s, puesto = COALESCE(%s, puesto)
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, puesto, trabajador_id),
            )
            counts["taller"] = max(0, cur.rowcount or 0)

            # --- Huérfanas con nombre+ubic anteriores ---
            if nombre_ant is not None and ubic_ant is not None:
                for table, extra in (
                    ("produccion_plata", ""),
                    ("produccion_pita", ""),
                    ("nomina_taller", ", puesto = COALESCE(%s, puesto)"),
                ):
                    if table == "nomina_taller":
                        cur.execute(
                            f"""
                            UPDATE {table}
                               SET nombre = %s, ubic = %s, trabajador_id = %s
                                   {extra}
                             WHERE nombre = %s AND ubic = %s
                               AND (trabajador_id IS NULL OR trabajador_id = 0 OR trabajador_id = %s)
                            """,
                            (nombre, ubic, trabajador_id, puesto, nombre_ant, ubic_ant, trabajador_id),
                        )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {table}
                               SET nombre = %s, ubic = %s, trabajador_id = %s
                             WHERE nombre = %s AND ubic = %s
                               AND (trabajador_id IS NULL OR trabajador_id = 0 OR trabajador_id = %s)
                            """,
                            (nombre, ubic, trabajador_id, nombre_ant, ubic_ant, trabajador_id),
                        )
                    counts["orphans"] += max(0, cur.rowcount or 0)

            # Forzar commit si el driver no autocommitea en este cursor
            try:
                self.db.connect().commit()
            except Exception:
                pass

        return counts


    def diagnostico_sync(self) -> dict:
        """Desajustes catálogo vs nóminas + muestra Vela + tipos de columna."""
        mismatches: list[dict] = []
        sample_vela: list[dict] = []
        columns: list[dict] = []
        with self.db.cursor() as cur:
            for area, table in (
                ("plata", "produccion_plata"),
                ("pita", "produccion_pita"),
                ("taller", "nomina_taller"),
            ):
                try:
                    cur.execute(
                        f"""
                        SELECT p.id AS prod_id, p.trabajador_id, p.nombre AS nombre_fila, p.ubic AS ubic_fila,
                               tr.nombre_mostrar AS cat_nombre, tr.ubic AS cat_ubic
                        FROM {table} p
                        LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
                        WHERE tr.id IS NOT NULL
                          AND (p.nombre <> tr.nombre_mostrar OR p.ubic <> tr.ubic)
                        LIMIT 100
                        """
                    )
                    for r in cur.fetchall() or []:
                        r = dict(r)
                        r["area"] = area
                        mismatches.append(r)
                except Exception as e:
                    mismatches.append({"area": area, "prod_id": "?", "nombre_fila": str(e)})

            try:
                cur.execute(
                    """
                    SELECT id, nombre_mostrar AS nombre, ubic, tipo AS extra, id AS trabajador_id
                    FROM trabajadores
                    WHERE nombre_mostrar LIKE %s OR nombre_completo LIKE %s
                    LIMIT 20
                    """,
                    ("%Vela%", "%Vela%"),
                )
                for r in cur.fetchall() or []:
                    sample_vela.append({**dict(r), "src": "trabajadores"})
            except Exception:
                pass
            try:
                cur.execute(
                    """
                    SELECT id, nombre, ubic, trabajador_id, folio AS extra
                    FROM produccion_plata
                    WHERE nombre LIKE %s
                    LIMIT 30
                    """,
                    ("%Vela%",),
                )
                for r in cur.fetchall() or []:
                    sample_vela.append({**dict(r), "src": "produccion_plata"})
            except Exception:
                pass
            try:
                cur.execute(
                    """
                    SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, DATA_TYPE, IS_NULLABLE, COLUMN_KEY
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME IN (
                        'trabajadores','produccion_plata','produccion_pita','nomina_taller',
                        'trabajos','semanas'
                      )
                    ORDER BY TABLE_NAME, ORDINAL_POSITION
                    """
                )
                columns = [dict(r) for r in (cur.fetchall() or [])]
            except Exception:
                columns = []
        counts = {"trabajadores": 0, "plata": 0, "semanas": 0}
        try:
            with self.db.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM trabajadores")
                counts["trabajadores"] = int((cur.fetchone() or {}).get("n") or 0)
                cur.execute("SELECT COUNT(*) AS n FROM produccion_plata")
                counts["plata"] = int((cur.fetchone() or {}).get("n") or 0)
                cur.execute("SELECT COUNT(*) AS n FROM semanas")
                counts["semanas"] = int((cur.fetchone() or {}).get("n") or 0)
        except Exception:
            pass

        orphans = self.listar_huerfanos()
        migrations = self.migraciones_pendientes()
        folios_dup = self.folios_duplicados()
        semana_info = self.semana_actual_info()

        return {
            "mismatches": mismatches,
            "sample_vela": sample_vela,
            "columns": columns,
            "n_mismatches": len(mismatches),
            "counts": counts,
            "orphans": orphans,
            "n_orphans": len(orphans),
            "migrations": migrations,
            "folios_duplicados": folios_dup,
            "n_folios_dup": len(folios_dup),
            "semana_actual": semana_info,
        }

    def listar_huerfanos(self) -> list[dict]:
        """Filas sin trabajador_id válido o con id inexistente."""
        out: list[dict] = []
        with self.db.cursor() as cur:
            for area, table in (
                ("plata", "produccion_plata"),
                ("pita", "produccion_pita"),
                ("taller", "nomina_taller"),
            ):
                try:
                    cur.execute(
                        f"""
                        SELECT p.id AS prod_id, p.nombre, p.ubic, p.trabajador_id,
                               tr.id AS cat_id
                        FROM {table} p
                        LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
                        WHERE p.trabajador_id IS NULL OR p.trabajador_id = 0 OR tr.id IS NULL
                        LIMIT 200
                        """
                    )
                    for r in cur.fetchall() or []:
                        row = dict(r)
                        row["area"] = area
                        out.append(row)
                except Exception as e:
                    out.append({"area": area, "prod_id": "?", "nombre": str(e)})
        return out

    def reparar_huerfanos(self) -> dict:
        """
        Enlaza filas huérfanas a trabajadores por nombre_mostrar + ubic exactos.
        No inventa trabajadores nuevos.
        """
        linked = {"plata": 0, "pita": 0, "taller": 0, "sin_match": 0}
        with self.db.cursor() as cur:
            for area, table in (
                ("plata", "produccion_plata"),
                ("pita", "produccion_pita"),
                ("taller", "nomina_taller"),
            ):
                try:
                    cur.execute(
                        f"""
                        SELECT p.id, p.nombre, p.ubic
                        FROM {table} p
                        LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
                        WHERE p.trabajador_id IS NULL OR p.trabajador_id = 0 OR tr.id IS NULL
                        """
                    )
                    rows = list(cur.fetchall() or [])
                except Exception:
                    continue
                for r in rows:
                    cur.execute(
                        """
                        SELECT id FROM trabajadores
                        WHERE nombre_mostrar = %s AND ubic = %s
                        LIMIT 1
                        """,
                        (r.get("nombre"), r.get("ubic")),
                    )
                    hit = cur.fetchone()
                    if not hit:
                        linked["sin_match"] += 1
                        continue
                    tid = int(hit["id"])
                    cur.execute(
                        f"UPDATE {table} SET trabajador_id = %s WHERE id = %s",
                        (tid, r["id"]),
                    )
                    linked[area] += max(0, cur.rowcount or 0)
            try:
                self.db.connect().commit()
            except Exception:
                pass
        return linked

    def migraciones_pendientes(self) -> list[dict]:
        """Columnas esperadas por versión vs information_schema."""
        expected = [
            ("trabajadores", "sueldo_modo", "003_taller_fijo_folio_qr.sql"),
            ("trabajadores", "sueldo_base", "003_taller_fijo_folio_qr.sql"),
            ("trabajadores", "codigo_qr", "003_taller_fijo_folio_qr.sql"),
            ("trabajos", "terminado_en", "003_taller_fijo_folio_qr.sql"),
        ]
        missing = []
        with self.db.cursor() as cur:
            for table, col, script in expected:
                try:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS n FROM information_schema.COLUMNS
                        WHERE TABLE_SCHEMA = DATABASE()
                          AND TABLE_NAME = %s AND COLUMN_NAME = %s
                        """,
                        (table, col),
                    )
                    n = int((cur.fetchone() or {}).get("n") or 0)
                    if n == 0:
                        missing.append({
                            "table": table,
                            "column": col,
                            "script": script,
                            "status": "faltante",
                        })
                    else:
                        missing.append({
                            "table": table,
                            "column": col,
                            "script": script,
                            "status": "ok",
                        })
                except Exception as e:
                    missing.append({
                        "table": table,
                        "column": col,
                        "script": script,
                        "status": f"error: {e}",
                    })
        return missing

    def folios_duplicados(self, semana_id: int | None = None) -> list[dict]:
        """
        Folios no vacíos usados por más de un trabajador_id distinto
        (misma semana si se indica; si no, global).
        """
        out: list[dict] = []
        sql = """
            SELECT p.folio, p.semana_id, s.codigo AS semana_codigo,
                   COUNT(DISTINCT p.trabajador_id) AS n_trabajadores,
                   GROUP_CONCAT(DISTINCT CONCAT(p.nombre, ' [', p.ubic, ']')
                                ORDER BY p.nombre SEPARATOR ' | ') AS quienes,
                   GROUP_CONCAT(DISTINCT p.trabajador_id) AS ids
            FROM produccion_plata p
            LEFT JOIN semanas s ON s.id = p.semana_id
            WHERE p.folio IS NOT NULL AND TRIM(p.folio) <> ''
        """
        params: list = []
        if semana_id:
            sql += " AND p.semana_id = %s"
            params.append(semana_id)
        sql += """
            GROUP BY p.folio, p.semana_id, s.codigo
            HAVING COUNT(DISTINCT p.trabajador_id) > 1
            ORDER BY p.semana_id DESC, p.folio
            LIMIT 100
        """
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, params)
                out = [dict(r) for r in (cur.fetchall() or [])]
            except Exception:
                out = []
        return out

    def semana_actual_info(self) -> dict:
        """Rango sáb–vie de hoy y si existe semana en BD."""
        from app.core.calendar_util import sugerir_codigo_semana, today
        codigo, sab, vie = sugerir_codigo_semana()
        info = {
            "hoy": today().isoformat(),
            "codigo": codigo,
            "fecha_inicio": sab.isoformat(),
            "fecha_fin": vie.isoformat(),
            "existe": False,
            "semana_id": None,
            "cerrada": None,
        }
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, codigo, fecha_inicio, fecha_fin, cerrada
                    FROM semanas
                    WHERE fecha_inicio = %s AND fecha_fin = %s
                    LIMIT 1
                    """,
                    (sab.isoformat(), vie.isoformat()),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT id, codigo, fecha_inicio, fecha_fin, cerrada
                        FROM semanas
                        WHERE codigo = %s AND anio = %s
                        LIMIT 1
                        """,
                        (codigo, sab.year),
                    )
                    row = cur.fetchone()
                if row:
                    info["existe"] = True
                    info["semana_id"] = int(row["id"])
                    info["cerrada"] = bool(row.get("cerrada"))
                    info["codigo_bd"] = row.get("codigo")
        except Exception as e:
            info["error"] = str(e)
        return info

    def sincronizar_todos_denormalizados(self) -> dict:
        """Repara todas las líneas ligadas a un trabajador_id válido."""
        total = {"plata": 0, "pita": 0, "taller": 0, "trabajadores": 0}
        with self.db.cursor() as cur:
            cur.execute("SELECT id FROM trabajadores")
            ids = [int(r["id"]) for r in (cur.fetchall() or [])]
        for tid in ids:
            try:
                c = self.sincronizar_denormalizados(tid)
                total["plata"] += c.get("plata", 0)
                total["pita"] += c.get("pita", 0)
                total["taller"] += c.get("taller", 0)
                total["trabajadores"] += 1
            except Exception:
                logger.exception("sync all id=%s", tid)
        return total

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


class ProduccionRepo(BaseRepo):
    def obtener(self, prod_id: int) -> dict | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM produccion_plata WHERE id = %s", (prod_id,))
            return cur.fetchone()

    def listar_por_semana(self, semana_id: int, *, incluir_terminados: bool = False) -> list[dict]:
        """Lista producción; por defecto oculta folios marcados terminados (trabajo inactivo)."""
        sql = """
            SELECT p.id, p.semana_id, p.trabajador_id, p.trabajo_id,
                   COALESCE(tr.nombre_mostrar, p.nombre) AS nombre,
                   COALESCE(tr.ubic, p.ubic) AS ubic,
                   p.folio, p.modelo, p.material, p.tarifa_gr,
                   p.gm_sab, p.gm_dom, p.gm_lun, p.gm_mar, p.gm_mie, p.gm_jue, p.gm_vie,
                   p.total_gramos, p.efectivo, p.firmado, p.notas,
                   p.nombre AS nombre_guardado, p.ubic AS ubic_guardada,
                   tr.nombre_mostrar AS cat_nombre, tr.ubic AS cat_ubic,
                   COALESCE(tj.activo, 1) AS trabajo_activo,
                   tj.terminado_en
            FROM produccion_plata p
            LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
            LEFT JOIN trabajos tj ON tj.id = p.trabajo_id
            WHERE p.semana_id = %s
        """
        if not incluir_terminados:
            sql += """
              AND (p.trabajo_id IS NULL OR tj.id IS NULL OR COALESCE(tj.activo, 1) = 1)
              AND (p.notas IS NULL OR p.notas NOT LIKE %s)
            """
            params: tuple = (semana_id, "%[terminado]%")
        else:
            params = (semana_id,)
        sql += """
            ORDER BY COALESCE(tr.nombre_mostrar, p.nombre), COALESCE(tr.ubic, p.ubic), p.id
        """
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, params)
                return list(cur.fetchall() or [])
            except Exception:
                # Fallback sin join trabajos / sin filtro
                cur.execute(
                    """
                    SELECT id, semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo,
                           material, tarifa_gr,
                           gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie,
                           total_gramos, efectivo, firmado, notas
                    FROM produccion_plata
                    WHERE semana_id = %s
                    ORDER BY nombre, ubic, id
                    """,
                    (semana_id,),
                )
                rows = list(cur.fetchall() or [])
                if not incluir_terminados:
                    rows = [
                        r for r in rows
                        if "[terminado]" not in str(r.get("notas") or "")
                    ]
                return rows

    def listar_terminados_semana(self, semana_id: int) -> list[dict]:
        """Líneas de la semana ligadas a trabajo terminado o marcadas [terminado]."""
        sql = """
            SELECT p.id, p.semana_id, p.trabajador_id, p.trabajo_id,
                   COALESCE(tr.nombre_mostrar, p.nombre) AS nombre,
                   COALESCE(tr.ubic, p.ubic) AS ubic,
                   p.folio, p.modelo, p.material, p.total_gramos, p.efectivo, p.notas,
                   COALESCE(tj.activo, 1) AS trabajo_activo,
                   tj.terminado_en
            FROM produccion_plata p
            LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
            LEFT JOIN trabajos tj ON tj.id = p.trabajo_id
            WHERE p.semana_id = %s
              AND (
                    (p.trabajo_id IS NOT NULL AND COALESCE(tj.activo, 1) = 0)
                 OR (p.notas IS NOT NULL AND p.notas LIKE %s)
              )
            ORDER BY COALESCE(tr.nombre_mostrar, p.nombre), p.id
        """
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, (semana_id, "%[terminado]%"))
                return list(cur.fetchall() or [])
            except Exception:
                return []

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
        # Solo líneas de la semana origen (evita re-duplicar el catálogo completo).
        # Si el destino está vacío y no había líneas en origen, se complementa con trabajos activos.
        seen = set()
        to_insert = []
        for r in origen:
            key = (
                r.get("trabajador_id"),
                str(r.get("trabajo_id") or ""),
                str(r.get("folio") or ""),
                str(r.get("material") or ""),
                str(r.get("nombre") or "").lower(),
                int(r.get("ubic") or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            to_insert.append(r)
        dest_count = 0
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM produccion_plata WHERE semana_id=%s",
                (semana_destino_id,),
            )
            dest_count = int((cur.fetchone() or {}).get("n") or 0)
        if not to_insert and dest_count == 0:
            for r in todos:
                key = (
                    r.get("trabajador_id"),
                    str(r.get("trabajo_id") or ""),
                    str(r.get("folio") or ""),
                    str(r.get("material") or ""),
                    str(r.get("nombre") or "").lower(),
                    int(r.get("ubic") or 0),
                )
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
                    WHERE semana_id=%s
                      AND (
                        (trabajador_id IS NOT NULL AND trabajador_id=%s)
                        OR (nombre=%s AND ubic=%s)
                      )
                      AND COALESCE(folio,'')=COALESCE(%s,'')
                      AND COALESCE(material,'')=COALESCE(%s,'')
                      AND COALESCE(modelo,'')=COALESCE(%s,'')
                    LIMIT 1
                    """,
                    (
                        semana_destino_id,
                        r.get("trabajador_id"),
                        r.get("nombre"),
                        r.get("ubic"),
                        r.get("folio"),
                        r.get("material"),
                        r.get("modelo"),
                    ),
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
        material: str | None = None,
        trabajador_id: int | None = None,
        *,
        prefer_visibles: bool = True,
    ) -> dict | None:
        """
        Busca línea de la semana. Prefiere filas visibles (no [terminado], trabajo activo).
        Orden de match: trabajador_id+folio(+material) > nombre+ubic+folio(+material).
        """
        folio_n = (folio or "").strip() or None
        mat_n = (material or "").strip() or None
        with self.db.cursor() as cur:
            clauses = ["p.semana_id = %s"]
            params: list = [semana_id]
            if trabajador_id:
                clauses.append("p.trabajador_id = %s")
                params.append(int(trabajador_id))
            else:
                clauses.append("p.nombre = %s")
                params.append(nombre)
                clauses.append("p.ubic = %s")
                params.append(int(ubic))
            if folio_n:
                clauses.append("p.folio = %s")
                params.append(folio_n)
            else:
                clauses.append("(p.folio IS NULL OR TRIM(p.folio) = '')")
            if mat_n:
                clauses.append("UPPER(TRIM(COALESCE(p.material,''))) = %s")
                params.append(mat_n.upper())
            sql = f"""
                SELECT p.*,
                       COALESCE(tj.activo, 1) AS trabajo_activo,
                       CASE
                         WHEN p.notas IS NOT NULL AND p.notas LIKE '%[terminado]%' THEN 1
                         ELSE 0
                       END AS es_terminado
                FROM produccion_plata p
                LEFT JOIN trabajos tj ON tj.id = p.trabajo_id
                WHERE {' AND '.join(clauses)}
                ORDER BY
                  CASE WHEN p.notas IS NOT NULL AND p.notas LIKE '%[terminado]%' THEN 1 ELSE 0 END ASC,
                  CASE WHEN COALESCE(tj.activo, 1) = 1 THEN 0 ELSE 1 END ASC,
                  p.id DESC
                LIMIT 5
            """
            cur.execute(sql, params)
            rows = list(cur.fetchall() or [])
        if not rows:
            return None
        if prefer_visibles:
            for r in rows:
                term = bool(r.get("es_terminado"))
                act = int(r.get("trabajo_activo") if r.get("trabajo_activo") is not None else 1)
                if not term and act == 1:
                    return r
            # si solo hay terminadas, devolver la más reciente para poder reabrirla
        return rows[0]

    def reabrir_linea_si_terminada(self, prod_id: int) -> None:
        """Quita marca [terminado] de notas y reactiva trabajo ligado."""
        with self.db.cursor() as cur:
            cur.execute("SELECT trabajo_id, notas FROM produccion_plata WHERE id=%s", (prod_id,))
            row = cur.fetchone()
            if not row:
                return
            notas = row.get("notas") or ""
            if "[terminado]" in notas:
                nueva = " ".join(
                    ln for ln in notas.replace("[terminado]", " ").split() if ln
                ).strip() or None
                cur.execute(
                    "UPDATE produccion_plata SET notas=%s WHERE id=%s",
                    (nueva, prod_id),
                )
            tid = row.get("trabajo_id")
            if tid:
                try:
                    cur.execute(
                        "UPDATE trabajos SET activo=1, terminado_en=NULL WHERE id=%s",
                        (int(tid),),
                    )
                except Exception:
                    pass

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
        """Actualiza un solo día de una línea existente (None o 0 = vacío). Gramos a 1 decimal."""
        from app.services.audit_service import AuditService
        if gramos is not None:
            try:
                gramos = round(float(gramos), 1)
            except (TypeError, ValueError):
                gramos = None
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



class NominaTallerRepo(BaseRepo):
    """Nómina de taller: sueldo + extras. Torcedores: pago = pitas × precio_pita (defecto 3.2)."""

    PRECIO_PITA_DEFAULT = 3.2

    @staticmethod
    def es_torcedor(puesto: str | None) -> bool:
        p = (puesto or "").strip().lower()
        return "torcedor" in p

    def listar_por_semana(self, semana_id: int, **_kwargs) -> list[dict]:
        with self.db.cursor() as cur:
            rows = []
            try:
                cur.execute(
                    """
                    SELECT n.id, n.semana_id, n.trabajador_id,
                           COALESCE(tr.nombre_mostrar, n.nombre) AS nombre,
                           COALESCE(tr.ubic, n.ubic) AS ubic,
                           COALESCE(tr.puesto, n.puesto) AS puesto,
                           n.sueldo, n.extras, n.total, n.firmado, n.notas,
                           n.pitas, n.precio_pita,
                           COALESCE(tr.sueldo_modo, 'variable') AS sueldo_modo,
                           tr.sueldo_base
                    FROM nomina_taller n
                    LEFT JOIN trabajadores tr ON (
                        (n.trabajador_id IS NOT NULL AND tr.id = n.trabajador_id)
                        OR (
                            (n.trabajador_id IS NULL OR n.trabajador_id = 0)
                            AND tr.nombre_mostrar = n.nombre
                            AND tr.ubic = n.ubic
                        )
                    )
                    WHERE n.semana_id = %s
                    ORDER BY
                      CASE WHEN LOWER(COALESCE(tr.puesto, n.puesto, '')) LIKE '%%torcedor%%' THEN 1 ELSE 0 END,
                      COALESCE(tr.ubic, n.ubic),
                      COALESCE(tr.nombre_mostrar, n.nombre)
                    """,
                    (semana_id,),
                )
                rows = list(cur.fetchall() or [])
            except Exception:
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
                rows = list(cur.fetchall() or [])
            return self._enriquecer_taller_lineas(rows)


    def _enriquecer_taller_lineas(self, rows: list[dict]) -> list[dict]:
        """
        Asegura sueldo_modo/sueldo_base desde el catálogo.
        Si falta trabajador_id, intenta enlazar por nombre + ubic y lo guarda.
        """
        if not rows:
            return rows
        # índice de trabajadores
        by_id: dict[int, dict] = {}
        by_key: dict[tuple, dict] = {}
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, nombre_mostrar, ubic, puesto, sueldo_modo, sueldo_base, tipo, activo
                    FROM trabajadores
                    """
                )
                for t in cur.fetchall() or []:
                    by_id[int(t["id"])] = t
                    k = (
                        str(t.get("nombre_mostrar") or "").strip().lower(),
                        int(t.get("ubic") or 0),
                    )
                    by_key[k] = t
        except Exception:
            pass

        for r in rows:
            tid = r.get("trabajador_id")
            t = by_id.get(int(tid)) if tid is not None else None
            if t is None:
                k = (
                    str(r.get("nombre") or "").strip().lower(),
                    int(r.get("ubic") or 0),
                )
                t = by_key.get(k)
                if t is not None:
                    r["trabajador_id"] = int(t["id"])
                    # backfill silencioso
                    try:
                        with self.db.cursor() as cur:
                            cur.execute(
                                "UPDATE nomina_taller SET trabajador_id=%s WHERE id=%s AND (trabajador_id IS NULL OR trabajador_id=0)",
                                (int(t["id"]), int(r["id"])),
                            )
                    except Exception:
                        pass
            if t is not None:
                modo = str(t.get("sueldo_modo") or "variable").strip().lower()
                r["sueldo_modo"] = "fijo" if modo == "fijo" else "variable"
                r["sueldo_base"] = t.get("sueldo_base")
                if not r.get("puesto") and t.get("puesto"):
                    r["puesto"] = t.get("puesto")
            else:
                modo = str(r.get("sueldo_modo") or "variable").strip().lower()
                r["sueldo_modo"] = "fijo" if modo == "fijo" else "variable"
                r.setdefault("sueldo_base", None)
            r.setdefault("pitas", None)
            r.setdefault("precio_pita", self.PRECIO_PITA_DEFAULT)
            r["es_torcedor"] = self.es_torcedor(r.get("puesto"))
            # Si es fijo y la línea tiene sueldo 0 pero hay base, sugerir base en UI (no forzar overwrite)
            try:
                if r["sueldo_modo"] == "fijo" and float(r.get("sueldo") or 0) == 0 and r.get("sueldo_base") is not None:
                    r["sueldo_sugerido"] = float(r["sueldo_base"])
            except (TypeError, ValueError):
                pass
        return rows

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

    def _calc_torcedor(self, data: dict) -> dict:
        """Si es torcedor y hay pitas, fija sueldo = pitas × precio."""
        puesto = data.get("puesto")
        if not self.es_torcedor(str(puesto) if puesto is not None else None):
            return data
        if "pitas" not in data and data.get("pitas") is None:
            return data
        try:
            pitas = float(data.get("pitas") or 0)
        except (TypeError, ValueError):
            return data
        precio = data.get("precio_pita")
        try:
            precio = float(precio) if precio is not None else self.PRECIO_PITA_DEFAULT
        except (TypeError, ValueError):
            precio = self.PRECIO_PITA_DEFAULT
        data = dict(data)
        data["precio_pita"] = precio
        data["sueldo"] = round(pitas * precio, 2)
        return data

    def _resolve_trabajador_id(self, data: dict) -> dict:
        if data.get("trabajador_id"):
            return data
        nombre = str(data.get("nombre") or "").strip()
        ubic = data.get("ubic")
        if not nombre or ubic is None:
            return data
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT id, sueldo_modo, sueldo_base, puesto FROM trabajadores WHERE nombre_mostrar=%s AND ubic=%s LIMIT 1",
                    (nombre, int(ubic)),
                )
                t = cur.fetchone()
                if t:
                    data = dict(data)
                    data["trabajador_id"] = int(t["id"])
                    if not data.get("puesto") and t.get("puesto"):
                        data["puesto"] = t.get("puesto")
                    if data.get("sueldo") in (None, "", 0, 0.0) and str(t.get("sueldo_modo") or "").lower() == "fijo" and t.get("sueldo_base") is not None:
                        data["sueldo"] = float(t["sueldo_base"])
        except Exception:
            pass
        return data

    def insertar(self, semana_id: int, data: dict) -> int:
        data = self._resolve_trabajador_id(dict(data))
        data = self._calc_torcedor(data)
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO nomina_taller
                      (semana_id, trabajador_id, nombre, ubic, puesto, sueldo, extras, pitas, precio_pita, firmado, notas)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        semana_id,
                        data.get("trabajador_id"),
                        data["nombre"],
                        data["ubic"],
                        data.get("puesto"),
                        float(data.get("sueldo") or 0),
                        float(data.get("extras") or 0),
                        data.get("pitas"),
                        data.get("precio_pita") or self.PRECIO_PITA_DEFAULT,
                        1 if data.get("firmado") else 0,
                        data.get("notas"),
                    ),
                )
            except Exception:
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
        data = self._calc_torcedor(dict(data))
        fields = []
        params: list = []
        for k in ("nombre", "ubic", "puesto", "sueldo", "extras", "pitas", "precio_pita", "firmado", "notas", "trabajador_id"):
            if k in data:
                fields.append(f"{k}=%s")
                params.append(data[k])
        if not fields:
            return
        params.append(row_id)
        with self.db.cursor() as cur:
            try:
                cur.execute(f"UPDATE nomina_taller SET {', '.join(fields)} WHERE id=%s", params)
            except Exception:
                # sin columnas pitas (migración pendiente)
                fields2, params2 = [], []
                for k in ("nombre", "ubic", "puesto", "sueldo", "extras", "firmado", "notas", "trabajador_id"):
                    if k in data:
                        fields2.append(f"{k}=%s")
                        params2.append(data[k])
                if not fields2:
                    return
                params2.append(row_id)
                cur.execute(f"UPDATE nomina_taller SET {', '.join(fields2)} WHERE id=%s", params2)

    def eliminar(self, row_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM nomina_taller WHERE id=%s", (row_id,))


class ProduccionPitaRepo(BaseRepo):
    """Nómina Pita: modelo/folio/material PITA NxN + efectivo."""

    def listar_por_semana(self, semana_id: int, **_kwargs) -> list[dict]:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.semana_id, p.trabajador_id,
                       COALESCE(tr.nombre_mostrar, p.nombre) AS nombre,
                       COALESCE(tr.ubic, p.ubic) AS ubic,
                       p.modelo, p.folio, p.material, p.producto, p.pitas, p.efectivo,
                       p.firmado, p.notas
                FROM produccion_pita p
                LEFT JOIN trabajadores tr ON tr.id = p.trabajador_id
                WHERE p.semana_id = %s
                ORDER BY COALESCE(tr.ubic, p.ubic), COALESCE(tr.nombre_mostrar, p.nombre)
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


class CatalogosRepo:
    """Catálogos: tarifas_material y modelos (fuente de verdad en BD)."""

    def __init__(self, db=None) -> None:
        self.db = db or get_db()

    def listar_materiales(self, solo_activos: bool = True) -> list[dict]:
        sql = "SELECT id, material, tarifa_por_gramo, descripcion, activo FROM tarifas_material"
        if solo_activos:
            sql += " WHERE activo = 1"
        sql += " ORDER BY material"
        try:
            with self.db.cursor() as cur:
                cur.execute(sql)
                return list(cur.fetchall() or [])
        except Exception:
            return []

    def upsert_material(
        self,
        material: str,
        tarifa_por_gramo: float,
        descripcion: str | None = None,
        activo: int = 1,
        mat_id: int | None = None,
    ) -> dict:
        material = (material or "").strip().upper()
        if not material:
            raise ValueError("Material vacío")
        with self.db.cursor() as cur:
            if mat_id:
                cur.execute(
                    """
                    UPDATE tarifas_material
                       SET material=%s, tarifa_por_gramo=%s, descripcion=%s, activo=%s
                     WHERE id=%s
                    """,
                    (material, tarifa_por_gramo, descripcion, int(bool(activo)), mat_id),
                )
                return {"id": mat_id, "ok": True}
            cur.execute(
                """
                INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion, activo)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  tarifa_por_gramo = VALUES(tarifa_por_gramo),
                  descripcion = VALUES(descripcion),
                  activo = VALUES(activo)
                """,
                (material, tarifa_por_gramo, descripcion, int(bool(activo))),
            )
            cur.execute("SELECT id FROM tarifas_material WHERE material=%s", (material,))
            row = cur.fetchone() or {}
            return {"id": row.get("id"), "ok": True}

    def set_material_activo(self, mat_id: int, activo: bool) -> None:
        with self.db.cursor() as cur:
            cur.execute(
                "UPDATE tarifas_material SET activo=%s WHERE id=%s",
                (1 if activo else 0, mat_id),
            )

    def listar_modelos(self, tipo: str | None = None) -> list[dict]:
        sql = "SELECT id, modelo, tipo, material_default, tarifa_default, notas FROM modelos"
        params: tuple = ()
        if tipo:
            sql += " WHERE tipo=%s"
            params = (tipo,)
        sql += " ORDER BY tipo, modelo"
        try:
            with self.db.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall() or [])
        except Exception:
            return []

    def upsert_modelo(
        self,
        modelo: str,
        tipo: str = "PLT",
        material_default: str | None = None,
        tarifa_default: float | None = None,
        notas: str | None = None,
        modelo_id: int | None = None,
    ) -> dict:
        modelo = (modelo or "").strip().upper()
        tipo = (tipo or "PLT").strip().upper()
        if not modelo:
            raise ValueError("Modelo vacío")
        with self.db.cursor() as cur:
            if modelo_id:
                cur.execute(
                    """
                    UPDATE modelos
                       SET modelo=%s, tipo=%s, material_default=%s, tarifa_default=%s, notas=%s
                     WHERE id=%s
                    """,
                    (modelo, tipo, material_default, tarifa_default, notas, modelo_id),
                )
                return {"id": modelo_id, "ok": True}
            cur.execute(
                """
                INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  material_default = VALUES(material_default),
                  tarifa_default = VALUES(tarifa_default),
                  notas = VALUES(notas)
                """,
                (modelo, tipo, material_default, tarifa_default, notas),
            )
            cur.execute(
                "SELECT id FROM modelos WHERE modelo=%s AND tipo=%s",
                (modelo, tipo),
            )
            row = cur.fetchone() or {}
            return {"id": row.get("id"), "ok": True}

    def eliminar_modelo(self, modelo_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM modelos WHERE id=%s", (modelo_id,))

    def materiales_nombres(self, solo_activos: bool = True) -> list[str]:
        return [str(m["material"]) for m in self.listar_materiales(solo_activos=solo_activos) if m.get("material")]

    def tarifa_de(self, material: str) -> float | None:
        material = (material or "").strip().upper()
        if not material:
            return None
        for m in self.listar_materiales(solo_activos=False):
            if str(m.get("material") or "").upper() == material:
                try:
                    return float(m.get("tarifa_por_gramo") or 0)
                except (TypeError, ValueError):
                    return None
        return None
