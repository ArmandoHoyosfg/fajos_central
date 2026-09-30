"""Instancia única de plantillas Jinja2 para la app web."""
from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.web.jinja_ext import register_filters

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
register_filters(templates)
