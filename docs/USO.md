# Guía de uso — Fajos Central (Windows + PowerShell 7)

## 1. Primera vez

```powershell
cd ruta\a\fajos_central
pwsh -File .\setup_windows.ps1
```

Configura la base de datos:

- **Recomendado:** abre `python launcher.py` → **Configurar conexión** → Guardar (crea `config.ini`).
- Alternativa: copia `config.ini.example` a `config.ini` y pon usuario/contraseña.
- También puedes usar `.env` (las variables `FAJOS_DB_*` tienen prioridad).

En **HeidiSQL**, sobre la base `fajos_central`, ejecuta en orden:

1. `db\schema\001_schema_inicial.sql`
2. `db\schema\002_suministro_e_import.sql`

## 2. Arrancar el sistema

```powershell
pwsh -File .\start.ps1
# o
python launcher.py
```

- Iniciar servidor web → abre el navegador en `http://127.0.0.1:8000`
- Otros PCs en la red: `http://IP_DE_ESTE_EQUIPO:8000`

## 3. Importar el Excel (seguro)

```powershell
# Simulación: no escribe en la BD
python scripts\import_excel.py .\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx

# Aplicar (trabajadores nuevos + líneas con gramos/folio)
python scripts\import_excel.py .\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx --apply --codigo "16-22" --inicio 2026-08-16 --fin 2026-08-22
```

**Garantías:**

| Comportamiento | Detalle |
|----------------|---------|
| No borra | Nunca elimina filas existentes |
| Trabajadores | Solo agrega si no existe el par nombre+ubic |
| Producción | Omite duplicados (misma semana + nombre + ubic + folio) |
| Dry-run | Por defecto solo reporta qué haría |

## 4. Flujo semanal recomendado

1. (Opcional) Llenar o actualizar el Excel de captura.
2. Importar con dry-run → revisar → `--apply`.
3. O capturar directo en la web: **Producción** → crear semana → agregar líneas.
4. Exportar nómina formal (Excel/PDF) desde la misma pantalla.
5. Imprimir y firmar.

## 5. Excel de referencia

Archivo: `templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx`

- **Nomina-Imprimir**: captura (no muestra ceros).
- **Nomina-Formal**: se llena sola; no muestra ceros; columna Firma.
- **Trabajadores / Modelos / Tarifas / Resumen**: catálogos y totales.

## 6. Si algo falla

- Revisa `logs\fajos.log` y `logs\server_launcher.log`
- API de salud: `http://127.0.0.1:8000/api/health`
- Documentación API: `http://127.0.0.1:8000/docs`
- Estado del proyecto para IAs: `docs\PROJECT_STATE.md`
