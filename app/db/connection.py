"""
Conexión a MariaDB con manejo de errores claro.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Optional

import mysql.connector
from mysql.connector import Error, MySQLConnection

from app.core.config import settings
from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class Database:
    def __init__(self, config: dict | None = None):
        self._config = config or settings.db_config
        self._conn: Optional[MySQLConnection] = None

    def connect(self) -> MySQLConnection:
        if self._conn is not None and self._conn.is_connected():
            return self._conn
        try:
            cfg = dict(self._config)
            # autocommit evita pérdida de INSERT/CREATE si se olvida commit
            cfg.setdefault("autocommit", True)
            self._conn = mysql.connector.connect(**cfg)
            logger.info(
                "Conectado a %s@%s:%s/%s",
                cfg.get("user"),
                cfg.get("host"),
                cfg.get("port"),
                cfg.get("database"),
            )
            return self._conn
        except Error as e:
            logger.exception("Fallo de conexión a BD")
            raise DatabaseError(
                "No se pudo conectar a la base de datos.",
                details={
                    "host": self._config.get("host"),
                    "database": self._config.get("database"),
                    "mysql_errno": getattr(e, "errno", None),
                },
                cause=e,
            ) from e

    def close(self) -> None:
        if self._conn is not None and self._conn.is_connected():
            self._conn.close()
            self._conn = None
            logger.info("Conexión BD cerrada")

    @contextmanager
    def cursor(self, dictionary: bool = True) -> Generator[Any, None, None]:
        conn = self.connect()
        cur = conn.cursor(dictionary=dictionary, buffered=True)
        try:
            yield cur
            if not getattr(conn, "autocommit", False):
                conn.commit()
        except Error as e:
            try:
                conn.rollback()
            except Exception:
                pass
            # 1146 table missing → warning, not stack trace noise for callers that recover
            errno = getattr(e, "errno", None)
            if errno == 1146:
                logger.warning("Tabla inexistente: %s", e)
            else:
                logger.exception("Error en consulta SQL")
            raise DatabaseError(
                "Error al ejecutar consulta en la base de datos.",
                details={"mysql_errno": errno, "msg": str(e)},
                cause=e,
            ) from e
        finally:
            try:
                cur.close()
            except Exception:
                pass


_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
