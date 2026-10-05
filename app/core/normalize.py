"""Normalización de nombres (collation-safe)."""
from __future__ import annotations

import unicodedata


def fold_name(name: str) -> str:
    """Clave comparable con utf8mb4_unicode_ci: sin acentos, minúsculas."""
    if not name:
        return ""
    nfkd = unicodedata.normalize("NFKD", str(name).strip())
    no_acc = "".join(c for c in nfkd if not unicodedata.combining(c))
    return no_acc.casefold().strip()


def canonical_name(name: str) -> str:
    """Nombre para mostrar: espacios colapsados, sin extremos."""
    if not name:
        return ""
    return " ".join(str(name).strip().split())


def names_match(a: str, b: str) -> bool:
    return fold_name(a) == fold_name(b)
