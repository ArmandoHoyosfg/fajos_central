# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

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
