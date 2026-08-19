# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [2.3.2] — 2026-08-19

### Corregido
- Launcher: layout compacto en rejilla (sin scroll), tamaño al contenido, centrado

## [2.3.1] — 2026-08-18

### Corregido
- Launcher: config BD sin pydantic_settings (solo config.ini / stdlib)
- UI launcher más compacta, centrada y adaptable a la pantalla
- Ventana de importación maximizada

## [2.3.0] — 2026-08-18

### Añadido
- UI web rediseñada (CSS dark-first, logo, badges, tablas)
- HTTPS opcional: certificados locales, redirección HTTP→HTTPS, launcher abre https
- `scripts/generate_ssl_certs.py`

## [2.2.4] — 2026-08-18

### Corregido / Añadido
- Launcher: sección BD arriba del todo + scroll (botón Configurar conexión visible)
- Logo Fajos Piteados Central en web y launcher

## [2.2.3] — 2026-08-17

### Corregido
- Error del dashboard web (`TemplateResponse` / Starlette): la página inicio volvía a cargar
- Mensajes de error HTML más claros en el navegador

## [2.2.2] — 2026-08-17

### Añadido
- `config.ini` para usuario/contraseña MariaDB (editable desde el launcher)
- Botones «Configurar conexión» y «Probar conexión» en el launcher
- App de escritorio lee el mismo `config.ini`

## [2.2.1] — 2026-08-17

### Añadido
- Launcher como centro de control: web, escritorio, import Excel, docs, SQL
- `docs/ARCHIVOS_RAIZ.md` — guía de cada archivo de la carpeta principal

## [2.2.0] — 2026-08-17

### Añadido
- **Importación segura Excel → MariaDB** (`app/services/import_service.py`, `scripts/import_excel.py`)
  - Dry-run por defecto; `--apply` para escribir
  - No borra datos; upsert trabajadores por (nombre, ubic); evita duplicar producción
- Migración SQL `db/schema/002_suministro_e_import.sql` (suministro diario + import_log)
- Captura web de producción mejorada: crear semana, agregar línea, borrar, export
- Excel: ceros ocultos en captura y formal

## [2.1.1] — 2026-08-17

### Añadido
- Scripts PowerShell 7: `setup_windows.ps1`, `start.ps1`
- Log del servidor desde el launcher en `logs/server_launcher.log` (útil en Windows)

## [2.1.0] — 2026-08-17

### Añadido
- **Launcher GUI** (`launcher.py`): ventana para iniciar/detener el servidor web,
  abrir el navegador, lanzar la app de escritorio legacy y abrir la carpeta del proyecto
- Usa solo la biblioteca estándar (tkinter); no requiere dependencias extra

## [2.0.0] — 2026-08-17

### Añadido
- Aplicación web FastAPI con dashboard, trabajadores y producción
- API REST documentada en `/docs`
- Exportación multi-formato (Excel, CSV, PDF, JSON)
- Manejo de errores estructurado (códigos estables para humanos e IA)
- Tests con pytest
- Configuración por `.env` (pydantic-settings)
- Logging a consola y archivo
- Script SQL de esquema en `db/schema/`
- Consolidación de todo el trabajo previo en una sola carpeta versionada

### Incluido como referencia
- Excel optimizado (`templates_excel/`)
- GUI de escritorio PySide6 (`desktop_legacy/`)
- Script CLI de automatización (`scripts/`)

## [1.0.0] — 2026-08-17

### Añadido
- Excel de nóminas optimizado (captura + formal vinculada)
- Catálogo de trabajadores, modelos y tarifas
- Script SQL MariaDB inicial
- Automatización Python CLI
- Prototipo GUI PySide6
