"""Orquestador: sugerencias al crear/editar folio sin generar el número."""
from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repos.produccion import ProduccionRepo
from app.services.folio_learning.prefix_patterns import PrefixPatternLearner, extraer_prefijo
from app.services.folio_learning.price_confidence import PriceConfidence
from app.services.folio_learning.worker_history import WorkerHistory
from app.services.folio_learning.validators import FolioValidators

logger = get_logger(__name__)


class FolioLearningService:
    def __init__(self, db=None):
        self.db = db or get_db()
        self.prod = ProduccionRepo(self.db)
        self.prefix = PrefixPatternLearner(self.db)
        self.prices = PriceConfidence(self.db)
        self.workers = WorkerHistory(self.db)
        self.validators = FolioValidators(self.db)

    def sugerir_formulario(
        self,
        *,
        folio: str = "",
        material: str = "",
        modelo: str = "",
        semana_id: int | None = None,
        trabajador_id: int | None = None,
        nombre: str | None = None,
        ubic: int | None = None,
        rellenar_vacios: bool = True,
    ) -> dict[str, Any]:
        """
        Respuesta unificada para UI de alta/edición.
        No inventa números de folio. Fallos parciales no tumban el endpoint.
        """
        folio = (folio or "").strip()
        material = (material or "").strip()
        modelo = (modelo or "").strip()
        out: dict[str, Any] = {
            "ok": True,
            "folio": folio,
            "prefijo": extraer_prefijo(folio),
            "modelo": None,
            "material": None,
            "tarifa_gr": None,
            "tarifa_detalle": None,
            "tarifa_confianza": None,
            "fuente": None,
            "avisos": [],
            "portadores": [],
            "hermanos": [],
            "similares": [],
            "trabajador": None,
            "plantilla_prefijo": None,
            "existe": False,
        }

        # Solo prefijo (ST-) → plantilla + hermanos, sin meta exacta
        solo_prefijo = bool(out["prefijo"] and folio.upper() == out["prefijo"])

        try:
            if folio and not solo_prefijo:
                meta = self.prod.meta_por_folio(folio, semana_id=semana_id) or {}
                if meta:
                    out["modelo"] = meta.get("modelo")
                    out["material"] = meta.get("material")
                    out["tarifa_gr"] = meta.get("tarifa_gr")
                    out["fuente"] = "folio_existente"
        except Exception:
            logger.debug("meta_por_folio falló", exc_info=True)

        try:
            if folio and not solo_prefijo:
                ctx = self.validators.contexto_folio(
                    folio,
                    semana_id=semana_id,
                    trabajador_id=trabajador_id,
                    nombre=nombre,
                    ubic=ubic,
                )
                out["portadores"] = ctx.get("portadores") or []
                out["avisos"].extend(ctx.get("avisos") or [])
                out["existe"] = bool(ctx.get("existe"))
                if not ctx.get("existe"):
                    out["similares"] = self.validators.similares(folio)
        except Exception:
            logger.debug("contexto_folio falló", exc_info=True)

        try:
            if folio:
                plant = self.prefix.plantilla(folio)
                out["plantilla_prefijo"] = plant
                if plant and rellenar_vacios:
                    if not out.get("material") and plant.get("material"):
                        out["material"] = plant["material"]
                        out["fuente"] = out["fuente"] or "prefijo_historial"
                    if not out.get("modelo") and plant.get("modelo"):
                        out["modelo"] = plant["modelo"]
                    if out.get("tarifa_gr") is None and plant.get("tarifa_gr") is not None:
                        out["tarifa_gr"] = plant["tarifa_gr"]
                        out["tarifa_confianza"] = plant.get("tarifa_confianza")
                        out["tarifa_detalle"] = plant.get("detalle")
                out["hermanos"] = self.prefix.hermanos(folio)
        except Exception:
            logger.debug("plantilla prefijo falló", exc_info=True)

        try:
            mat_eff = material or out.get("material") or ""
            mod_eff = modelo or out.get("modelo") or None
            if mat_eff:
                price = self.prices.sugerir(mat_eff, mod_eff)
                if price:
                    if out.get("tarifa_gr") is None:
                        out["tarifa_gr"] = price["tarifa_gr"]
                        out["fuente"] = price.get("fuente")
                    out["tarifa_confianza"] = price.get("confianza")
                    out["tarifa_detalle"] = price.get("detalle")
                    out["tarifa_alternativas"] = price.get("alternativas")
        except Exception:
            logger.debug("precio falló", exc_info=True)

        try:
            if trabajador_id or nombre:
                wh = self.workers.resumen(
                    trabajador_id=trabajador_id,
                    nombre=nombre,
                    ubic=ubic,
                )
                out["trabajador"] = wh
                if rellenar_vacios and not folio:
                    if not out.get("material") and wh.get("material_habitual"):
                        out["material"] = wh["material_habitual"]
                        out["fuente"] = "trabajador_habitual"
                    if not out.get("modelo") and wh.get("modelo_habitual"):
                        out["modelo"] = wh["modelo_habitual"]
        except Exception:
            logger.debug("worker history falló", exc_info=True)

        return out
