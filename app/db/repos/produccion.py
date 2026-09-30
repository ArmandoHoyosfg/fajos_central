"""Repositorio: ProduccionRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class ProduccionRepo(BaseRepo):
    def obtener(self, prod_id: int) -> dict | None:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM produccion_plata WHERE id = %s", (prod_id,))
            return cur.fetchone()

    def listar_por_semana(self, semana_id: int, *, incluir_terminados: bool = False) -> list[dict]:
        """Lista producción; por defecto **no** muestra folios terminados/cerrados.

        Criterio de ocultar (cualquiera):
        - notas contienen [terminado]
        - trabajo ligado con activo = 0
        """
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
            # Ocultar si notas tienen [terminado] O el trabajo está inactivo.
            # (Antes: trabajo_id NULL pasaba el filtro de trabajo; solo notas bastaba,
            #  pero reforzamos con exclusión explícita.)
            sql += """
              AND (p.notas IS NULL OR (p.notas NOT LIKE %s AND LOWER(p.notas) NOT LIKE %s))
              AND NOT (p.trabajo_id IS NOT NULL AND COALESCE(tj.activo, 1) = 0)
            """
            params: tuple = (semana_id, "%[terminado]%", "%[cerrado]%")
        else:
            params = (semana_id,)
        sql += """
            ORDER BY COALESCE(tr.nombre_mostrar, p.nombre), COALESCE(tr.ubic, p.ubic), p.id
        """
        with self.db.cursor() as cur:
            try:
                cur.execute(sql, params)
                rows = list(cur.fetchall() or [])
                if not incluir_terminados:
                    from app.services.export.helpers import linea_activa
                    rows = [r for r in rows if linea_activa(r)]
                return rows
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
                    from app.services.export.helpers import linea_activa
                    rows = [r for r in rows if linea_activa(r)]
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
            from app.db.repos.trabajos import TrabajosRepo
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



    def meta_por_folio(self, folio: str, semana_id: int | None = None) -> dict | None:
        """Última línea conocida del folio → modelo, material, tarifa."""
        folio = (folio or "").strip()
        if not folio:
            return None
        with self.db.cursor() as cur:
            if semana_id:
                cur.execute(
                    """
                    SELECT modelo, material, tarifa_gr, folio
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) = UPPER(%s) AND semana_id = %s
                    ORDER BY id DESC LIMIT 1
                    """,
                    (folio, int(semana_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT modelo, material, tarifa_gr, folio
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) = UPPER(%s)
                    ORDER BY id DESC LIMIT 1
                    """,
                    (folio,),
                )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "modelo": row.get("modelo"),
                "material": row.get("material"),
                "tarifa_gr": float(row["tarifa_gr"]) if row.get("tarifa_gr") is not None else None,
            }

    def sincronizar_folio(
        self,
        folio: str,
        *,
        modelo: str | None = None,
        material: str | None = None,
        tarifa_gr: float | None = None,
        semana_id: int | None = None,
    ) -> int:
        """Actualiza modelo/material/tarifa en todas las líneas del mismo folio."""
        folio = (folio or "").strip()
        if not folio:
            return 0
        fields, params = [], []
        if modelo is not None and str(modelo).strip() != "":
            fields.append("modelo=%s")
            params.append(str(modelo).strip())
        if material is not None and str(material).strip() != "":
            fields.append("material=%s")
            params.append(str(material).strip())
        if tarifa_gr is not None and str(tarifa_gr).strip() != "":
            fields.append("tarifa_gr=%s")
            params.append(float(tarifa_gr))
        if not fields:
            return 0
        sql = f"UPDATE produccion_plata SET {', '.join(fields)} WHERE UPPER(TRIM(folio)) = UPPER(%s)"
        params.append(folio)
        if semana_id:
            sql += " AND semana_id=%s"
            params.append(int(semana_id))
        with self.db.cursor() as cur:
            cur.execute(sql, params)
            return int(cur.rowcount or 0)


    def duplicar_trabajos_a_semana(self, semana_origen_id: int, semana_destino_id: int) -> dict:
        """
        Copia trabajos ACTIVOS con línea de producción a otra semana.
        No copia gramos ni folios terminados/cerrados.
        Reutiliza trabajo_id existentes.
        """
        from app.services.audit_service import AuditService
        from app.services.export_service import linea_activa

        AuditService(self.db).assert_semana_abierta(semana_destino_id)
        with self.db.cursor() as cur:
            # Solo líneas de origen que NO estén terminadas/cerradas
            try:
                cur.execute(
                    """
                    SELECT p.trabajador_id, p.trabajo_id, p.nombre, p.ubic, p.folio, p.modelo,
                           p.material, p.tarifa_gr, p.notas,
                           COALESCE(t.activo, 1) AS trabajo_activo
                    FROM produccion_plata p
                    LEFT JOIN trabajos t ON t.id = p.trabajo_id
                    WHERE p.semana_id = %s
                      AND (p.notas IS NULL OR (
                            LOWER(p.notas) NOT LIKE '%%[terminado]%%'
                        AND LOWER(p.notas) NOT LIKE '%%[cerrado]%%'
                      ))
                      AND (t.id IS NULL OR t.activo = 1)
                    """,
                    (semana_origen_id,),
                )
            except Exception:
                # Fallback sin JOIN trabajos (BD antigua)
                cur.execute(
                    """
                    SELECT p.trabajador_id, p.trabajo_id, p.nombre, p.ubic, p.folio, p.modelo,
                           p.material, p.tarifa_gr, p.notas
                    FROM produccion_plata p
                    WHERE p.semana_id = %s
                      AND (p.notas IS NULL OR (
                            LOWER(p.notas) NOT LIKE '%%[terminado]%%'
                        AND LOWER(p.notas) NOT LIKE '%%[cerrado]%%'
                      ))
                    """,
                    (semana_origen_id,),
                )
            origen = list(cur.fetchall() or [])
            # Trabajos activos del catálogo (solo activo=1)
            cur.execute(
                """
                SELECT t.id AS trabajo_id, t.trabajador_id, tr.nombre_mostrar AS nombre, tr.ubic,
                       t.folio, t.modelo, t.material, t.tarifa_gr,
                       1 AS trabajo_activo
                FROM trabajos t
                JOIN trabajadores tr ON tr.id = t.trabajador_id
                WHERE t.activo = 1 AND tr.activo = 1
                """
            )
            todos = list(cur.fetchall() or [])
        # Solo líneas de la semana origen (evita re-duplicar el catálogo completo).
        # Defensa extra con linea_activa (notas / flags).
        seen = set()
        to_insert = []
        skipped_cerrados = 0
        for r in origen:
            if not linea_activa(r):
                skipped_cerrados += 1
                continue
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
        return {
            "created": created,
            "skipped": skipped,
            "skipped_cerrados": skipped_cerrados,
            "total_candidates": len(to_insert),
        }


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




