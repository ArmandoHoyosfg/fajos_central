"""Tests de configuración."""
from app.core.config import Settings


def test_default_settings():
    s = Settings(
        _env_file=None,  # no cargar .env real en test
        db_host="localhost",
        db_name="fajos_central",
    )
    assert s.db_name == "fajos_central"
    assert s.db_config["database"] == "fajos_central"
    assert s.app_port == 8000
