"""Tests unitarios del runner de migraciones (sin BD)."""
from app.db.migrate import _split_statements, _list_scripts, SKIP_PREFIXES


def test_split_statements_ignora_comentarios():
    sql = """
    -- comentario
    CREATE TABLE IF NOT EXISTS foo (id INT);
    ALTER TABLE foo ADD COLUMN IF NOT EXISTS bar INT;
    """
    parts = _split_statements(sql)
    assert len(parts) == 2
    assert "CREATE TABLE" in parts[0]
    assert "ALTER TABLE" in parts[1]


def test_list_scripts_skips_000():
    for p in _list_scripts():
        assert not any(p.name.startswith(s) for s in SKIP_PREFIXES)
