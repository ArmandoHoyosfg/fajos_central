"""Validaciones orientativas al crear/editar folio (multi-trabajador permitido)."""
from __future__ import annotations

from typing import Any

from app.db.connection import get_db


class FolioValidators:
    def __init__(self, db=None):
        self.db = db or get_db()

    def contexto_folio(
        self,
        folio: str,
        *,
        semana_id: int | None = None,
        trabajador_id: int | None = None,
        nombre: str | None = None,
        ubic: int | None = None,
    ) -> dict[str, Any]:
        """Quiénes llevan el folio, si está cerrado, avisos (sin bloquear multi-trabajador)."""
        folio = (folio or "").strip()
        avisos: list[dict] = []
        portadores: list[dict] = []
        if not folio:
            return {"ok": False, "avisos": [], "portadores": [], "existe": False}

        with self.db.cursor() as cur:
            # Portadores en semana actual (o global reciente)
            if semana_id:
                cur.execute(
                    """
                    SELECT id, nombre, ubic, trabajador_id, material, modelo, tarifa_gr,
                           COALESCE(terminado, 0) AS terminado,
                           COALESCE(cerrado, 0) AS cerrado,
                           COALESCE(total_gramos, 0) AS total_gramos
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) = UPPER(%s) AND semana_id = %s
                    ORDER BY id
                    """,
                    (folio, int(semana_id)),
                )
            else:
                cur.execute(
                    """
                    SELECT id, nombre, ubic, trabajador_id, material, modelo, tarifa_gr,
                           COALESCE(terminado, 0) AS terminado,
                           COALESCE(cerrado, 0) AS cerrado,
                           COALESCE(total_gramos, 0) AS total_gramos, semana_id
                    FROM produccion_plata
                    WHERE UPPER(TRIM(folio)) = UPPER(%s)
                    ORDER BY id DESC LIMIT 20
                    """,
                    (folio,),
                )
            rows = [dict(r) for r in (cur.fetchall() or [])]

        for r in rows:
            portadores.append({
                "prod_id": r.get("id"),
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "trabajador_id": r.get("trabajador_id"),
                "material": r.get("material"),
                "modelo": r.get("modelo"),
                "tarifa_gr": float(r["tarifa_gr"]) if r.get("tarifa_gr") is not None else None,
                "terminado": bool(r.get("terminado")),
                "cerrado": bool(r.get("cerrado")),
                "total_gramos": float(r.get("total_gramos") or 0),
                "semana_id": r.get("semana_id"),
            })

        activos = [p for p in portadores if not p["terminado"] and not p["cerrado"]]
        cerrados = [p for p in portadores if p["terminado"] or p["cerrado"]]

        # Mismo trabajador + mismo folio + misma semana → ya existe su línea
        if trabajador_id or (nombre is not None and ubic is not None):
            for p in portadores:
                same = False
                if trabajador_id and p.get("trabajador_id") and int(p["trabajador_id"]) == int(trabajador_id):
                    same = True
                elif nombre and str(p.get("nombre") or "").strip().upper() == str(nombre).strip().upper():
                    if ubic is None or int(p.get("ubic") or -1) == int(ubic):
                        same = True
                if same and semana_id:
                    avisos.append({
                        "nivel": "warn",
                        "codigo": "ya_tiene_linea",
                        "texto": f"Este trabajador ya tiene línea del folio {folio} en la semana (material {p.get('material') or '—'}).",
                    })
                    break

        if len(activos) >= 1:
            nombres = ", ".join(f"{p['nombre']} ({p['ubic']})" for p in activos[:5])
            avisos.append({
                "nivel": "info",
                "codigo": "compartido",
                "texto": f"Folio compartido ahora por {len(activos)} trabajador(es): {nombres}. Está permitido.",
            })

        if cerrados and not activos:
            avisos.append({
                "nivel": "info",
                "codigo": "reactivar",
                "texto": f"El folio {folio} estaba cerrado/terminado; al guardar se puede reabrir en esta semana.",
            })

        # Materiales distintos en el mismo folio (DOL vs AG3 es normal)
        mats = {str(p.get("material") or "").upper() for p in portadores if p.get("material")}
        if len(mats) > 1:
            avisos.append({
                "nivel": "info",
                "codigo": "multi_material",
                "texto": "Este folio ya se usa con varios materiales: " + ", ".join(sorted(mats)) + ".",
            })

        return {
            "ok": True,
            "existe": bool(portadores),
            "portadores": portadores,
            "n_activos": len(activos),
            "n_cerrados": len(cerrados),
            "avisos": avisos,
        }

    def similares(self, folio: str, limit: int = 5) -> list[dict]:
        """Folios parecidos (mismo prefijo + longitud cercana) para detectar typos — no genera números."""
        import re
        folio = (folio or "").strip()
        if len(folio) < 3:
            return []
        m = re.match(r"^([A-Za-z]{1,8}-)(.*)$", folio)
        if not m:
            return []
        pref, rest = m.group(1).upper(), m.group(2)
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT folio FROM produccion_plata
                WHERE UPPER(TRIM(folio)) LIKE %s
                  AND UPPER(TRIM(folio)) <> UPPER(%s)
                ORDER BY id DESC LIMIT 40
                """,
                (pref + "%", folio),
            )
            cands = [str(r["folio"]).strip() for r in (cur.fetchall() or []) if r.get("folio")]
        # Distancia simple: misma longitud o ±1 y muchos caracteres en común
        scored = []
        for c in cands:
            cu = c.upper()
            if not cu.startswith(pref):
                continue
            cr = cu[len(pref):]
            if abs(len(cr) - len(rest)) > 2:
                continue
            common = sum(1 for a, b in zip(rest.upper(), cr) if a == b)
            score = common - abs(len(cr) - len(rest))
            if score >= max(1, len(rest) - 2):
                scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [{"folio": f, "parecido": True} for _, f in scored[:limit]]
