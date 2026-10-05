# Importar Excel → MariaDB

## Requisitos
1. MariaDB con la base `fajos_central` y el esquema ejecutado (`db/schema/*.sql`).
2. `config.ini` en la raíz del proyecto (puedes crearlo desde el launcher).
3. Entorno virtual con dependencias.

## PowerShell 7

```powershell
cd '.\Documents\Proyectos Desarrollo\fajos_central\'
.\.venv\Scripts\Activate.ps1

# Simular (seguro)
python scripts\importar_excel.py --excel ".\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx"

# Aplicar
python scripts\importar_excel.py --excel ".\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx" --aplicar
```

Si el Excel está en otra carpeta, usa la ruta completa:

```powershell
python scripts\importar_excel.py --excel "C:\Users\Orion Ethan\Documents\...\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx" --aplicar --semana "16-22" --inicio 2026-08-16 --fin 2026-08-22
```

## Qué se carga
| Hoja Excel        | Tabla BD            |
|-------------------|---------------------|
| Trabajadores      | trabajadores        |
| Nomina-Imprimir   | semanas + produccion_plata |

No borra datos. Duplicados de producción se omiten.
