"""
Configuración central.
Prioridad (de mayor a menor):
  1. Variables de entorno FAJOS_*
  2. Archivo .env
  3. Archivo config.ini  ← usuario / contraseña de MariaDB
  4. Valores por defecto
"""
from __future__ import annotations

import configparser
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_INI = BASE_DIR / "config.ini"
CONFIG_INI_EXAMPLE = BASE_DIR / "config.ini.example"


def _read_ini() -> dict:
    """Lee config.ini si existe y devuelve dict plano para defaults."""
    data: dict = {}
    path = CONFIG_INI if CONFIG_INI.exists() else None
    if path is None:
        return data
    parser = configparser.ConfigParser()
    try:
        parser.read(path, encoding="utf-8")
    except Exception:
        return data
    if parser.has_section("database"):
        db = parser["database"]
        if db.get("host"):
            data["db_host"] = db.get("host", "localhost")
        if db.get("port"):
            try:
                data["db_port"] = int(db.get("port", "3306"))
            except ValueError:
                pass
        if "user" in db:
            data["db_user"] = db.get("user", "root")
        if "password" in db:
            data["db_password"] = db.get("password", "")
        if db.get("database"):
            data["db_name"] = db.get("database", "fajos_central")
    if parser.has_section("server"):
        srv = parser["server"]
        if srv.get("host"):
            data["app_host"] = srv.get("host", "0.0.0.0")
        if srv.get("port"):
            try:
                data["app_port"] = int(srv.get("port", "8000"))
            except ValueError:
                pass
        if "debug" in srv:
            data["debug"] = srv.get("debug", "true").lower() in ("1", "true", "yes")
        if "force_https" in srv:
            data["force_https"] = srv.get("force_https", "false").lower() in ("1", "true", "yes")
        if srv.get("ssl_certfile"):
            data["ssl_certfile"] = srv.get("ssl_certfile")
        if srv.get("ssl_keyfile"):
            data["ssl_keyfile"] = srv.get("ssl_keyfile")
    return data


def save_database_config(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    app_host: str = "0.0.0.0",
    app_port: int = 8000,
    debug: bool = True,
) -> Path:
    """Guarda (o crea) config.ini con los datos de conexión."""
    parser = configparser.ConfigParser()
    if CONFIG_INI.exists():
        parser.read(CONFIG_INI, encoding="utf-8")
    if not parser.has_section("database"):
        parser.add_section("database")
    if not parser.has_section("server"):
        parser.add_section("server")
    parser.set("database", "host", host)
    parser.set("database", "port", str(port))
    parser.set("database", "user", user)
    parser.set("database", "password", password)
    parser.set("database", "database", database)
    parser.set("server", "host", app_host)
    parser.set("server", "port", str(app_port))
    parser.set("server", "debug", "true" if debug else "false")
    with open(CONFIG_INI, "w", encoding="utf-8") as f:
        f.write("; Fajos Central — configuración local (no subir a Git)\n")
        parser.write(f)
    # Invalidar caché de settings
    get_settings.cache_clear()
    return CONFIG_INI


def load_ini_database() -> dict:
    """Para el launcher / UI: lee valores actuales de BD."""
    defaults = {
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "fajos_central",
    }
    ini = _read_ini()
    return {
        "host": ini.get("db_host", defaults["host"]),
        "port": ini.get("db_port", defaults["port"]),
        "user": ini.get("db_user", defaults["user"]),
        "password": ini.get("db_password", defaults["password"]),
        "database": ini.get("db_name", defaults["database"]),
    }


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="FAJOS_",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "fajos_central"

    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    secret_key: str = "dev-secret-change-me"

    # HTTPS (opcional en red local; certificados autofirmados)
    force_https: bool = False
    ssl_certfile: str = ""
    ssl_keyfile: str = ""

    export_dir: Path = BASE_DIR / "exports"
    log_dir: Path = BASE_DIR / "logs"

    @property
    def db_config(self) -> dict:
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
            "autocommit": True,
        }


@lru_cache
def get_settings() -> Settings:
    ini_defaults = _read_ini()
    # Variables de entorno y .env tienen prioridad sobre ini vía pydantic;
    # aplicamos ini solo donde no haya env.
    for key, val in ini_defaults.items():
        env_key = f"FAJOS_{key.upper()}"
        if env_key not in os.environ and key not in os.environ:
            # Pydantic lee FAJOS_DB_HOST etc.
            os.environ.setdefault(f"FAJOS_{key.upper()}", str(val))
    # Mapear nombres ini → env FAJOS_*
    mapping = {
        "db_host": "FAJOS_DB_HOST",
        "db_port": "FAJOS_DB_PORT",
        "db_user": "FAJOS_DB_USER",
        "db_password": "FAJOS_DB_PASSWORD",
        "db_name": "FAJOS_DB_NAME",
        "app_host": "FAJOS_APP_HOST",
        "app_port": "FAJOS_APP_PORT",
        "debug": "FAJOS_DEBUG",
        "force_https": "FAJOS_FORCE_HTTPS",
        "ssl_certfile": "FAJOS_SSL_CERTFILE",
        "ssl_keyfile": "FAJOS_SSL_KEYFILE",
    }
    for key, env_name in mapping.items():
        if key in ini_defaults and env_name not in os.environ:
            os.environ[env_name] = str(ini_defaults[key]).lower() if key == "debug" else str(ini_defaults[key])
    return Settings()


settings = get_settings()
