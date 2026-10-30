"""Plantillas por prefijo de folio (F-, ST-, P-…) a partir del historial real."""
from __future__ import annotations

from collections import Counter
from typing import Any

from app.db.connection import get_db


def extraer_prefijo(folio: str) -> str | None:
    """ST-248 → ST- ; F-019-1 → F- ; vacío si no hay patrón letras+guion."""
    import re
    s = (folio or "").strip().upper()
    m = re.match(r"^([A-Z]{1,8})-", s)
    return (m.group(1) + "-") if m else None


class PrefixPatternLearner:
    def __init__(self, db=None):
        self.db = db or get_db()

    def plantilla(self, folio: str, limit_semanas: int = 16) -> dict[str, Any] | None:
        """Moda de material/modelo/tarifa para el prefijo del folio."""
        pref = extraer_prefijo(folio)
        if not pref:
            return None
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT p.material, p.modelo, p.tarifa_gr
                FROM produccion_plata p
                INNER JOIN (
                    SELECT id FROM semanas ORDER BY fecha_inicio DESC LIMIT %s
                ) s ON s.id = p.semana_id
                WHERE UPPER(TRIM(p.folio)) LIKE %s
                  AND p.material IS NOT NULL AND TRIM(p.material) <> ''
                ORDER BY p.id DESC
                LIMIT 400
                """,
                (int(limit_semanas), pref + "%"),
            )
            rows = cur.fetchall() or []
        if not rows:
            return None
        mats = Counter(str(r.get("material") or "").strip().upper() for r in rows if r.get("material"))
        mods = Counter(str(r.get("modelo") or "").strip() for r in rows if r.get("modelo"))
        tars = Counter()
        for r in rows:
            if r.get("tarifa_gr") is None:
                continue
            try:
                tars[round(float(r["tarifa_gr"]), 2)] += 1
            except (TypeError, ValueError):
                pass
        n = len(rows)
        mat, mat_n = mats.most_common(1)[0] if mats else (None, 0)
        mod, mod_n = mods.most_common(1)[0] if mods else (None, 0)
        tar, tar_n = tars.most_common(1)[0] if tars else (None, 0)
        return {
            "prefijo": pref,
            "material": mat,
            "material_confianza": round(mat_n / n, 2) if n else 0,
            "modelo": mod,
            "modelo_confianza": round(mod_n / n, 2) if n else 0,
            "tarifa_gr": float(tar) if tar is not None else None,
            "tarifa_confianza": round(tar_n / n, 2) if n and tar is not None else 0,
            "muestras": n,
            "fuente": "prefijo_historial",
            "detalle": f"En {pref}* (últimas {limit_semanas} sem.): {mat or '—'} · {mod or '—'} · ${tar if tar is not None else '—'}",
        }

    def hermanos(self, folio: str, limit: int = 8) -> list[dict]:
        """Otros folios del mismo prefijo usados recientemente (ayuda, no genera números)."""
        pref = extraer_prefijo(folio)
        if not pref:
            return []
        folio_u = (folio or "").strip().upper()
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT p.folio, p.material, p.modelo, p.tarifa_gr,
                       COUNT(DISTINCT p.semana_id) AS n_semanas,
                       MAX(p.id) AS max_id
                FROM produccion_plata p
                WHERE UPPER(TRIM(p.folio)) LIKE %s
                  AND UPPER(TRIM(p.folio)) <> %s
                GROUP BY p.folio, p.material, p.modelo, p.tarifa_gr
                ORDER BY max_id DESC
                LIMIT %s
                """,
                (pref + "%", folio_u, int(limit)),
            )
            rows = cur.fetchall() or []
        out = []
        seen = set()
        for r in rows:
            f = str(r.get("folio") or "").strip()
            if not f or f.upper() in seen:
                continue
            seen.add(f.upper())
            out.append({
                "folio": f,
                "material": r.get("material"),
                "modelo": r.get("modelo"),
                "tarifa_gr": float(r["tarifa_gr"]) if r.get("tarifa_gr") is not None else None,
            })
        return out[:limit]
