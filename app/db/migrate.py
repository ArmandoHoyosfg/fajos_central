"""Migraciones versionadas al arranque.

Aplica scripts en db/schema/ (excepto 000_ completo) y registra en schema_migrations.
Idempotente: ADD COLUMN IF NOT EXISTS / CREATE TABLE IF NOT EXISTS recomendados.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.core.logging_config import get_logger
from app.db.connection import get_db

logger = get_logger(__name__)

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "db" / "schema"
# 000 es bootstrap completo (DROP+CREATE); no se re-aplica en instalaciones vivas
SKIP_PREFIXES = ("000_",)


def _list_scripts() -> list[Path]:
    if not SCHEMA_DIR.is_dir():
        return []
    files = sorted(SCHEMA_DIR.glob("*.sql"))
    return [p for p in files if not any(p.name.startswith(s) for s in SKIP_PREFIXES)]


def _split_statements(sql: str) -> list[str]:
    """Parte por ; respetando comentarios simples."""
    lines = []
    for line in sql.splitlines():
        s = line.strip()
        if s.startswith("--"):
            continue
        lines.append(line)
    text = "\n".join(lines)
    parts = []
    buf = []
    for chunk in text.split(";"):
        chunk = chunk.strip()
        if chunk:
            parts.append(chunk)
    return parts


class MigrationRunner:
    def ensure_table(self) -> None:
        with get_db().cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                  filename VARCHAR(120) NOT NULL,
                  applied_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  ok TINYINT(1) NOT NULL DEFAULT 1,
                  mensaje VARCHAR(255) NULL,
                  PRIMARY KEY (id),
                  UNIQUE KEY uk_filename (filename)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

    def applied(self) -> set[str]:
        self.ensure_table()
        with get_db().cursor() as cur:
            cur.execute("SELECT filename FROM schema_migrations WHERE ok = 1")
            return {str(r["filename"]) for r in (cur.fetchall() or [])}

    def status(self) -> list[dict[str, Any]]:
        applied = self.applied()
        out = []
        for p in _list_scripts():
            out.append({
                "filename": p.name,
                "applied": p.name in applied,
                "path": str(p),
            })
        return out

    def apply_pending(self) -> dict[str, Any]:
        """Aplica scripts pendientes. Devuelve resumen."""
        self.ensure_table()
        done = self.applied()
        applied_now: list[str] = []
        errors: list[str] = []
        skipped: list[str] = []

        for path in _list_scripts():
            if path.name in done:
                skipped.append(path.name)
                continue
            sql = path.read_text(encoding="utf-8", errors="replace")
            stmts = _split_statements(sql)
            try:
                with get_db().cursor() as cur:
                    for st in stmts:
                        try:
                            cur.execute(st)
                            try:
                                if getattr(cur, "with_rows", False):
                                    cur.fetchall()
                                while cur.nextset():
                                    if getattr(cur, "with_rows", False):
                                        cur.fetchall()
                            except Exception:
                                pass
                        except Exception as e:
                            # Idempotencia blanda: columna/tabla ya existe
                            msg = str(e).lower()
                            if any(x in msg for x in ("duplicate", "exists", "already")):
                                logger.info("migrate ignore (%s): %s", path.name, e)
                                continue
                            raise
                    cur.execute(
                        """
                        INSERT INTO schema_migrations (filename, ok, mensaje)
                        VALUES (%s, 1, %s)
                        ON DUPLICATE KEY UPDATE ok=1, mensaje=VALUES(mensaje), applied_en=CURRENT_TIMESTAMP
                        """,
                        (path.name, f"{len(stmts)} statements"),
                    )
                applied_now.append(path.name)
                logger.info("Migración aplicada: %s", path.name)
            except Exception as e:
                logger.exception("Fallo migración %s", path.name)
                errors.append(f"{path.name}: {e}")
                try:
                    with get_db().cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO schema_migrations (filename, ok, mensaje)
                            VALUES (%s, 0, %s)
                            ON DUPLICATE KEY UPDATE ok=0, mensaje=VALUES(mensaje)
                            """,
                            (path.name, str(e)[:250]),
                        )
                except Exception:
                    pass

        return {
            "ok": len(errors) == 0,
            "applied": applied_now,
            "skipped": skipped,
            "errors": errors,
            "pending_before": [p.name for p in _list_scripts() if p.name not in done],
        }


def run_migrations_on_startup() -> dict[str, Any]:
    try:
        return MigrationRunner().apply_pending()
    except Exception as e:
        logger.warning("No se pudieron aplicar migraciones al arranque: %s", e)
        return {"ok": False, "errors": [str(e)], "applied": [], "skipped": []}
