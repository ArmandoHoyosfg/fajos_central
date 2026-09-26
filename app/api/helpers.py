"""Helpers compartidos entre routers."""
from __future__ import annotations

from typing import Any

from fastapi import Request

from app.db.repository import TrabajadoresRepo, CatalogosRepo
from app.web.context import build_template_context
from app.web.templating import templates

__all__ = ["templates", "get_catalogos_repo", "_ctx", "_dev_page_payload", "_parse_num"]

def get_catalogos_repo():
    from app.db.repository import CatalogosRepo
    return CatalogosRepo()


from app.web.context import build_template_context, to_template_value

def _ctx(request: Request, **kwargs):
    return build_template_context(request, **kwargs)

def _dev_page_payload(repo: TrabajadoresRepo, *, action_result=None, sync_result=None, error=None):
    from app.web.debug_pages import render_debug_page
    from app.services.dashboard_service import check_db
    from app import __version__
    data: dict = {
        "mismatches": [], "sample_vela": [], "columns": [], "counts": {},
        "orphans": [], "migrations": [], "folios_duplicados": [], "semana_actual": {},
    }
    try:
        data = repo.diagnostico_sync()
    except Exception as e:
        if error is None:
            error = str(e)
    lan = "—"
    try:
        from app.core.network import lan_urls
        from app.core.config import get_settings
        s = get_settings()
        port = int(getattr(s, "app_port", 8000) or 8000)
        urls = lan_urls(port=port)
        lan = f"{urls.get('ip')}:{port}"
    except Exception:
        pass
    apr = {}
    try:
        from app.services.aprendizaje_service import AprendizajeService
        apr = AprendizajeService().resumen_aprendizaje()
    except Exception as e:
        apr = {"tabla_ok": False, "error": str(e), "folios_inactivos": [], "candidatos_dup": []}
    return render_debug_page(
        db_ok=check_db(),
        columns=data.get("columns") or [],
        mismatches=data.get("mismatches") or [],
        sample_vela=data.get("sample_vela") or [],
        meta={"version": __version__, "lan": lan},
        counts=data.get("counts") or {},
        orphans=data.get("orphans") or [],
        migrations=data.get("migrations") or [],
        folios_dup=data.get("folios_duplicados") or [],
        semana_actual=data.get("semana_actual") or {},
        aprendizaje=apr,
        sync_result=sync_result,
        action_result=action_result,
        error=error,
    )


def _parse_num(val: str | None, default=None, allow_empty_none: bool = True):
    """Convierte string de formulario a float de forma segura."""
    if val is None:
        return default
    s = str(val).strip().replace(",", ".")
    if s == "":
        return None if allow_empty_none else 0.0
    try:
        return float(s)
    except ValueError as e:
        from app.core.exceptions import ValidationAppError
        raise ValidationAppError(f"Valor numérico inválido: {val!r}") from e

