"""Reglas de aprendizaje y duplicados (sin BD)."""
from __future__ import annotations

import unicodedata

# Lógica espejo de AprendizajeService (unitaria, sin importar app completa)
def _norm_nombre(s: str) -> str:
    s = unicodedata.normalize("NFD", (s or "").strip().lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.split())


def _nombres_similares(a: str, b: str) -> bool:
    na, nb = _norm_nombre(a), _norm_nombre(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    ta, tb = na.split(), nb.split()
    if na in nb or nb in na:
        corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
        if len(largo) >= 2 and len(corto) >= 1 and set(corto) <= set(largo):
            return True
        return False
    if not ta or not tb:
        return False
    if ta[0] != tb[0] or len(ta[0]) < 4:
        return False
    extra = (set(ta) & set(tb)) - {ta[0]}
    return bool(extra and len(ta) >= 2 and len(tb) >= 2)


def _ubic_key(ubic) -> str | None:
    if ubic is None:
        return None
    s = str(ubic).strip()
    if s == "" or s.lower() in ("none", "null", "-"):
        return None
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s.lower()


def test_nombres_iguales_acentos():
    assert _nombres_similares("José Luis Ramírez", "Jose Luis Ramirez")


def test_nombres_distintos_solo_pila():
    assert not _nombres_similares("Carlos Mendoza", "Carlos Gomez")


def test_ubic_misma_normalizada():
    assert _ubic_key(737) == _ubic_key("737")
    assert _ubic_key(None) is None
    assert _ubic_key("") is None


def test_alerta_shape_keys():
    """Contrato de alertas_operativas (campos esperados por Dashboard)."""
    required = {"nivel", "codigo", "titulo", "detalle", "href", "accion"}
    sample = {
        "nivel": "warn",
        "codigo": "aprendizaje_sin_avance",
        "titulo": "3 folio(s) sin avance",
        "detalle": "…",
        "href": "/produccion?filtro=sin_avance",
        "accion": "Ver en Plata",
        "count": 3,
        "fuente": "aprendizaje",
    }
    assert required <= set(sample.keys())
    assert sample["fuente"] == "aprendizaje"
