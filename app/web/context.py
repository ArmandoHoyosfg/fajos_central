"""Contexto seguro para plantillas Jinja (sin romper estructuras anidadas)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def to_template_value(value: Any) -> Any:
    """
    Normaliza valores para Jinja:
    - Decimal → float
    - date/datetime → iso str
    - dict/list → recursivo (NO convertir dict anidados a str)
    - resto se deja o se str()
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): to_template_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_template_value(v) for v in value]
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8", errors="replace")
        except Exception:
            return str(value)
    # objetos tipo Row / mapping
    if hasattr(value, "keys") and hasattr(value, "__getitem__"):
        try:
            return {str(k): to_template_value(value[k]) for k in value.keys()}
        except Exception:
            pass
    return str(value)


def build_template_context(request, **kwargs) -> dict[str, Any]:
    """Une common_template_context + kwargs normalizados + request."""
    from app.api.deps import common_template_context

    extra: dict[str, Any] = {}
    for k, v in kwargs.items():
        try:
            extra[str(k)] = to_template_value(v)
        except Exception:
            try:
                extra[str(k)] = str(v)
            except Exception:
                extra[str(k)] = None
    data = common_template_context(extra if extra else None)
    if not isinstance(data, dict):
        data = {}
    data["request"] = request
    return data
