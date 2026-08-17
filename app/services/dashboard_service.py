"""Servicio de dashboard."""
from __future__ import annotations

from app.db.repository import DashboardRepo


class DashboardService:
    def __init__(self, repo: DashboardRepo | None = None):
        self.repo = repo or DashboardRepo()

    def get_dashboard(self) -> dict:
        general = self.repo.resumen_general()
        semanas = self.repo.ultimas_semanas(8)
        return {
            "kpis": general,
            "ultimas_semanas": semanas,
        }
