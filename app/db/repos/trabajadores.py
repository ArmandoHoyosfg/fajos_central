"""Repositorio: TrabajadoresRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

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
        try:
            ubic = int(data["ubic"])
        except (TypeError, ValueError):
            raise ValidationAppError("La ubicación debe ser un número.", details={"field": "ubic"})
        nombre = str(data["nombre_mostrar"]).strip()
        nombre_full = (data.get("nombre_completo") or nombre or "").strip() or nombre
        tipo = (data.get("tipo") or "PLT").strip() or "PLT"
        puesto = (data.get("puesto") or None)
        if puesto is not None:
            puesto = str(puesto).strip() or None
        modo = str(data.get("sueldo_modo") or "variable").strip().lower()
        if modo not in ("fijo", "variable"):
            modo = "variable"
        base = None
        if data.get("sueldo_base") not in (None, ""):
            try:
                base = float(data["sueldo_base"])
            except (TypeError, ValueError):
                raise ValidationAppError("Sueldo base inválido.", details={"field": "sueldo_base"})
        fecha = _parse_fecha_sql(data.get("fecha_incorporacion"))
        notas = data.get("notas") or None
        activo = 1
        if data.get("activo") is not None and str(data.get("activo")).strip() != "":
            try:
                activo = 1 if int(data.get("activo")) else 0
            except (TypeError, ValueError):
                activo = 1

        # Evitar duplicado obvio nombre+ubic activos
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM trabajadores
                 WHERE nombre_mostrar = %s AND ubic = %s AND activo = 1
                 LIMIT 1
                """,
                (nombre, ubic),
            )
            exists = cur.fetchone()
            if exists:
                raise ValidationAppError(
                    f"Ya existe un trabajador activo «{nombre}» en ubic {ubic} (id={exists.get('id')}).",
                    details={"field": "nombre_mostrar", "id": exists.get("id")},
                )

        params_full = (nombre, nombre_full, ubic, tipo, puesto, modo, base, activo, fecha, notas, None)
        sql_full = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, sueldo_modo, sueldo_base,
                 activo, fecha_incorporacion, notas, codigo_qr)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        sql_mid = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, sueldo_modo, sueldo_base,
                 activo, fecha_incorporacion, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        params_mid = (nombre, nombre_full, ubic, tipo, puesto, modo, base, activo, fecha, notas)
        sql_legacy = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        params_legacy = (nombre, nombre_full, ubic, tipo, puesto, activo, fecha, notas)

        try:
            with self.db.cursor() as cur:
                try:
                    cur.execute(sql_full, params_full)
                except Exception as e1:
                    msg = str(e1).lower()
                    if "unknown column" in msg or "sueldo_modo" in msg or "codigo_qr" in msg:
                        try:
                            cur.execute(sql_mid, params_mid)
                        except Exception as e2:
                            msg2 = str(e2).lower()
                            if "unknown column" in msg2 or "sueldo" in msg2:
                                cur.execute(sql_legacy, params_legacy)
                            else:
                                raise
                    else:
                        raise
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
        if "fecha_incorporacion" in data:
            data["fecha_incorporacion"] = _parse_fecha_sql(data.get("fecha_incorporacion"))
        if "ubic" in data and data["ubic"] not in (None, ""):
            try:
                data["ubic"] = int(data["ubic"])
            except (TypeError, ValueError):
                raise ValidationAppError("La ubicación debe ser un número.", details={"field": "ubic"})
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
        counts = {"plata": 0, "pita": 0, "taller": 0, "taller_sueldo": 0, "orphans": 0, "by_name": 0}
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

            # --- Taller: nombre, ubic, puesto ---
            cur.execute(
                """
                UPDATE nomina_taller
                   SET nombre = %s, ubic = %s, puesto = COALESCE(%s, puesto)
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, puesto, trabajador_id),
            )
            counts["taller"] = max(0, cur.rowcount or 0)

            # --- Taller: sueldo fijo desde catálogo (solo no firmados) ---
            modo = str(t.get("sueldo_modo") or "variable").strip().lower()
            base = t.get("sueldo_base")
            counts["taller_sueldo"] = 0
            if modo == "fijo" and base is not None and str(base).strip() != "":
                try:
                    base_f = float(base)
                    cur.execute(
                        """
                        UPDATE nomina_taller
                           SET sueldo = %s,
                               total = %s + COALESCE(extras, 0),
                               puesto = COALESCE(%s, puesto)
                         WHERE trabajador_id = %s
                           AND COALESCE(firmado, 0) = 0
                           AND (
                                COALESCE(sueldo, 0) = 0
                                OR ABS(COALESCE(sueldo, 0) - %s) > 0.009
                           )
                        """,
                        (base_f, base_f, puesto, trabajador_id, base_f),
                    )
                    counts["taller_sueldo"] = max(0, cur.rowcount or 0)
                except (TypeError, ValueError):
                    pass

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
        total = {"plata": 0, "pita": 0, "taller": 0, "taller_sueldo": 0, "trabajadores": 0}
        with self.db.cursor() as cur:
            cur.execute("SELECT id FROM trabajadores")
            ids = [int(r["id"]) for r in (cur.fetchall() or [])]
        for tid in ids:
            try:
                c = self.sincronizar_denormalizados(tid)
                total["plata"] += c.get("plata", 0)
                total["pita"] += c.get("pita", 0)
                total["taller"] += c.get("taller", 0)
                total["taller_sueldo"] += c.get("taller_sueldo", 0)
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


