"""Extensiones Jinja2 centralizadas (un solo punto de registro)."""
from __future__ import annotations

from markupsafe import Markup


def tojson_safe(value):
    """tojson que soporta Decimal/date/Path (evita TypeError en templates)."""
    from app.core.jsonutil import dumps_safe
    return Markup(dumps_safe(value, ensure_ascii=False))


def _json_dumps_policy(obj, **kwargs):
    from app.core.jsonutil import dumps_safe
    return dumps_safe(obj, **kwargs)


def register_filters(templates) -> None:
    """
    Registra filtros/políticas en una instancia Jinja2Templates.
    Idempotente: se puede llamar más de una vez sin daño.
    """
    env = templates.env
    env.filters["tojson"] = tojson_safe
    env.policies["json.dumps_function"] = _json_dumps_policy
