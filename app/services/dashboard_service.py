"""Servicio de dashboard."""
from __future__ import annotations

from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repository import DashboardRepo, SemanasRepo, TrabajadoresRepo
from app.core.exceptions import DatabaseError

logger = get_logger(__name__)


def check_db() -> bool:
    try:
        db = get_db()
        with db.cursor() as cur:
            cur.execute("SELECT 1 AS ok")
            cur.fetchone()
        return True
    except Exception as e:
        logger.warning("Health BD falló: %s", e)
        return False


class DashboardService:
    def __init__(self) -> None:
        self.repo = DashboardRepo()
        self.semanas = SemanasRepo()
        self.trabajadores = TrabajadoresRepo()

    def get_dashboard(self) -> dict:
        db_ok = check_db()
        if not db_ok:
            return {
                "db_ok": False,
                "kpis": {
                    "trabajadores_activos": 0,
                    "trabajadores_plt": 0,
                    "total_semanas": 0,
                    "total_gramos_historico": 0,
                    "total_efectivo_historico": 0,
                    "nomina_total_acumulada": 0,
                },
                "ultimas_semanas": [],
            }
        try:
            kpis = self.repo.resumen_general()
            semanas = self.repo.ultimas_semanas(8)
            return {"db_ok": True, "kpis": kpis, "ultimas_semanas": semanas}
        except DatabaseError:
            return {
                "db_ok": False,
                "kpis": {
                    "trabajadores_activos": 0,
                    "trabajadores_plt": 0,
                    "total_semanas": 0,
                    "total_gramos_historico": 0,
                    "total_efectivo_historico": 0,
                    "nomina_total_acumulada": 0,
                },
                "ultimas_semanas": [],
            }

    def buscar(self, q: str) -> dict:
        q = (q or "").strip()
        if not q:
            return {"trabajadores": [], "semanas": [], "db_ok": check_db()}
        if not check_db():
            return {"trabajadores": [], "semanas": [], "db_ok": False}
        trab = self.trabajadores.listar(solo_activos=False, busqueda=q)
        # filtrar semanas por código o notas
        todas = self.semanas.listar()
        ql = q.lower()
        sem = [
            s for s in todas
            if ql in str(s.get("codigo") or "").lower()
            or ql in str(s.get("notas") or "").lower()
            or ql in str(s.get("fecha_inicio") or "")
            or ql in str(s.get("fecha_fin") or "")
        ]
        return {"trabajadores": trab, "semanas": sem[:30], "db_ok": True}
