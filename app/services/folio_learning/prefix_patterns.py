"""Plantillas por prefijo de folio (F-, ST-, P-…) a partir del historial real."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from app.db.connection import get_db


def extraer_prefijo(folio: str) -> str | None:
    """ST-248 → ST- ; F-019-1 → F- ; vacío si no hay patrón letras+guion."""
    s = (folio or "").strip().upper()
    m = re.match(r"^([A-Z]{1,8})-", s)
    return (m.group(1) + "-") if m else None


class PrefixPatternLearner:
    def __init__(self, db=None):
        self.db = db or get_db()

    def plantilla(self, folio: str, limit_rows: int = 400) -> dict[str, Any] | None:
        """Moda de material/modelo/tarifa para el prefijo del folio."""
        pref = extraer_prefijo(folio)
        if not pref:
            return None
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT material, modelo, tarifa_gr
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) LIKE %s
                      AND material IS NOT NULL AND TRIM(material) <> ''
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (pref + "%", int(limit_rows)),
                )
                rows = cur.fetchall() or []
        except Exception:
            return None
        if not rows:
            return None
        mats = Counter(str(r.get("material") or "").strip().upper() for r in rows if r.get("material"))
        mods = Counter(str(r.get("modelo") or "").strip() for r in rows if r.get("modelo"))
        tars: Counter = Counter()
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
            "detalle": f"En {pref}* : {mat or '—'} · {mod or '—'} · ${tar if tar is not None else '—'}",
        }

    def hermanos(self, folio: str, limit: int = 8) -> list[dict]:
        """Otros folios del mismo prefijo usados recientemente (ayuda, no genera números)."""
        pref = extraer_prefijo(folio)
        if not pref:
            return []
        folio_u = (folio or "").strip().upper()
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT folio, material, modelo, tarifa_gr, MAX(id) AS max_id
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) LIKE %s
                      AND UPPER(TRIM(folio)) <> %s
                    GROUP BY folio, material, modelo, tarifa_gr
                    ORDER BY max_id DESC
                    LIMIT %s
                    """,
                    (pref + "%", folio_u, int(limit) * 3),
                )
                rows = cur.fetchall() or []
        except Exception:
            return []
        out = []
        seen: set[str] = set()
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
            if len(out) >= limit:
                break
        return out
