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
        Copia nombre_mostrar, ubic (y puesto en taller) del catálogo hacia:
        produccion_plata, produccion_pita, nomina_taller.

        1) Por trabajador_id (preferido)
        2) Filas huérfanas con el nombre+ubic anteriores (si se pasan)
        """
        t = self.obtener(trabajador_id)
        nombre = t.get("nombre_mostrar")
        ubic = t.get("ubic")
        puesto = t.get("puesto")
        counts = {"plata": 0, "pita": 0, "taller": 0, "orphans": 0}
        with self.db.cursor() as cur:
            cur.execute(
                """
                UPDATE produccion_plata
                   SET nombre = %s, ubic = %s
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, trabajador_id),
            )
            counts["plata"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

            cur.execute(
                """
                UPDATE produccion_pita
                   SET nombre = %s, ubic = %s
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, trabajador_id),
            )
            counts["pita"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

            cur.execute(
                """
                UPDATE nomina_taller
                   SET nombre = %s, ubic = %s, puesto = COALESCE(%s, puesto)
                 WHERE trabajador_id = %s
                """,
                (nombre, ubic, puesto, trabajador_id),
            )
            counts["taller"] = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0

            # Huérfanas: mismo nombre+ubic viejos, sin trabajador_id o con NULL
            if nombre_ant is not None and ubic_ant is not None:
                for table in ("produccion_plata", "produccion_pita", "nomina_taller"):
                    if table == "nomina_taller":
                        cur.execute(
                            f"""
                            UPDATE {table}
                               SET nombre = %s, ubic = %s, trabajador_id = %s,
                                   puesto = COALESCE(%s, puesto)
                             WHERE (trabajador_id IS NULL OR trabajador_id = 0)
                               AND nombre = %s AND ubic = %s
                            """,
                            (nombre, ubic, trabajador_id, puesto, nombre_ant, ubic_ant),
                        )
                    else:
                        cur.execute(
                            f"""
                            UPDATE {table}
                               SET nombre = %s, ubic = %s, trabajador_id = %s
                             WHERE (trabajador_id IS NULL OR trabajador_id = 0)
                               AND nombre = %s AND ubic = %s
                            """,
                            (nombre, ubic, trabajador_id, nombre_ant, ubic_ant),
                        )
                    n = cur.rowcount if cur.rowcount and cur.rowcount > 0 else 0
                    counts["orphans"] += n
                    # También filas con trabajador_id ya correcto ya actualizadas;
                    # filas con OTRO id no se tocan.

                # Filas que aún tienen el ubic/nombre viejos pero YA tienen este trabajador_id
                # (por si el UPDATE por id falló parcialmente) — redundante pero seguro
                pass

        return counts

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
            try:
                cur.execute(
                    """
                    SELECT n.id, n.semana_id, n.trabajador_id, n.nombre, n.ubic, n.puesto,
                           n.sueldo, n.extras, n.total, n.firmado, n.notas,
                           COALESCE(tr.sueldo_modo, 'variable') AS sueldo_modo,
                           tr.sueldo_base
                    FROM nomina_taller n
                    LEFT JOIN trabajadores tr ON tr.id = n.trabajador_id
                    WHERE n.semana_id = %s
                    ORDER BY n.ubic, n.nombre
                    """,
                    (semana_id,),
                )
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
            for r in rows:
                r.setdefault("sueldo_modo", "variable")
                r.setdefault("sueldo_base", None)
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
