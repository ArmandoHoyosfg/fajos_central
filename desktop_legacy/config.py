"""
Configuración app de escritorio — usa config.ini de la raíz del proyecto.
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
RESOURCES_DIR = BASE_DIR / "resources"
CONFIG_INI = PROJECT_ROOT / "config.ini"


def _load_db_config() -> dict:
    cfg = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "fajos_central",
        "charset": "utf8mb4",
        "collation": "utf8mb4_unicode_ci",
        "autocommit": True,
    }
    if not CONFIG_INI.exists():
        return cfg
    parser = configparser.ConfigParser()
    parser.read(CONFIG_INI, encoding="utf-8")
    if parser.has_section("database"):
        db = parser["database"]
        cfg["host"] = db.get("host", cfg["host"])
        try:
            cfg["port"] = int(db.get("port", str(cfg["port"])))
        except ValueError:
            pass
        cfg["user"] = db.get("user", cfg["user"])
        cfg["password"] = db.get("password", cfg["password"])
        cfg["database"] = db.get("database", cfg["database"])
    return cfg


DB_CONFIG = _load_db_config()

APP_NAME = "Fajos Central — Nóminas"
APP_VERSION = "1.0.0"
APP_ORG = "Taller de Fajos Central"
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700
