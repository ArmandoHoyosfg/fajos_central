#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importa el Excel de nóminas a MariaDB (fajos_central).

Uso (PowerShell 7, desde la raíz del proyecto):

  # 1) Simular (no escribe en BD) — recomendado primero
  .\.venv\Scripts\python.exe scripts\importar_excel.py --excel "ruta\al\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"

  # 2) Aplicar de verdad
  .\.venv\Scripts\python.exe scripts\importar_excel.py --excel "ruta\al\NOMINA.xlsx" --aplicar

  # Opcional: forzar código de semana y fechas
  .\.venv\Scripts\python.exe scripts\importar_excel.py --excel "NOMINA.xlsx" --aplicar `
      --semana "16-22" --inicio 2026-08-16 --fin 2026-08-22 --anio 2026

Qué importa:
  - Hoja Trabajadores  → tabla trabajadores (upsert por nombre + ubic)
  - Hoja Nomina-Imprimir → semana + líneas produccion_plata
  - No borra datos previos; omite producción duplicada (semana+nombre+ubic+folio)

Requisitos:
  - config.ini o .env con conexión MariaDB
  - Esquema ya creado (db/schema/*.sql en HeidiSQL)
  - openpyxl + mysql-connector-python en el venv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Raíz del proyecto en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importar Excel de nóminas Fajos Central → MariaDB"
    )
    parser.add_argument(
        "--excel",
        "-e",
        required=True,
        help="Ruta al archivo .xlsx (Nomina-Imprimir + Trabajadores)",
    )
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Escribe en la BD. Sin este flag solo simula (dry-run).",
    )
    parser.add_argument("--semana", default=None, help="Código semana, ej. 16-22")
    parser.add_argument("--inicio", default=None, help="Fecha inicio YYYY-MM-DD")
    parser.add_argument("--fin", default=None, help="Fecha fin YYYY-MM-DD")
    parser.add_argument("--anio", type=int, default=2026, help="Año (default 2026)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Imprime el reporte completo en JSON",
    )
    args = parser.parse_args()

    excel = Path(args.excel)
    if not excel.is_file():
        # Intentar rutas relativas al proyecto
        candidates = [
            excel,
            ROOT / excel,
            ROOT / "templates_excel" / excel.name,
            ROOT.parent / "NOMINA_FAJOS_OPTIMIZADA_2026.xlsx",
            ROOT / "NOMINA_FAJOS_OPTIMIZADA_2026.xlsx",
        ]
        excel = next((p for p in candidates if p.is_file()), excel)

    if not excel.is_file():
        print(f"ERROR: no se encuentra el Excel: {args.excel}", file=sys.stderr)
        print("Pasa la ruta completa con --excel", file=sys.stderr)
        return 1

    dry_run = not args.aplicar
    modo = "SIMULACIÓN (no escribe)" if dry_run else "APLICAR (escribe en BD)"
    print(f"=== Import Excel → fajos_central ===")
    print(f"Archivo : {excel.resolve()}")
    print(f"Modo    : {modo}")
    print()

    try:
        from app.services.import_service import ImportService
    except Exception as e:
        print(f"ERROR al cargar el servicio de importación: {e}", file=sys.stderr)
        print("Activa el venv e instala requirements.txt", file=sys.stderr)
        return 1

    try:
        svc = ImportService()
        report = svc.import_excel(
            excel,
            dry_run=dry_run,
            codigo_semana=args.semana,
            fecha_inicio=args.inicio,
            fecha_fin=args.fin,
            anio=args.anio,
        )
    except Exception as e:
        print(f"ERROR durante la importación: {e}", file=sys.stderr)
        return 1

    t = report.get("trabajadores", {})
    p = report.get("produccion", {})
    print("--- Trabajadores ---")
    print(f"  Nuevos     : {len(t.get('nuevos', []))}")
    print(f"  Existentes : {len(t.get('existentes', []))}")
    print(f"  Errores    : {len(t.get('errores', []))}")
    for err in (t.get("errores") or [])[:10]:
        print(f"    · {err}")

    print("--- Semana ---")
    print(f"  {report.get('semana')}")

    print("--- Producción (Nomina-Imprimir) ---")
    print(f"  Nuevas líneas : {len(p.get('nuevas', []))}")
    print(f"  Omitidas dup. : {len(p.get('omitidas_duplicado', []))}")
    print(f"  Errores       : {len(p.get('errores', []))}")
    for err in (p.get("errores") or [])[:10]:
        print(f"    · {err}")

    print()
    print(report.get("mensaje") or ("OK" if report.get("ok") else "Con advertencias"))

    if args.json:
        print()
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    if dry_run:
        print()
        print(">>> Fue solo simulación. Para grabar en la BD añade: --aplicar")

    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    raise SystemExit(main())
