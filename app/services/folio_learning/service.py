"""Orquestador: sugerencias al crear/editar folio sin generar el número."""
from __future__ import annotations

from typing import Any

from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repos.produccion import ProduccionRepo
from app.services.folio_learning.prefix_patterns import PrefixPatternLearner, extraer_prefijo
from app.services.folio_learning.price_confidence import PriceConfidence
from app.services.folio_learning.production_patterns import ProductionPatterns
from app.services.folio_learning.worker_history import WorkerHistory
from app.services.folio_learning.validators import FolioValidators

logger = get_logger(__name__)


class FolioLearningService:
    def __init__(self, db=None):
        self.db = db or get_db()
        self.prod = ProduccionRepo(self.db)
        self.prefix = PrefixPatternLearner(self.db)
        self.prices = PriceConfidence(self.db)
        self.patterns = ProductionPatterns(self.db)
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
                # Preferir historial con modelo y gramos reales
                meta = self.patterns.meta_folio_completa(folio) or {}
                if not meta:
                    meta = self.prod.meta_por_folio(folio, semana_id=semana_id) or {}
                if meta:
                    if meta.get("modelo"):
                        out["modelo"] = meta.get("modelo")
                    if meta.get("material"):
                        out["material"] = meta.get("material")
                    if meta.get("tarifa_gr") is not None:
                        out["tarifa_gr"] = meta.get("tarifa_gr")
                    out["fuente"] = meta.get("fuente") or "folio_existente"
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
                # Modelos frecuentes para este material (ayuda cuando no los capturan)
                mods = self.patterns.modelos_por_material(mat_eff, limit=5)
                out["modelos_sugeridos"] = mods
                if rellenar_vacios and not out.get("modelo") and mods:
                    top = mods[0]
                    # Solo auto-rellenar si hay señal clara (>=25% o >=5 usos)
                    if top.get("veces", 0) >= 5 or top.get("confianza", 0) >= 0.25:
                        out["modelo"] = top.get("modelo")
                        out["modelo_sugerido"] = top
                        if not out.get("fuente"):
                            out["fuente"] = "modelo_material"
        except Exception:
            logger.debug("precio/modelo falló", exc_info=True)

        try:
            if trabajador_id or nombre:
                wh = self.workers.resumen(
                    trabajador_id=trabajador_id,
                    nombre=nombre,
                    ubic=ubic,
                )
                out["trabajador"] = wh
                ult = self.patterns.ultimo_del_trabajador(
                    trabajador_id=trabajador_id, nombre=nombre, ubic=ubic
                )
                if rellenar_vacios:
                    if not out.get("material") and (ult or {}).get("material"):
                        out["material"] = ult["material"]
                        out["fuente"] = "trabajador_reciente"
                    elif not out.get("material") and wh.get("material_habitual"):
                        out["material"] = wh["material_habitual"]
                        out["fuente"] = "trabajador_habitual"
                    if not out.get("modelo") and (ult or {}).get("modelo"):
                        out["modelo"] = ult["modelo"]
                    elif not out.get("modelo") and wh.get("modelo_habitual"):
                        out["modelo"] = wh["modelo_habitual"]
                    if out.get("tarifa_gr") is None and (ult or {}).get("tarifa_gr") is not None:
                        out["tarifa_gr"] = ult["tarifa_gr"]
        except Exception:
            logger.debug("worker history falló", exc_info=True)

        return out
