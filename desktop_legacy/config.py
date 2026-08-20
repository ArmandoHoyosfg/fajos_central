"""
Configuración app de escritorio — usa config.ini de la raíz del proyecto.
"""
from __future__ import annotations

import configparser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
RESOURCES_DIR = BASE_DIR / "resources"
CONFIG_INI = PROJECT_ROOT / "config.ini"


def _read_project_version() -> str:
    vf = PROJECT_ROOT / "VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip() or "2.4.0"
    return "2.4.0"


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

APP_NAME = "Fajos Piteados Central"
APP_VERSION = _read_project_version()
APP_ORG = "Taller de Fajos Central"
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700
