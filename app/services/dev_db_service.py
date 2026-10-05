"""Consultas y reparaciones guiadas para el panel DEV (seguro).

Nivel A: solo SELECT sobre tablas en allowlist, un statement, LIMIT forzado.
Nivel B: acciones de reparación versionadas en código (no SQL libre de escritura).
"""
from __future__ import annotations

import re
import time
from typing import Any

from app.core.logging_config import get_logger
from app.db.connection import get_db

logger = get_logger(__name__)

# Tablas permitidas en SELECT (minúsculas)
ALLOWED_TABLES: frozenset[str] = frozenset({
    "trabajadores",
    "trabajos",
    "semanas",
    "produccion_plata",
    "produccion_pita",
    "nomina_taller",
    "tarifas_material",
    "modelos",
    "historial_precios",
    "aprendizaje_eventos",
    "aprendizaje_stats",
    "schema_migrations",
    "cierre_dia",
})

MAX_ROWS = 200
QUERY_TIMEOUT_HINT = 8  # segundos (best-effort)

# Solo identificadores simples para FROM/JOIN
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|CREATE|REPLACE|GRANT|REVOKE|"
    r"CALL|EXEC|EXECUTE|INTO\s+OUTFILE|LOAD\s+DATA|SET\s+|LOCK\s+|UNLOCK\s+)\b",
    re.I,
)

PRESETS: list[dict[str, str]] = [
    {
        "id": "trab_activos",
        "label": "Trabajadores activos",
        "sql": "SELECT id, nombre_mostrar, ubic, tipo, puesto, sueldo_modo, sueldo_base, activo "
               "FROM trabajadores WHERE activo = 1 ORDER BY ubic, nombre_mostrar LIMIT 200",
    },
    {
        "id": "trab_baja",
        "label": "Trabajadores en baja",
        "sql": "SELECT id, nombre_mostrar, ubic, tipo, activo, notas "
               "FROM trabajadores WHERE activo = 0 ORDER BY id DESC LIMIT 200",
    },
    {
        "id": "semana_actual_lineas",
        "label": "Líneas Plata de la última semana",
        "sql": "SELECT p.id, p.nombre, p.ubic, p.folio, p.material, p.total_gramos, p.efectivo, p.notas "
               "FROM produccion_plata p "
               "WHERE p.semana_id = (SELECT id FROM semanas ORDER BY fecha_inicio DESC LIMIT 1) "
               "ORDER BY p.ubic, p.nombre LIMIT 200",
    },
    {
        "id": "folios_terminados",
        "label": "Líneas con [terminado] en notas",
        "sql": "SELECT id, semana_id, nombre, ubic, folio, total_gramos, notas "
               "FROM produccion_plata WHERE notas LIKE '%[terminado]%' "
               "ORDER BY id DESC LIMIT 200",
    },
    {
        "id": "trabajos_inactivos",
        "label": "Trabajos (folios) inactivos",
        "sql": "SELECT id, trabajador_id, folio, modelo, material, activo, terminado_en "
               "FROM trabajos WHERE activo = 0 ORDER BY id DESC LIMIT 200",
    },
    {
        "id": "semanas",
        "label": "Semanas (últimas 30)",
        "sql": "SELECT id, codigo, fecha_inicio, fecha_fin, anio, notas "
               "FROM semanas ORDER BY fecha_inicio DESC LIMIT 30",
    },
    {
        "id": "merges",
        "label": "Eventos de unión de fichas",
        "sql": "SELECT id, tipo, entidad_id, payload_json, creado_en "
               "FROM aprendizaje_eventos WHERE tipo IN ('merge','merge_rollback') "
               "ORDER BY id DESC LIMIT 50",
    },
    {
        "id": "migraciones",
        "label": "Migraciones aplicadas",
        "sql": "SELECT filename, ok, mensaje, applied_en FROM schema_migrations ORDER BY filename",
    },
]

REPAIRS: list[dict[str, str]] = [
    {
        "id": "migrar",
        "label": "Aplicar migraciones pendientes",
        "desc": "Ejecuta scripts en db/schema/ que aún no están en schema_migrations.",
    },
    {
        "id": "sync_denorm",
        "label": "Sincronizar catálogo → nóminas",
        "desc": "Copia nombre/ubic/puesto del catálogo a líneas denormalizadas.",
    },
    {
        "id": "huerfanos",
        "label": "Reparar huérfanos",
        "desc": "Reenlaza o limpia filas sin trabajador válido cuando es posible.",
    },
    {
        "id": "crear_semana",
        "label": "Crear semana actual si falta",
        "desc": "Alta la semana del calendario (sáb–vie) si no existe en BD.",
    },
    {
        "id": "purgar_terminados",
        "label": "Purgar terminados antiguos (>7 días)",
        "desc": "Limpia registros de trabajos terminados según la regla de purga.",
    },
    {
        "id": "reparar_inteligente",
        "label": "Reparación completa (pipeline)",
        "desc": "Migraciones → consistencia → huérfanos → sync (orden fijo en código).",
    },
]


class DevDbService:
    def list_presets(self) -> list[dict[str, str]]:
        return [{"id": p["id"], "label": p["label"]} for p in PRESETS]

    def list_repairs(self) -> list[dict[str, str]]:
        return list(REPAIRS)

    def list_tables(self) -> list[str]:
        return sorted(ALLOWED_TABLES)

    def _validate_select(self, sql: str) -> str:
        if not sql or not str(sql).strip():
            raise ValueError("SQL vacío")
        s = str(sql).strip().rstrip(";")
        if ";" in s:
            raise ValueError("Solo se permite un statement (sin ';')")
        if _FORBIDDEN.search(s):
            raise ValueError("Solo consultas SELECT de lectura están permitidas")
        # Quitar comentarios simples
        lines = []
        for line in s.splitlines():
            if line.strip().startswith("--"):
                continue
            lines.append(line)
        s = "\n".join(lines).strip()
        if not re.match(r"^SELECT\b", s, re.I):
            raise ValueError("La consulta debe empezar con SELECT")
        # Tablas referenciadas tras FROM / JOIN
        tables = re.findall(r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)", s, re.I)
        if not tables:
            raise ValueError("No se detectó tabla en FROM/JOIN")
        bad = [t for t in tables if t.lower() not in ALLOWED_TABLES]
        if bad:
            raise ValueError(
                f"Tabla(s) no permitida(s): {', '.join(bad)}. "
                f"Permitidas: {', '.join(sorted(ALLOWED_TABLES))}"
            )
        # Forzar LIMIT
        if not re.search(r"\bLIMIT\s+\d+", s, re.I):
            s = f"{s} LIMIT {MAX_ROWS}"
        else:
            def _cap_limit(m):
                n = int(m.group(1))
                return f"LIMIT {min(n, MAX_ROWS)}"
            s = re.sub(r"\bLIMIT\s+(\d+)", _cap_limit, s, count=1, flags=re.I)
        return s

    def run_select(self, sql: str | None = None, *, preset_id: str | None = None) -> dict[str, Any]:
        if preset_id:
            preset = next((p for p in PRESETS if p["id"] == preset_id), None)
            if not preset:
                raise ValueError(f"Preset desconocido: {preset_id}")
            sql = preset["sql"]
        safe = self._validate_select(sql or "")
        t0 = time.time()
        rows: list[dict] = []
        columns: list[str] = []
        with get_db().cursor() as cur:
            try:
                # Best-effort timeout (MariaDB)
                try:
                    cur.execute(f"SET SESSION MAX_EXECUTION_TIME={QUERY_TIMEOUT_HINT * 1000}")
                except Exception:
                    pass
                cur.execute(safe)
                rows = list(cur.fetchall() or [])
                if rows:
                    columns = list(rows[0].keys())
                elif cur.description:
                    columns = [d[0] for d in cur.description]
            finally:
                try:
                    cur.execute("SET SESSION MAX_EXECUTION_TIME=0")
                except Exception:
                    pass
        # Serializar valores no JSON
        clean = []
        for r in rows:
            item = {}
            for k, v in dict(r).items():
                if hasattr(v, "isoformat"):
                    item[k] = v.isoformat()
                elif isinstance(v, (bytes, bytearray)):
                    item[k] = v.decode("utf-8", errors="replace")
                else:
                    item[k] = v
            clean.append(item)
        ms = int((time.time() - t0) * 1000)
        logger.info("DEV SELECT ok rows=%s ms=%s", len(clean), ms)
        try:
            from app.services.aprendizaje_service import AprendizajeService
            AprendizajeService().registrar(
                "dev_select",
                entidad="dev",
                payload={"preset": preset_id, "sql": safe[:500], "rows": len(clean), "ms": ms},
            )
        except Exception:
            pass
        return {
            "ok": True,
            "sql": safe,
            "columns": columns,
            "rows": clean,
            "n": len(clean),
            "ms": ms,
            "limit_max": MAX_ROWS,
        }

    def run_repair(self, action_id: str) -> dict[str, Any]:
        action_id = (action_id or "").strip().lower()
        known = {r["id"] for r in REPAIRS}
        if action_id not in known:
            raise ValueError(f"Acción desconocida: {action_id}")
        result: dict[str, Any] = {"ok": True, "action": action_id}

        if action_id == "migrar":
            from app.db.migrate import MigrationRunner
            result.update(MigrationRunner().apply_pending())
        elif action_id == "sync_denorm":
            from app.db.repository import TrabajadoresRepo
            result["sync"] = TrabajadoresRepo().sincronizar_todos_denormalizados()
        elif action_id == "huerfanos":
            from app.db.repository import TrabajadoresRepo
            repo = TrabajadoresRepo()
            if hasattr(repo, "reparar_huerfanos"):
                result["huerfanos"] = repo.reparar_huerfanos()
            else:
                result["ok"] = False
                result["error"] = "reparar_huerfanos no disponible"
        elif action_id == "crear_semana":
            from app.db.repository import SemanasRepo
            from app.core.calendar_util import (
                encontrar_semana_actual,
                today,
                sugerir_codigo_semana,
            )
            sem = SemanasRepo()
            existentes = sem.listar()
            actual = encontrar_semana_actual(existentes, today())
            if actual:
                result["semana"] = {
                    "id": actual.get("id"),
                    "codigo": actual.get("codigo"),
                    "fecha_inicio": str(actual.get("fecha_inicio") or ""),
                    "fecha_fin": str(actual.get("fecha_fin") or ""),
                }
                result["msg"] = "La semana actual ya existe"
            else:
                codigo, sab, vie = sugerir_codigo_semana(today())
                sid = sem.crear({
                    "codigo": codigo,
                    "fecha_inicio": sab.isoformat(),
                    "fecha_fin": vie.isoformat(),
                    "anio": sab.year,
                    "notas": "Creada desde DEV",
                })
                result["semana_id"] = sid
                result["codigo"] = codigo
                result["msg"] = f"Semana creada {codigo}"
        elif action_id == "purgar_terminados":
            from app.services.aprendizaje_service import AprendizajeService
            try:
                result["purga"] = AprendizajeService().purgar_terminados(dias=7)
            except Exception as e:
                result["ok"] = False
                result["error"] = str(e)
        elif action_id == "reparar_inteligente":
            steps = []
            try:
                from app.db.migrate import MigrationRunner
                r = MigrationRunner().apply_pending()
                if not isinstance(r, dict):
                    r = {"result": r}
                r.setdefault("ok", True)
                steps.append({"paso": "migrar", **r})
            except Exception as e:
                steps.append({"paso": "migrar", "ok": False, "error": str(e)})
            try:
                from app.services.consistency_service import ConsistencyService
                r = ConsistencyService().revisar(auto_repair=False)
                if not isinstance(r, dict):
                    r = {"result": r}
                r.setdefault("ok", True)
                steps.append({"paso": "consistencia", **r})
            except Exception as e:
                steps.append({"paso": "consistencia", "ok": False, "error": str(e)})
            try:
                from app.db.repository import TrabajadoresRepo
                repo = TrabajadoresRepo()
                h = repo.reparar_huerfanos() if hasattr(repo, "reparar_huerfanos") else {}
                if not isinstance(h, dict):
                    h = {"result": h}
                h.setdefault("ok", True)
                steps.append({"paso": "huerfanos", **h})
                s = repo.sincronizar_todos_denormalizados() or {}
                if not isinstance(s, dict):
                    s = {"result": s}
                s.setdefault("ok", True)
                steps.append({"paso": "sync", **s})
            except Exception as e:
                steps.append({"paso": "sync", "ok": False, "error": str(e)})
            result["steps"] = steps
            result["ok"] = all(bool(s.get("ok", True)) for s in steps if isinstance(s, dict))

        try:
            from app.services.aprendizaje_service import AprendizajeService
            AprendizajeService().registrar(
                "dev_repair",
                entidad="dev",
                payload={"action": action_id, "ok": result.get("ok"), "summary": str(result)[:400]},
            )
        except Exception:
            pass
        return result
