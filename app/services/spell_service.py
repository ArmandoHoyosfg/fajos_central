"""Diccionario ortográfico del sistema + vocabulario de la app (complemento).

Detecta, si existe:
  - hunspell / aspell (Linux/macOS y algunos Windows con herramientas instaladas)
  - paquete opcional ``pyspellchecker`` / ``spellchecker``
  - diccionarios del navegador vía ``spellcheck`` HTML (capa cliente)

No es obligatorio: si no hay diccionario, la app sigue igual y solo usa
el vocabulario interno (catálogos, nombres) como sugerencias de dominio.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Rutas habituales de diccionarios (es / es_MX / es_ES)
_DICT_CANDIDATES = (
    # Linux / macOS
    "/usr/share/hunspell/es_MX.dic",
    "/usr/share/hunspell/es_ES.dic",
    "/usr/share/hunspell/es.dic",
    "/usr/share/myspell/dicts/es_MX.dic",
    "/usr/share/myspell/dicts/es_ES.dic",
    "/usr/share/myspell/es_ES.dic",
    "/usr/local/share/hunspell/es_ES.dic",
    "/opt/homebrew/share/hunspell/es_ES.dic",
    # Windows: LibreOffice, OpenOffice, Hunspell portable
    r"C:\Program Files\LibreOffice\share\extensions\dict-es\es_ES.dic",
    r"C:\Program Files\LibreOffice\share\extensions\dict-es\es_MX.dic",
    r"C:\Program Files (x86)\LibreOffice\share\extensions\dict-es\es_ES.dic",
    r"C:\Program Files\LibreOffice\share\extensions\dict-es\es.dic",
    r"C:\Program Files\OpenOffice 4\share\extensions\dict-es\es_ES.dic",
    r"C:\Hunspell\es_ES.dic",
    r"C:\Hunspell\es_MX.dic",
)


class SpellService:
    """Estado del diccionario del sistema y sugerencias combinadas."""

    def status(self) -> dict[str, Any]:
        hunspell = shutil.which("hunspell")
        aspell = shutil.which("aspell")
        dict_path = self._find_dict_file()
        pyspell = self._pyspell_available()
        browser_hint = (
            "El navegador usa el diccionario del SO en campos con spellcheck=true "
            "(Chrome/Edge/Firefox respetan el idioma es si está instalado en el sistema)."
        )
        # archivo .dic cuenta aunque no haya binario hunspell
        available = bool(hunspell or aspell or dict_path or pyspell)
        engines = []
        if hunspell:
            engines.append("hunspell")
        if aspell:
            engines.append("aspell")
        if dict_path:
            engines.append(f"archivo:{Path(dict_path).name}")
        if pyspell:
            engines.append("pyspellchecker")
        engines.append("navegador/SO (HTML spellcheck)")
        return {
            "disponible": available,
            "hunspell": hunspell or None,
            "aspell": aspell or None,
            "dict_path": dict_path,
            "pyspellchecker": pyspell,
            "motores": engines,
            "idioma_preferido": "es",
            "nota": browser_hint if not (hunspell or aspell or pyspell) else (
                "Diccionario de sistema detectado; se combina con vocabulario de la app."
            ),
        }

    def suggest(self, word: str, *, limit: int = 8, dominio: list[str] | None = None) -> dict[str, Any]:
        """Sugerencias ortográficas + términos de dominio (catálogo/nombres)."""
        w = (word or "").strip()
        if not w or len(w) < 2:
            return {"word": w, "ok": True, "suggestions": [], "source": []}
        st = self.status()
        suggestions: list[str] = []
        sources: list[str] = []

        # 1) Dominio app (siempre, complemento)
        dom = dominio or self._domain_vocab()
        dom_hits = self._match_domain(w, dom, limit=limit)
        if dom_hits:
            suggestions.extend(dom_hits)
            sources.append("app")

        # 2) hunspell
        if st.get("hunspell"):
            hs = self._hunspell_suggest(w, limit=limit)
            for s in hs:
                if s not in suggestions:
                    suggestions.append(s)
            if hs:
                sources.append("hunspell")

        # 3) aspell
        if st.get("aspell") and len(suggestions) < limit:
            as_ = self._aspell_suggest(w, limit=limit)
            for s in as_:
                if s not in suggestions:
                    suggestions.append(s)
            if as_:
                sources.append("aspell")

        # 4) archivo .dic del sistema (sin binario hunspell)
        if st.get("dict_path") and len(suggestions) < limit:
            ds = self._dicfile_suggest(w, limit=limit)
            for s in ds:
                if s not in suggestions:
                    suggestions.append(s)
            if ds:
                sources.append("dic_archivo")

        # 5) pyspellchecker (opcional pip)
        if st.get("pyspellchecker") and len(suggestions) < limit:
            ps = self._pyspell_suggest(w, limit=limit)
            for s in ps:
                if s not in suggestions:
                    suggestions.append(s)
            if ps:
                sources.append("pyspellchecker")

        return {
            "word": w,
            "ok": True,
            "suggestions": suggestions[:limit],
            "source": sources,
            "dict_available": bool(st.get("disponible")),
            "status": {k: st.get(k) for k in ("disponible", "dict_path", "hunspell", "aspell", "pyspellchecker", "motores")},
        }

    # —— internals ——

    @staticmethod
    def _find_dict_file() -> str | None:
        for p in _DICT_CANDIDATES:
            if os.path.isfile(p):
                return p
        # Linux / macOS
        for base in (
            "/usr/share/hunspell",
            "/usr/share/myspell/dicts",
            "/usr/local/share/hunspell",
            "/opt/homebrew/share/hunspell",
        ):
            try:
                b = Path(base)
                if not b.is_dir():
                    continue
                for f in sorted(b.glob("es*.dic")):
                    return str(f)
            except OSError:
                continue
        # Windows: escanear LibreOffice / Program Files
        windir = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        windir_x86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        local = os.environ.get("LOCALAPPDATA", "")
        scan_roots = [
            Path(windir) / "LibreOffice",
            Path(windir_x86) / "LibreOffice",
            Path(windir) / "OpenOffice 4",
            Path(r"C:\Hunspell"),
        ]
        if local:
            scan_roots.append(Path(local) / "Programs" / "LibreOffice")
        for root in scan_roots:
            try:
                if not root.exists():
                    continue
                for f in root.rglob("es*.dic"):
                    name = f.name.lower()
                    if "es_mx" in name or "es_es" in name or name.startswith("es"):
                        return str(f)
            except OSError:
                continue
        return None

    @lru_cache(maxsize=1)
    def _load_dic_words(self) -> frozenset[str]:
        """Carga palabras del .dic (sin hunspell binario) para sugerencias por distancia."""
        path = self._find_dict_file()
        if not path:
            return frozenset()
        words: set[str] = set()
        try:
            # dic hunspell: palabra o palabra/flags
            with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                first = True
                for i, line in enumerate(fh):
                    if first:
                        first = False
                        # primera línea suele ser el conteo
                        if line.strip().isdigit():
                            continue
                    w = line.strip().split("/")[0].strip()
                    if len(w) >= 3 and w.isalpha():
                        words.add(w.lower())
                    if i > 120_000:  # límite de memoria
                        break
        except OSError as e:
            logger.debug("No se pudo leer dic %s: %s", path, e)
            return frozenset()
        logger.info("Diccionario cargado: %s (%s palabras)", path, len(words))
        return frozenset(words)

    def _dicfile_suggest(self, word: str, limit: int = 8) -> list[str]:
        """Sugerencias por prefijo / distancia simple sobre el .dic del sistema."""
        words = self._load_dic_words()
        if not words:
            return []
        wl = word.lower()
        if wl in words:
            return []
        # prefijos
        pref = [w for w in words if w.startswith(wl[: max(2, len(wl) - 1)])]
        # distancia de edición 1-2 (muestra limitada)
        out: list[str] = []
        for w in pref:
            if w not in out:
                out.append(w)
            if len(out) >= limit:
                return out
        # si pocos, buscar ediciones cercanas en subconjunto
        if len(out) < limit and len(wl) >= 3:
            for w in words:
                if abs(len(w) - len(wl)) > 2:
                    continue
                if self._edit_distance(wl, w) <= 2:
                    if w not in out:
                        out.append(w)
                    if len(out) >= limit:
                        break
        return out[:limit]

    @staticmethod
    def _edit_distance(a: str, b: str) -> int:
        if a == b:
            return 0
        if abs(len(a) - len(b)) > 2:
            return 99
        # Levenshtein acotado
        la, lb = len(a), len(b)
        prev = list(range(lb + 1))
        for i, ca in enumerate(a, 1):
            cur = [i]
            for j, cb in enumerate(b, 1):
                cost = 0 if ca == cb else 1
                cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + cost))
            prev = cur
            if min(prev) > 2:
                return 99
        return prev[-1]

    @staticmethod
    def _pyspell_available() -> bool:
        try:
            import spellchecker  # type: ignore  # noqa: F401
            return True
        except Exception:
            try:
                import pyspellchecker  # type: ignore  # noqa: F401
                return True
            except Exception:
                return False

    def _hunspell_suggest(self, word: str, limit: int = 8) -> list[str]:
        bin_ = shutil.which("hunspell")
        if not bin_:
            return []
        dict_path = self._find_dict_file()
        args = [bin_, "-d", "es_ES,es_MX,es", "-a"]
        # -a: pipe mode
        try:
            proc = subprocess.run(
                args,
                input=f"^{word}\n",
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            out = proc.stdout or ""
        except Exception as e:
            logger.debug("hunspell falló: %s", e)
            return []
        # Formato: * (ok) o & word count offset: sug1, sug2
        for line in out.splitlines():
            if line.startswith("*") or line.startswith("+"):
                return []  # palabra correcta
            if line.startswith("#"):
                return []
            if line.startswith("&"):
                # & palabra n offset: a, b, c
                try:
                    part = line.split(":", 1)[1]
                    return [s.strip() for s in part.split(",") if s.strip()][:limit]
                except IndexError:
                    return []
        return []

    def _aspell_suggest(self, word: str, limit: int = 8) -> list[str]:
        bin_ = shutil.which("aspell")
        if not bin_:
            return []
        try:
            proc = subprocess.run(
                [bin_, "-d", "es", "pipe"],
                input=f"^{word}\n",
                capture_output=True,
                text=True,
                timeout=2.5,
                check=False,
            )
            out = proc.stdout or ""
        except Exception as e:
            logger.debug("aspell falló: %s", e)
            return []
        for line in out.splitlines():
            if line.startswith("*") or line.startswith("+"):
                return []
            if line.startswith("&"):
                try:
                    part = line.split(":", 1)[1]
                    return [s.strip() for s in part.split(",") if s.strip()][:limit]
                except IndexError:
                    return []
        return []

    def _pyspell_suggest(self, word: str, limit: int = 8) -> list[str]:
        try:
            from spellchecker import SpellChecker
            sp = SpellChecker(language="es")
            # si la palabra está bien, no sugerir
            if word.lower() in sp:
                return []
            cands = sp.candidates(word) or set()
            return list(cands)[:limit]
        except Exception:
            return []

    @lru_cache(maxsize=1)
    def _domain_vocab(self) -> tuple[str, ...]:
        """Vocabulario de la app: materiales, modelos, nombres frecuentes."""
        words: list[str] = []
        try:
            from app.db.repository import CatalogosRepo, TrabajadoresRepo
            cat = CatalogosRepo()
            for m in cat.listar_materiales(solo_activos=False) or []:
                n = (m.get("material") or m.get("nombre") or "").strip()
                if n:
                    words.append(n)
            for m in cat.listar_modelos() or []:
                n = (m.get("modelo") or m.get("nombre") or "").strip()
                if n:
                    words.append(n)
            for t in TrabajadoresRepo().listar(solo_activos=False) or []:
                n = (t.get("nombre_mostrar") or "").strip()
                if n:
                    words.append(n)
                    # también tokens del nombre
                    for part in n.replace(",", " ").split():
                        if len(part) > 2:
                            words.append(part)
        except Exception as e:
            logger.debug("vocabulario dominio: %s", e)
        # términos de negocio frecuentes
        words.extend([
            "plata", "pita", "taller", "folio", "gramos", "nómina", "nomina",
            "AG3", "DOL", "cinturón", "cinturon", "torcedor", "torcedores",
        ])
        # únicos preservando orden
        seen = set()
        out = []
        for w in words:
            k = w.lower()
            if k not in seen:
                seen.add(k)
                out.append(w)
        return tuple(out)

    @staticmethod
    def _match_domain(word: str, vocab: list[str] | tuple[str, ...], limit: int = 8) -> list[str]:
        wl = word.lower()
        starts = []
        contains = []
        for v in vocab:
            vl = v.lower()
            if vl.startswith(wl):
                starts.append(v)
            elif wl in vl and v not in starts:
                contains.append(v)
        return (starts + contains)[:limit]


@lru_cache(maxsize=1)
def get_spell_service() -> SpellService:
    return SpellService()
