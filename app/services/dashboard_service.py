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

    @staticmethod
    def _norm(s: str) -> str:
        """Minúsculas, sin acentos, colapsa espacios (para búsqueda flexible)."""
        import unicodedata
        s = (s or "").strip().lower()
        s = "".join(
            c for c in unicodedata.normalize("NFD", s)
            if unicodedata.category(c) != "Mn"
        )
        return " ".join(s.split())

    @staticmethod
    def _tokens(q: str) -> list[str]:
        n = DashboardService._norm(q)
        # también versión sin espacios para "tigre02" ≈ "tigre 02"
        parts = [t for t in n.split() if t]
        return parts

    @staticmethod
    def _match_tokens(text: str, tokens: list[str]) -> bool:
        if not tokens:
            return False
        hay = DashboardService._norm(text)
        hay_ns = hay.replace(" ", "")
        for t in tokens:
            if t in hay or t.replace(" ", "") in hay_ns:
                continue
            return False
        return True

    def buscar(self, q: str) -> dict:
        """Búsqueda amplia: trabajadores, folios (todas las semanas), trabajos, semanas.

        - Tokens: «tigre 02» y «tigre02» coinciden.
        - Folios en **todas** las semanas (no solo 12).
        - Agrupa historial del folio (gramos acumulados, últimas semanas).
        - Material / modelo / ubic también cuentan.
        """
        q = (q or "").strip()
        empty = {"trabajadores": [], "semanas": [], "folios": [], "trabajos": [], "db_ok": check_db()}
        if not q:
            return empty
        if not check_db():
            empty["db_ok"] = False
            return empty

        tokens = self._tokens(q)
        ql = self._norm(q)
        ql_ns = ql.replace(" ", "")

        # —— Trabajadores (BD + filtro token extra)
        trab_raw = self.trabajadores.listar(solo_activos=False, busqueda=q) or []
        # Ampliar: si pocos resultados, traer todos activos y filtrar en Python
        if len(trab_raw) < 3:
            try:
                todos_t = self.trabajadores.listar(solo_activos=False) or []
            except Exception:
                todos_t = trab_raw
            extra = []
            for t in todos_t:
                blob = " ".join([
                    str(t.get("nombre_mostrar") or ""),
                    str(t.get("nombre_completo") or ""),
                    str(t.get("ubic") or ""),
                    str(t.get("puesto") or ""),
                    str(t.get("tipo") or ""),
                ])
                if self._match_tokens(blob, tokens) or ql_ns in self._norm(blob).replace(" ", ""):
                    extra.append(t)
            # merge by id
            seen_id = {int(t["id"]) for t in trab_raw if t.get("id") is not None}
            for t in extra:
                tid = t.get("id")
                if tid is not None and int(tid) not in seen_id:
                    trab_raw.append(t)
                    seen_id.add(int(tid))
        trab = trab_raw[:50]

        # —— Semanas
        todas = self.semanas.listar() or []
        sem = [
            s for s in todas
            if self._match_tokens(
                " ".join([
                    str(s.get("codigo") or ""),
                    str(s.get("notas") or ""),
                    str(s.get("fecha_inicio") or ""),
                    str(s.get("fecha_fin") or ""),
                ]),
                tokens,
            )
            or ql in self._norm(str(s.get("codigo") or ""))
        ]

        # —— Folios en TODAS las semanas (agregados)
        folio_agg: dict[str, dict] = {}
        try:
            from app.db.repository import ProduccionRepo
            prod = ProduccionRepo()
            for s in todas:
                try:
                    rows = prod.listar_por_semana(int(s["id"]), incluir_terminados=True) or []
                except Exception:
                    continue
                for r in rows:
                    folio = (r.get("folio") or "").strip()
                    if not folio:
                        continue
                    blob = " ".join([
                        folio,
                        str(r.get("nombre") or ""),
                        str(r.get("ubic") or ""),
                        str(r.get("material") or ""),
                        str(r.get("modelo") or ""),
                    ])
                    if not (
                        self._match_tokens(blob, tokens)
                        or ql_ns in self._norm(folio).replace(" ", "")
                        or ql in self._norm(folio)
                    ):
                        continue
                    key = folio.upper()
                    g = float(r.get("total_gramos") or 0)
                    if g <= 0:
                        g = sum(
                            float(r.get(c) or 0)
                            for c in (
                                "gm_sab", "gm_dom", "gm_lun", "gm_mar",
                                "gm_mie", "gm_jue", "gm_vie",
                            )
                        )
                    slot = folio_agg.setdefault(key, {
                        "folio": folio,
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "material": r.get("material"),
                        "modelo": r.get("modelo"),
                        "semana": s.get("codigo"),
                        "semana_id": s.get("id"),
                        "gramos": 0.0,
                        "n_semanas": 0,
                        "semanas_list": [],
                    })
                    slot["gramos"] = float(slot["gramos"]) + g
                    slot["n_semanas"] = int(slot["n_semanas"]) + 1
                    if s.get("codigo") and s.get("codigo") not in slot["semanas_list"]:
                        slot["semanas_list"].append(s.get("codigo"))
                    # guardar la semana más reciente como enlace
                    slot["semana"] = s.get("codigo")
                    slot["semana_id"] = s.get("id")
                    slot["nombre"] = r.get("nombre") or slot["nombre"]
                    slot["ubic"] = r.get("ubic") if r.get("ubic") is not None else slot["ubic"]
                    if r.get("material"):
                        slot["material"] = r.get("material")
                    if r.get("modelo"):
                        slot["modelo"] = r.get("modelo")
        except Exception:
            folio_agg = {}

        folios = []
        for slot in folio_agg.values():
            g = float(slot["gramos"])
            slot["gramos"] = round(g, 1) if g else ""
            slot["semanas_txt"] = ", ".join(slot.get("semanas_list") or [])[:80]
            folios.append(slot)
        folios.sort(key=lambda x: (-float(x["gramos"] or 0), str(x.get("folio") or "")))
        folios = folios[:60]

        # —— Trabajos (catálogo de folios activos/cerrados)
        trabajos = []
        try:
            from app.db.repository import TrabajosRepo
            tr_repo = TrabajosRepo()
            for t in tr_repo.listar(solo_activos=False) or []:
                blob = " ".join([
                    str(t.get("folio") or ""),
                    str(t.get("nombre") or t.get("nombre_mostrar") or ""),
                    str(t.get("ubic") or ""),
                    str(t.get("material") or ""),
                    str(t.get("modelo") or ""),
                ])
                if self._match_tokens(blob, tokens) or ql_ns in self._norm(str(t.get("folio") or "")).replace(" ", ""):
                    trabajos.append(t)
                    if len(trabajos) >= 40:
                        break
        except Exception:
            trabajos = []

        # Complemento ortográfico si hay pocas coincidencias
        spell_hints: list[str] = []
        spell_status = {}
        try:
            from app.services.spell_service import get_spell_service
            sp = get_spell_service()
            spell_status = sp.status()
            total_hits = len(trab) + len(folios) + len(trabajos) + len(sem)
            if total_hits < 3 and tokens:
                for tok in tokens[:3]:
                    if len(tok) < 3:
                        continue
                    sug = sp.suggest(tok, limit=5)
                    for s in sug.get("suggestions") or []:
                        if s.lower() != tok and s not in spell_hints:
                            spell_hints.append(s)
        except Exception:
            spell_hints = []

        return {
            "trabajadores": trab,
            "semanas": sem[:30],
            "folios": folios,
            "trabajos": trabajos,
            "db_ok": True,
            "spell_hints": spell_hints[:8],
            "spell_status": spell_status,
        }

