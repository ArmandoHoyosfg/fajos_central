"""
Verificación rápida del proyecto Fajos Central.

Uso:
    python scripts/verify.py              # verificación completa
    python scripts/verify.py --skip-tests # solo import + versiones (más rápido)

Salida (ejemplo):
    ✅ Import app.main — versión 3.25.6
    ✅ Versiones coherentes (5/5 archivos)
    ✅ Tests: 19 passed en 0.56s
    ─────────────────────────────────────
    ✅ TODO OK
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

# Forzar UTF-8 en consolas Windows
if sys.platform == "win32":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ─── rutas ─────────────────────────────────────────────────────────────────────

def _project_root() -> Path:
    """Resuelve la raíz del proyecto desde el archivo actual."""
    here = Path(__file__).resolve().parent
    # scripts/ → subir 1 nivel
    candidate = here.parent
    if (candidate / "app").exists() and (candidate / "app" / "__init__.py").exists():
        return candidate
    # fallback: cwd
    cwd = Path.cwd()
    if (cwd / "app").exists():
        return cwd
    return candidate


ROOT = _project_root()


# ─── colores (ANSI, funcionan en Windows Terminal / PowerShell 7) ─────────────

def _green(s: str) -> str:
    return f"\033[92m{s}\033[0m"

def _red(s: str) -> str:
    return f"\033[91m{s}\033[0m"

def _yellow(s: str) -> str:
    return f"\033[93m{s}\033[0m"

def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"


# ─── checks ────────────────────────────────────────────────────────────────────

def check_import() -> tuple[bool, str]:
    """Verifica que app.main importa y devuelve la versión."""
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-c",
             "from app import __version__; print(__version__)"],
            capture_output=True, text=True, timeout=30, cwd=str(ROOT),
        )
        if result.returncode == 0:
            ver = result.stdout.strip()
            elapsed = time.perf_counter() - t0
            return True, f"Import app.main — versión {ver} ({elapsed:.1f}s)"
        else:
            err = result.stderr.strip()[:200]
            return False, f"Import falló: {err}"
    except subprocess.TimeoutExpired:
        return False, "Import timeout (30s)"
    except Exception as e:
        return False, f"Import error: {e}"


def check_versions() -> tuple[bool, list[tuple[str, str, bool]]]:
    """
    Verifica coherencia de versiones en 5 archivos.
    Devuelve (ok, lista_de_[archivo, version_encontrada, coincide]).
    """
    # fuente de verdad
    try:
        init_src = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', init_src)
        source_ver = m.group(1) if m else None
    except Exception:
        source_ver = None

    if source_ver is None:
        return False, [("app/__init__.py", "NO ENCONTRADA", False)]

    results: list[tuple[str, str, bool]] = [("app/__init__.py", source_ver, True)]

    # VERSION
    try:
        v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        results.append(("VERSION", v, v == source_ver))
    except Exception as e:
        results.append(("VERSION", f"ERROR: {e}", False))

    # README.md
    try:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        m = re.search(r'\*\*Versi[oó]n:\*\*\s*([\d.]+)', readme)
        v = m.group(1) if m else None
        results.append(("README.md", v or "NO ENCONTRADA", v == source_ver))
    except Exception as e:
        results.append(("README.md", f"ERROR: {e}", False))

    # CHANGELOG.md (primera entry ## [x.y.z])
    try:
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        m = re.search(r'## \[([\d.]+)\]', changelog)
        v = m.group(1) if m else None
        results.append(("CHANGELOG.md (1ra entry)", v or "NO ENCONTRADA", v == source_ver))
    except Exception as e:
        results.append(("CHANGELOG.md", f"ERROR: {e}", False))

    # PROJECT_STATE.md
    try:
        state = (ROOT / "docs" / "PROJECT_STATE.md").read_text(encoding="utf-8")
        m = re.search(r'Versi[oó]n app: \*\*([\d.]+)\*\*', state)
        v = m.group(1) if m else None
        results.append(("PROJECT_STATE.md", v or "NO ENCONTRADA", v == source_ver))
    except Exception as e:
        results.append(("PROJECT_STATE.md", f"ERROR: {e}", False))

    all_ok = all(ok for _, _, ok in results)
    return all_ok, results


def check_tests() -> tuple[bool, str]:
    """Corre pytest -q y devuelve (ok, resumen)."""
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-m", "pytest", "-q", "--tb=line"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        elapsed = time.perf_counter() - t0
        # extraer el resumen de la última línea útil
        output = result.stdout + result.stderr
        # buscar "N passed" o "N failed"
        m = re.search(r'(\d+)\s+passed', output)
        if m and result.returncode == 0:
            return True, f"Tests: {m.group(1)} passed en {elapsed:.1f}s"
        m_fail = re.search(r'(\d+)\s+failed', output)
        if m_fail:
            return False, f"Tests: {m_fail.group(1)} FAILED en {elapsed:.1f}s"
        if result.returncode == 0:
            return True, f"Tests: OK en {elapsed:.1f}s"
        return False, f"Tests: exit code {result.returncode} en {elapsed:.1f}s"
    except subprocess.TimeoutExpired:
        return False, "Tests: timeout (120s)"
    except Exception as e:
        return False, f"Tests: error {e}"


# ─── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Verificación rápida de Fajos Central.")
    p.add_argument("--skip-tests", action="store_true", help="Omitir pytest (más rápido).")
    args = p.parse_args()

    print(_bold(f"\n  Verificación — Fajos Central"))
    print(_bold(f"  Raíz: {ROOT}\n"))

    errors = 0

    # 1. import
    ok, msg = check_import()
    print(f"  {_green('✅') if ok else _red('❌')}  {msg}")
    if not ok:
        errors += 1

    # 2. versiones
    ok, results = check_versions()
    if ok:
        print(f"  {_green('✅')}  Versiones coherentes ({len(results)}/{len(results)} archivos)")
    else:
        print(f"  {_red('❌')}  Versiones INCOHERENTES:")
        for archivo, ver, coincide in results:
            mark = _green("✅") if coincide else _red("❌")
            print(f"         {mark}  {archivo:<28} {ver}")
        errors += 1

    # 3. tests
    if not args.skip_tests:
        ok, msg = check_tests()
        print(f"  {_green('✅') if ok else _red('❌')}  {msg}")
        if not ok:
            errors += 1
    else:
        print(f"  {_yellow('⏭')}  Tests omitidos (--skip-tests)")

    # resumen
    print()
    if errors == 0:
        print(_bold(_green("  ✅ TODO OK")))
    else:
        print(_bold(_red(f"  ❌ {errors} ERROR(S)")))
    print()

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())