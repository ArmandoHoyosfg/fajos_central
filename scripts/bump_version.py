"""
Cambia la versión del proyecto en todos los archivos de una sola llamada.

Uso:
    python scripts/bump_version.py 3.26.0
    python scripts/bump_version.py 3.26.0 --changelog-msg "Nueva feature X"
    python scripts/bump_version.py 3.26.0 --dry-run   # solo muestra, no escribe

Actualiza:
  1. app/__init__.py   → __version__ = "x.y.z"
  2. VERSION           → x.y.z
  3. README.md         → **Versión:** x.y.z
  4. CHANGELOG.md      → añade entry ## [x.y.z] — fecha (si no existe)
  5. docs/PROJECT_STATE.md → Versión app: **x.y.z** + Última actualización: fecha

NO toca:
  - Código fuente (solo los 5 archivos de metadata)
  - requirements.txt
  - db/schema/
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
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
    here = Path(__file__).resolve().parent
    candidate = here.parent
    if (candidate / "app").exists() and (candidate / "app" / "__init__.py").exists():
        return candidate
    cwd = Path.cwd()
    if (cwd / "app").exists():
        return cwd
    return candidate


ROOT = _project_root()


# ─── colores ───────────────────────────────────────────────────────────────────

def _green(s: str) -> str:
    return f"\033[92m{s}\033[0m"

def _red(s: str) -> str:
    return f"\033[91m{s}\033[0m"

def _bold(s: str) -> str:
    return f"\033[1m{s}\033[0m"

def _cyan(s: str) -> str:
    return f"\033[96m{s}\033[0m"


# ─── helpers ───────────────────────────────────────────────────────────────────

def _current_version() -> str | None:
    try:
        src = (ROOT / "app" / "__init__.py").read_text(encoding="utf-8")
        m = re.search(r'__version__\s*=\s*["\']([\d.]+)["\']', src)
        return m.group(1) if m else None
    except Exception:
        return None


def _valid_version(v: str) -> bool:
    return bool(re.match(r'^\d+\.\d+\.\d+$', v))


# ─── updates ───────────────────────────────────────────────────────────────────

def update_init_py(new_ver: str, dry: bool) -> tuple[bool, str]:
    path = ROOT / "app" / "__init__.py"
    src = path.read_text(encoding="utf-8")
    new_src, n = re.subn(
        r'__version__\s*=\s*["\'][\d.]+["\']',
        f'__version__ = "{new_ver}"',
        src,
    )
    if n == 0:
        return False, "NO se encontró __version__"
    if not dry:
        path.write_text(new_src, encoding="utf-8")
    return True, f'app/__init__.py → "{new_ver}"'


def update_version_file(new_ver: str, dry: bool) -> tuple[bool, str]:
    path = ROOT / "VERSION"
    old = path.read_text(encoding="utf-8").strip()
    if not dry:
        path.write_text(new_ver + "\n", encoding="utf-8")
    return True, f"VERSION: {old} → {new_ver}"


def update_readme(new_ver: str, dry: bool) -> tuple[bool, str]:
    path = ROOT / "README.md"
    src = path.read_text(encoding="utf-8")
    new_src, n = re.subn(
        r'\*\*Versi[oó]n:\*\*\s*[\d.]+',
        f'**Versión:** {new_ver}',
        src,
    )
    if n == 0:
        return False, "NO se encontró **Versión:** en README"
    if not dry:
        path.write_text(new_src, encoding="utf-8")
    return True, f"README.md → {new_ver}"


def update_changelog(new_ver: str, msg: str, dry: bool) -> tuple[bool, str]:
    path = ROOT / "CHANGELOG.md"
    src = path.read_text(encoding="utf-8")

    # si ya existe la entry, no duplicar
    if f"## [{new_ver}]" in src:
        return True, f"CHANGELOG.md: entry [{new_ver}] ya existe (sin cambios)"

    fecha = datetime.now().strftime("%Y-%m-%d")
    # buscar la primera entry existente para insertar antes de ella
    m = re.search(r'^## \[[\d.]+\]', src, re.MULTILINE)
    if m:
        insert_pos = m.start()
        # construir la nueva entry
        entry = (
            f"## [{new_ver}] — {fecha}\n\n"
            f"### Cambios\n- {msg}\n\n"
        )
        new_src = src[:insert_pos] + entry + src[insert_pos:]
    else:
        # no hay entries, añadir al final
        new_src = src.rstrip() + f"\n\n## [{new_ver}] — {fecha}\n\n### Cambios\n- {msg}\n"

    if not dry:
        path.write_text(new_src, encoding="utf-8")
    return True, f"CHANGELOG.md: entry [{new_ver}] añadida"


def update_project_state(new_ver: str, dry: bool) -> tuple[bool, str]:
    path = ROOT / "docs" / "PROJECT_STATE.md"
    src = path.read_text(encoding="utf-8")
    fecha = datetime.now().strftime("%Y-%m-%d")

    changes = 0

    # 1. "Última actualización: YYYY-MM-DD | Versión app: **X.Y.Z**"
    new_src, n1 = re.subn(
        r'Última actualización: [\d-]+ \| Versi[oó]n app: \*\*[\d.]+\*\*',
        f'Última actualización: {fecha} | Versión app: **{new_ver}**',
        src,
    )
    changes += n1

    # 2. "Versión actual:** X.Y.Z" (en la sección de checkpoint de sesión)
    new_src, n2 = re.subn(
        r'\*\*Versi[oó]n actual:\*\* [\d.]+',
        f'**Versión actual:** {new_ver}',
        new_src,
    )
    changes += n2

    if changes == 0:
        return False, "NO se encontró versión en PROJECT_STATE.md"

    if not dry:
        path.write_text(new_src, encoding="utf-8")
    return True, f"PROJECT_STATE.md → {new_ver} ({changes} cambio/s)"


# ─── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(
        description="Cambia la versión del proyecto en todos los archivos.",
    )
    p.add_argument("version", help="Nueva versión (ej: 3.26.0)")
    p.add_argument(
        "--changelog-msg",
        default="Actualización de versión.",
        help="Mensaje para la entry en CHANGELOG.md",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra los cambios, no escribe archivos.",
    )
    args = p.parse_args()

    new_ver = args.version.strip()
    if not _valid_version(new_ver):
        print(_red(f"  ❌ Versión inválida: '{new_ver}'"))
        print(_red(f"     Formato esperado: X.Y.Z (ej: 3.26.0)"))
        return 1

    old_ver = _current_version()
    mode = "DRY RUN" if args.dry_run else "ESCRIBIENDO"

    print(_bold(f"\n  Bump versión — Fajos Central"))
    print(_bold(f"  {old_ver or '?'} → {new_ver}  [{mode}]"))
    print(_bold(f"  Raíz: {ROOT}\n"))

    updates = [
        ("app/__init__.py", lambda: update_init_py(new_ver, args.dry_run)),
        ("VERSION", lambda: update_version_file(new_ver, args.dry_run)),
        ("README.md", lambda: update_readme(new_ver, args.dry_run)),
        ("CHANGELOG.md", lambda: update_changelog(new_ver, args.changelog_msg, args.dry_run)),
        ("PROJECT_STATE.md", lambda: update_project_state(new_ver, args.dry_run)),
    ]

    errors = 0
    for nombre, fn in updates:
        try:
            ok, msg = fn()
            mark = _green("✅") if ok else _red("❌")
            print(f"  {mark}  {msg}")
            if not ok:
                errors += 1
        except Exception as e:
            print(f"  {_red('❌')}  {nombre}: {e}")
            errors += 1

    print()
    if errors == 0:
        print(_bold(_green("  ✅ Bump de versión completado")))
        if not args.dry_run:
            print(_bold(f"  Siguiente paso:  python scripts/verify.py"))
    else:
        print(_bold(_red(f"  ❌ {errors} error(es) durante el bump")))
    print()

    return 0 if errors == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())