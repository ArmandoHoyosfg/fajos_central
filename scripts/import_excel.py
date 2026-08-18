#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Importación segura Excel → MariaDB (Windows / PowerShell 7)

Uso (PowerShell):
  cd fajos_central
  .\\.venv\\Scripts\\Activate.ps1

  # 1) Simulación (no escribe nada)
  python scripts\\import_excel.py "templates_excel\\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"

  # 2) Aplicar de verdad
  python scripts\\import_excel.py "templates_excel\\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx" --apply

  # Opciones de semana
  python scripts\\import_excel.py archivo.xlsx --apply --codigo "16-22" --inicio 2026-08-16 --fin 2026-08-22
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.logging_config import setup_logging
from app.services.import_service import ImportService


def main() -> int:
    setup_logging()
    p = argparse.ArgumentParser(description="Importar Excel de nóminas a MariaDB (seguro)")
    p.add_argument("excel", help="Ruta al archivo .xlsx")
    p.add_argument(
        "--apply",
        action="store_true",
        help="Escribe en la BD. Sin este flag solo simula (dry-run).",
    )
    p.add_argument("--codigo", default=None, help="Código de semana (ej: 16-22)")
    p.add_argument("--inicio", default=None, help="Fecha inicio YYYY-MM-DD")
    p.add_argument("--fin", default=None, help="Fecha fin YYYY-MM-DD")
    p.add_argument("--anio", type=int, default=2026)
    p.add_argument("--json", action="store_true", help="Imprime reporte JSON completo")
    args = p.parse_args()

    path = Path(args.excel)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()

    dry_run = not args.apply
    print("=" * 60)
    print("Fajos Central — Importación Excel")
    print(f"Archivo : {path}")
    print(f"Modo    : {'DRY-RUN (simulación)' if dry_run else 'APPLY (escribe en BD)'}")
    print("=" * 60)

    if not dry_run:
        print("ADVERTENCIA: Se escribirán datos nuevos en MariaDB.")
        print("No se borran registros existentes. Trabajadores se agregan solo si no existen.")
        print()

    svc = ImportService()
    try:
        report = svc.import_excel(
            path,
            dry_run=dry_run,
            codigo_semana=args.codigo,
            fecha_inicio=args.inicio,
            fecha_fin=args.fin,
            anio=args.anio,
        )
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

    t = report["trabajadores"]
    pr = report["produccion"]
    print(f"\nTrabajadores nuevos     : {len(t['nuevos'])}")
    print(f"Trabajadores ya existían: {len(t['existentes'])}")
    print(f"Errores trabajadores    : {len(t['errores'])}")
    if report.get("semana"):
        print(f"Semana                  : {report['semana']}")
    print(f"Líneas producción nuevas: {len(pr['nuevas'])}")
    print(f"Omitidas (duplicado)    : {len(pr['omitidas_duplicado'])}")
    print(f"Errores producción      : {len(pr['errores'])}")
    print(f"\n{report.get('mensaje', '')}")

    if t["errores"]:
        print("\n--- Errores trabajadores ---")
        for e in t["errores"][:20]:
            print(" ", e)
    if pr["errores"]:
        print("\n--- Errores producción ---")
        for e in pr["errores"][:20]:
            print(" ", e)
    if t["nuevos"] and dry_run:
        print("\n--- Trabajadores que SE AGREGARÍAN ---")
        for x in t["nuevos"][:15]:
            print(f"  + {x['nombre_mostrar']}  ubic={x['ubic']}  tipo={x.get('tipo')}")
        if len(t["nuevos"]) > 15:
            print(f"  ... y {len(t['nuevos'])-15} más")
    if pr["nuevas"] and dry_run:
        print("\n--- Producción que SE AGREGARÍA (muestra) ---")
        for x in pr["nuevas"][:10]:
            print(
                f"  + {x['nombre']} ubic={x['ubic']} folio={x.get('folio')} "
                f"sab={x.get('gm_sab')} dom={x.get('gm_dom')}"
            )
        if len(pr["nuevas"]) > 10:
            print(f"  ... y {len(pr['nuevas'])-10} más")

    if args.json:
        print("\n--- JSON ---")
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))

    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
