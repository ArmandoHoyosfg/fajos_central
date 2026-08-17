"""
Configuración central del proyecto Fajos Central.
"""
from pathlib import Path

# Rutas
BASE_DIR = Path(__file__).resolve().parent
RESOURCES_DIR = BASE_DIR / "resources"

# Base de datos MariaDB / MySQL
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "",          # <-- pon tu contraseña
    "database": "fajos_central",
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
    "autocommit": True,
}

# App
APP_NAME = "Fajos Central — Nóminas"
APP_VERSION = "1.0.0"
APP_ORG = "Taller de Fajos Central"

# UI
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700
