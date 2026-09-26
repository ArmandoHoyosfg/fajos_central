"""Base de repositorios y helpers SQL."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db

logger = get_logger(__name__)


class BaseRepo:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()



def _parse_fecha_sql(v):
    """Normaliza fechas de formularios a YYYY-MM-DD o None."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    # ISO
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # DD/MM/YYYY or DD-MM-YYYY
    for sep in ("/", "-"):
        parts = s.split(sep)
        if len(parts) == 3 and len(parts[2]) == 4:
            d, m, y = parts[0].zfill(2), parts[1].zfill(2), parts[2]
            if d.isdigit() and m.isdigit() and y.isdigit():
                return f"{y}-{m}-{d}"
    return s[:10]


