"""
Conexión singleton a MariaDB/MySQL.
"""
from __future__ import annotations

from typing import Optional

import mysql.connector
from mysql.connector import Error, MySQLConnection

from config import DB_CONFIG


class Database:
    _instance: Optional["Database"] = None
    _conn: Optional[MySQLConnection] = None

    def __new__(cls) -> "Database":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def connect(self) -> MySQLConnection:
        if self._conn is None or not self._conn.is_connected():
            try:
                self._conn = mysql.connector.connect(**DB_CONFIG)
            except Error as e:
                raise ConnectionError(f"No se pudo conectar a la base de datos: {e}") from e
        return self._conn

    def cursor(self, dictionary: bool = True):
        conn = self.connect()
        return conn.cursor(dictionary=dictionary)

    def close(self) -> None:
        if self._conn and self._conn.is_connected():
            self._conn.close()
            self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and self._conn.is_connected()
