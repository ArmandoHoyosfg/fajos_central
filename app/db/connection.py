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
            self._conn = mysql.connector.connect(**self._config)
            logger.info(
                "Conectado a %s@%s:%s/%s",
                self._config["user"],
                self._config["host"],
                self._config["port"],
                self._config["database"],
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
        cur = conn.cursor(dictionary=dictionary)
        try:
            yield cur
        except Error as e:
            logger.exception("Error en consulta SQL")
            raise DatabaseError(
                "Error al ejecutar consulta en la base de datos.",
                details={"mysql_errno": getattr(e, "errno", None)},
                cause=e,
            ) from e
        finally:
            cur.close()


_db: Optional[Database] = None


def get_db() -> Database:
    global _db
    if _db is None:
        _db = Database()
    return _db
