# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [3.2.0] — 2026-08-20

### Operación diaria
- Cerrar hoy (resumen + registro `cierre_dia`)
- Suministro Excel de una página
- Avisos al abrir app / web
- Duplicar folios a la semana siguiente
- Formal solo con gramos (>0)

## [3.1.2] — 2026-08-20

### Corregido / endurecido
- ImportError `etiqueta_semana` (calendar_util con fallback local)
- Días distintos de hoy **bloqueados**; edición solo con doble clic + confirmación
- Misma regla en Producción, Trabajos (desktop) y web

## [3.1.1] — 2026-08-20

### UI en vivo
- Totales se recalculan al editar gramos (desktop y web)
- Barra KPI fija en web (`#kpi-live`)
- Menos recargas completas; feedback al teclear
- Producción apunta a Trabajos para captura diaria (menos duplicación)

## [3.1.0] — 2026-08-20

### Trabajos activos + reglas de fecha
- Pestaña/página Trabajos activos (desktop y web)
- Recordatorio si falta captura del día de hoy
- Confirmación al editar días pasados con gramos
- Formal sigue leyendo producción ligada a trabajos

## [3.0.0] — 2026-08-20

### Mayor
- Tabla `trabajos` liga folio/modelo/material al trabajador
- `produccion_plata.trabajador_id` obligatorio + `trabajo_id`
- Un solo SQL: `000_fajos_central_completo.sql` (Excel V3)
- API `/api/trabajos`

## [2.9.0] — 2026-08-20

### Prioridad media
- `calendar_util` único (`app.core`; desktop reexporta)
- Web: edición inline de gramos + toast
- Filtro «sin firmar» + checkbox firmado
- Botón ★ Semana actual (web y desktop)
- Captura incluye trabajadores PIT/TLL (no solo PLT)

## [2.8.0] — 2026-08-20

### Alta prioridad
- Historial de cambios de producción (`historial_produccion`)
- Cierre / reapertura de semana (bloquea edición)
- Tarifas desde tabla `tarifas_material` (API + desktop)
- Backup automático en `exports/` al generar formal
- API suministro del día (`/api/suministro`)
- Script SQL `004_cierre_historial_tarifas.sql`

## [2.7.2] — 2026-08-20

### Corregido
- Export formal ordena por **ubic → nombre → folio** (materiales pueden intercalarse)
- Se mantienen los **colores de fila por material**

## [2.7.1] — 2026-08-20

### Export formal enriquecido
- Encabezado tipo hoja Nomina-Formal (taller, semana, periodo, mes, año)
- Fecha/hora de emisión en hoja y pie de página
- Resumen por material + Vo.Bo. supervisor y fecha de pago
- Mismo formato en desktop y export web xlsx

## [2.7.0] — 2026-08-20

### Web ↔ Desktop parity
- Fecha actual en topbar web (misma lógica de calendario)
- Semana ★ ACTUAL auto-seleccionada en Producción web
- Iconos SVG propios (favicon, calendario, materiales, estrella)
- Colores de fila por material en producción web
- Contexto de plantilla unificado (`common_template_context`)

## [2.6.1] — 2026-08-20

### Añadido
- Fecha actual visible en barra principal y status bar
- Comparación de semanas con el calendario (marca ★ ACTUAL)
- Auto-selección de la semana que contiene hoy
- Nueva semana sugiere rango sáb–vie de la semana corriente

## [2.6.0] — 2026-08-20

### Desktop UX
- Atajos: Enter guarda el día; flechas cambian día
- Toast discreto (sin modal) al guardar
- Línea completa colapsada por defecto
- Filtro «solo sin gramos hoy» y copiar día anterior → hoy
- Tarifa sugerida por material + aviso si difiere
- Aviso de folio duplicado en la semana
- Export Formal PDF + Excel ordenado por material
- Encabezado de impresión repetido en cada página

## [2.5.2] — 2026-08-20

### Corregido / Mejorado
- Desktop: scroll suave y más aire en Producción (deja de verse aplastado)
- Formal Excel: color por material en cada fila + leyenda (impresión)
- Export web xlsx formal: mismos colores de material

## [2.5.1] — 2026-08-20

### Añadido (app escritorio)
- Panel «Registrar un solo día» (crea o actualiza línea)
- Edición de gramos en tabla (doble clic)
- Color por material, resalte del día de hoy, totales KPI
- Filtro por nombre/folio/material y estados vacíos
- Badges de tipo en trabajadores

## [2.5.0] — 2026-08-20

### Añadido
- Import Excel con vista previa obligatoria antes de aplicar (launcher)
- PDF nómina formal con color por material y totales
- Normalización de nombres (acentos) en import y alta
- Captura de un solo día de trabajo por empleado (API + web)
- HTTPS: con certificados, redirección HTTP→HTTPS automática

## [2.4.1] — 2026-08-20

### Corregido / Mejorado
- App escritorio (PySide6): título v2.4.x, nombre Fajos Piteados Central, logo, acento dorado, búsqueda de trabajadores, estado BD en barra

## [2.4.0] — 2026-08-20

### Añadido
- UI unificada (web + estilo launcher): Lucide icons, logo, badges
- Dashboard con estado BD, KPIs y atajos
- Página /buscar (trabajadores + semanas/nóminas)
- Export formal ordenado (`?formal=1`) por ubic y nombre
- Health API con estado de MariaDB

## [2.3.3] — 2026-08-20

### Corregido
- setup_windows.ps1: detecta venv roto (Python314 ausente), recrea con py launcher
- start.ps1: usa siempre .venv\Scripts\python.exe (evita Inkscape/PATH)
- pip vía python -m pip

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
