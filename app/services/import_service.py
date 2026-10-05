"""
Importación segura Excel → MariaDB.

Seguridad:
- dry_run por defecto (no escribe)
- validación previa de filas
- no borra datos existentes
- upsert de trabajadores por (nombre_mostrar, ubic)
- evita duplicar producción (semana + nombre + ubic + folio)
- registro en import_log cuando se aplica
"""
from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl

from app.core.exceptions import ExportError, ValidationAppError
from app.core.normalize import canonical_name, fold_name
from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repository import ProduccionRepo, SemanasRepo, TrabajadoresRepo

logger = get_logger(__name__)


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return None if float(v) == 0 else float(v)
    try:
        f = float(str(v).replace(",", ".").strip())
        return None if f == 0 else f
    except (ValueError, TypeError):
        return None


def _str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


class ImportService:
    def __init__(self):
        self.db = get_db()
        self.trab = TrabajadoresRepo()
        self.sem = SemanasRepo()
        self.prod = ProduccionRepo()

    def import_excel(
        self,
        path: str | Path,
        *,
        dry_run: bool = True,
        codigo_semana: str | None = None,
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
        anio: int = 2026,
    ) -> dict[str, Any]:
        path = Path(path)
        if not path.exists():
            raise ValidationAppError(
                f"No se encuentra el archivo: {path}",
                details={"path": str(path)},
            )

        report: dict[str, Any] = {
            "archivo": str(path),
            "modo": "dry_run" if dry_run else "apply",
            "trabajadores": {"nuevos": [], "existentes": [], "errores": []},
            "semana": None,
            "produccion": {"nuevas": [], "omitidas_duplicado": [], "errores": []},
            "ok": True,
            "mensaje": "",
        }

        try:
            wb = openpyxl.load_workbook(path, data_only=True)
        except Exception as e:
            raise ValidationAppError(
                "No se pudo abrir el Excel. ¿Está corrupto o abierto en otro programa?",
                details={"path": str(path)},
                cause=e,
            ) from e

        # --- Trabajadores ---
        if "Trabajadores" in wb.sheetnames:
            self._import_trabajadores(wb["Trabajadores"], report, dry_run)
        else:
            report["trabajadores"]["errores"].append("Hoja 'Trabajadores' no encontrada")

        # --- Semana + producción desde Nomina-Imprimir ---
        if "Nomina-Imprimir" in wb.sheetnames:
            ws = wb["Nomina-Imprimir"]
            codigo, mes_txt = self._leer_cabecera_semana(ws)
            codigo = codigo_semana or codigo or "import"
            # Fechas: si no vienen, usar placeholders del año
            fi = fecha_inicio or f"{anio}-01-01"
            ff = fecha_fin or f"{anio}-12-31"

            semana_id = self._ensure_semana(codigo, fi, ff, anio, report, dry_run)
            if semana_id is not None or dry_run:
                self._import_produccion(ws, semana_id, report, dry_run)
        else:
            report["produccion"]["errores"].append("Hoja 'Nomina-Imprimir' no encontrada")

        n_err = (
            len(report["trabajadores"]["errores"])
            + len(report["produccion"]["errores"])
        )
        report["ok"] = n_err == 0 or (
            len(report["trabajadores"]["nuevos"])
            + len(report["produccion"]["nuevas"])
            + len(report["trabajadores"]["existentes"])
        ) > 0

        if dry_run:
            report["mensaje"] = (
                "Simulación (dry_run): no se escribió nada en la base de datos. "
                "Revisa el reporte y vuelve a ejecutar con dry_run=false para aplicar."
            )
        else:
            report["mensaje"] = "Importación aplicada."
            self._log_import(path.name, report)

        logger.info(
            "Import %s | nuevos_trab=%s prod=%s dry_run=%s",
            path.name,
            len(report["trabajadores"]["nuevos"]),
            len(report["produccion"]["nuevas"]),
            dry_run,
        )
        return report

    def _leer_cabecera_semana(self, ws) -> tuple[str | None, str | None]:
        codigo = None
        mes = None
        # Buscar en primeras filas valores de semana/mes
        for r in range(1, 6):
            for c in range(1, 12):
                v = ws.cell(r, c).value
                prev = ws.cell(r, c - 1).value if c > 1 else None
                if prev and isinstance(prev, str) and "semana" in prev.lower():
                    codigo = _str(v)
                if prev and isinstance(prev, str) and "mes" in prev.lower():
                    mes = _str(v)
        # Fallback estructura conocida: D3 semana, G3 mes
        if not codigo:
            codigo = _str(ws.cell(3, 4).value)
        if not mes:
            mes = _str(ws.cell(3, 7).value)
        return codigo, mes

    def _import_trabajadores(self, ws, report: dict, dry_run: bool) -> None:
        # Encabezados en fila 4 típica
        header_row = 4
        for r in range(5, (ws.max_row or 5) + 1):
            nombre = canonical_name(_str(ws.cell(r, 2).value) or "") or None
            ubic_v = ws.cell(r, 4).value
            if not nombre or ubic_v is None or ubic_v == "":
                continue
            try:
                ubic = int(ubic_v)
            except (TypeError, ValueError):
                report["trabajadores"]["errores"].append(
                    f"Fila {r}: ubic inválida ({ubic_v})"
                )
                continue

            tipo = _str(ws.cell(r, 5).value) or "PLT"
            puesto = _str(ws.cell(r, 6).value)
            activo_raw = _str(ws.cell(r, 7).value)
            activo = 0 if activo_raw and activo_raw.lower() in ("no", "0", "false") else 1
            nombre_completo = _str(ws.cell(r, 3).value) or nombre
            fecha_inc = ws.cell(r, 8).value
            if isinstance(fecha_inc, datetime):
                fecha_inc = fecha_inc.date().isoformat()
            elif isinstance(fecha_inc, date):
                fecha_inc = fecha_inc.isoformat()
            else:
                fecha_inc = _str(fecha_inc)

            existing = self._find_trabajador(nombre, ubic)
            if existing:
                report["trabajadores"]["existentes"].append(
                    {"id": existing["id"], "nombre": nombre, "ubic": ubic}
                )
                continue

            entry = {
                "nombre_mostrar": nombre,
                "nombre_completo": nombre_completo,
                "ubic": ubic,
                "tipo": tipo if tipo in ("PLT", "PIT", "TLL", "PLT/PIT", "Mixto") else "PLT",
                "puesto": puesto,
                "fecha_incorporacion": fecha_inc,
                "activo": activo,
            }
            if dry_run:
                report["trabajadores"]["nuevos"].append({**entry, "id": None})
            else:
                try:
                    new_id = self._insert_trabajador(entry)
                    report["trabajadores"]["nuevos"].append({**entry, "id": new_id})
                except Exception as e:
                    report["trabajadores"]["errores"].append(
                        f"Fila {r} ({nombre}/{ubic}): {e}"
                    )

    def _find_trabajador(self, nombre: str, ubic: int) -> dict | None:
        """Busca por ubic y nombre normalizado (ignora acentos/mayúsculas)."""
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT id, nombre_mostrar, ubic FROM trabajadores WHERE ubic = %s",
                (ubic,),
            )
            rows = list(cur.fetchall() or [])
        target = fold_name(nombre)
        for row in rows:
            if fold_name(row.get("nombre_mostrar") or "") == target:
                return row
        return None

    def _insert_trabajador(self, data: dict) -> int:
        sql = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self.db.cursor() as cur:
            cur.execute(
                sql,
                (
                    data["nombre_mostrar"],
                    data.get("nombre_completo"),
                    data["ubic"],
                    data.get("tipo") or "PLT",
                    data.get("puesto"),
                    data.get("activo", 1),
                    data.get("fecha_incorporacion"),
                ),
            )
            return cur.lastrowid

    def _ensure_semana(
        self,
        codigo: str,
        fecha_inicio: str,
        fecha_fin: str,
        anio: int,
        report: dict,
        dry_run: bool,
    ) -> int | None:
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT id FROM semanas WHERE codigo = %s AND anio = %s LIMIT 1",
                (codigo, anio),
            )
            row = cur.fetchone()
        if row:
            report["semana"] = {"id": row["id"], "codigo": codigo, "creada": False}
            return row["id"]
        if dry_run:
            report["semana"] = {"id": None, "codigo": codigo, "creada": True, "dry_run": True}
            return None
        sid = self.sem.crear(
            {
                "codigo": codigo,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "anio": anio,
                "notas": "Importada desde Excel",
            }
        )
        report["semana"] = {"id": sid, "codigo": codigo, "creada": True}
        return sid

    def _import_produccion(self, ws, semana_id: int | None, report: dict, dry_run: bool) -> None:
        # Headers fila 5; datos desde 6
        for r in range(6, (ws.max_row or 6) + 1):
            nombre = canonical_name(_str(ws.cell(r, 1).value) or "") or None
            ubic_v = ws.cell(r, 2).value
            folio = _str(ws.cell(r, 3).value)
            # Saltar filas vacías de grupo (sin nombre ni folio ni gramos)
            gms = [_num(ws.cell(r, c).value) for c in range(7, 14)]
            if not nombre and not folio and not any(gms):
                continue
            # Filas de continuación (solo folio/gramos bajo el mismo trabajador):
            # si no hay nombre, intentar heredar de filas anteriores no se hace aquí;
            # solo importamos filas con nombre+ubic o con folio+gramos y ubic
            if not nombre:
                # buscar nombre hacia arriba en el Excel es frágil; exigir nombre en fila
                if folio or any(gms):
                    report["produccion"]["errores"].append(
                        f"Fila {r}: hay folio/gramos pero sin nombre (usa la fila del trabajador)"
                    )
                continue
            try:
                ubic = int(ubic_v) if ubic_v is not None and ubic_v != "" else None
            except (TypeError, ValueError):
                ubic = None
            if ubic is None:
                report["produccion"]["errores"].append(f"Fila {r}: {nombre} sin ubic válida")
                continue

            modelo = _str(ws.cell(r, 4).value)
            material = _str(ws.cell(r, 5).value)
            tarifa = _num(ws.cell(r, 6).value)
            notas = _str(ws.cell(r, 14).value)

            # Si no hay ningún gramo ni folio, no importar fila vacía de plantilla
            if not folio and not any(gms) and not modelo:
                continue

            trab = self._find_trabajador(nombre, ubic)
            payload = {
                "trabajador_id": trab["id"] if trab else None,
                "nombre": nombre,
                "ubic": ubic,
                "folio": folio,
                "modelo": modelo,
                "material": material,
                "tarifa_gr": tarifa,
                "gm_sab": gms[0],
                "gm_dom": gms[1],
                "gm_lun": gms[2],
                "gm_mar": gms[3],
                "gm_mie": gms[4],
                "gm_jue": gms[5],
                "gm_vie": gms[6],
                "notas": notas,
            }

            if not dry_run and semana_id is not None:
                if self._prod_exists(semana_id, nombre, ubic, folio):
                    report["produccion"]["omitidas_duplicado"].append(
                        {"nombre": nombre, "ubic": ubic, "folio": folio, "fila": r}
                    )
                    continue
                try:
                    new_id = self.prod.insertar(semana_id, payload)
                    report["produccion"]["nuevas"].append({**payload, "id": new_id, "fila": r})
                except Exception as e:
                    report["produccion"]["errores"].append(f"Fila {r}: {e}")
            else:
                report["produccion"]["nuevas"].append({**payload, "id": None, "fila": r})

    def _prod_exists(
        self, semana_id: int, nombre: str, ubic: int, folio: str | None
    ) -> bool:
        with self.db.cursor() as cur:
            if folio:
                cur.execute(
                    "SELECT id FROM produccion_plata WHERE semana_id=%s AND nombre=%s "
                    "AND ubic=%s AND folio=%s LIMIT 1",
                    (semana_id, nombre, ubic, folio),
                )
            else:
                cur.execute(
                    "SELECT id FROM produccion_plata WHERE semana_id=%s AND nombre=%s "
                    "AND ubic=%s AND (folio IS NULL OR folio='') LIMIT 1",
                    (semana_id, nombre, ubic),
                )
            return cur.fetchone() is not None

    def _log_import(self, archivo: str, report: dict) -> None:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "INSERT INTO import_log (archivo, modo, resumen_json, ok, mensaje) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        archivo,
                        report["modo"],
                        json.dumps(report, default=str, ensure_ascii=False)[:60000],
                        1 if report["ok"] else 0,
                        report.get("mensaje", "")[:500],
                    ),
                )
        except Exception as e:
            # Tabla puede no existir aún
            logger.warning("No se pudo escribir import_log: %s", e)
