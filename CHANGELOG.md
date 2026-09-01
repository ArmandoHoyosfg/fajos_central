# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [3.22.2] — 2026-09-01

### Fix botones Plata + migraciones
- `openEditPlt`: `const form` duplicado → SyntaxError y `openEditPlt is not defined`
- Cursores MySQL `buffered=True` y consumo de resultados en migraciones (`Unread result found`)

## [3.22.1] — 2026-09-01

### Errores visibles + consola Dev
- Toast de advertencia en errores de script, promesas y fallos de red/5xx
- Botones deshabilitados muestran el motivo al hacer clic
- Consola de solo lectura en `/dev` con eventos en vivo (servidor + navegador)
- API `/api/dev/logs` y `/api/dev/client-log`

## [3.22.0] — 2026-09-01

### Catálogos útiles, no solo adorno
- Material y modelo en captura: **lista sugerida + texto libre**
- Si el valor está en catálogo → aplica tarifa / material por defecto
- Si no está → se guarda igual, sin bloquear
- Modelos PLT cargados en formularios de Plata

## [3.21.7] — 2026-09-01

### UI: barra de semana sin bloquear la vista
- Eliminada la franja oscura a ancho completo (redundante con la fecha de la topbar)
- Contexto de semana en una línea discreta
- Códigos que cruzan mes: `29 ago-4 sep` (ya no `29/08-04/09`)

## [3.21.6] — 2026-09-01

### UI: barra «Hoy / Semana actual»
- Deja de usar fondo oscuro fijo (chocaba con tema Claro)
- Usa colores del tema y muestra el rango de fechas ISO junto al código

## [3.21.5] — 2026-08-31

### Fix: /dev NameError `method`
- En la página Dev, `{method:'POST'}` en un f-string se interpretaba como variable Python
- Escapado a `{{method:'POST'}}`

## [3.21.4] — 2026-08-31

### Suministro: hasta 10 avances
- Rango de avances **2–10** (ya no se reduce a 3 al tener Folio/Modelo/Mat/Obs)
- Se conserva la sincronización de opciones 0/1

## [3.21.3] — 2026-08-31

### Fix: opciones de Suministro no se reflejaban
- Los checkboxes desmarcados no se enviaban y el servidor los dejaba en 1
- Ahora siempre se envía 0/1 y cualquier cambio recarga la vista sincronizada

## [3.21.2] — 2026-08-31

### Suministro genérico + columnas compactas
- **Modo genérico**: solo UBIC + NOMBRE; folio/modelo/mat en blanco; cada nombre se repite N veces
- Checkbox Folio independiente
- Anchos: UBIC/Mat/Modelo estrechos; más espacio para Av1…AvN

## [3.21.1] — 2026-08-31

### Suministro: vertical + tinta + tipografía
- Orientación **vertical (retrato)** en Excel e impresión
- Máximo **10 columnas** totales (avances se limitan según Modelo/Mat/Obs)
- Temas de color: cian, magenta, amarillo, verde, gris/negro, claro, por material
- Letras: muy chica → muy grande

## [3.21.0] — 2026-08-31

### Suministro: ajustes de impresión
- Barra de opciones: avances (2–6), filas extra, papel (Carta/Oficio/A4), letra, colores
- Mostrar/ocultar Modelo, Material, Observaciones
- Excel e impresión usan los mismos parámetros
- Márgenes ~12 mm / 0.5" (impresoras de escritorio)

### Licencia
- Proyecto bajo **GPL-3.0-or-later** (`LICENSE`)

## [3.20.1] — 2026-08-31

### Una sola instancia de launcher
- Mutex/lock: no permite dos launchers a la vez (ni dos iconos en bandeja)
- El segundo intento muestra aviso y sale
- El arranque del servidor sigue liberando el puerto 8000 de procesos previos

## [3.20.0] — 2026-08-31

### Suministro diario (estilo papel)
- Nueva vista **/suministro** e Excel con fecha/día impresos
- UBIC, NOMBRE, FOLIO, MODELO, MAT prellenados
- 4 celdas de avance vacías + TOTAL (fórmula) + observaciones
- 2 filas amarillas por trabajador para folio nuevo del día
- Botón **Suministro día** en Plata

## [3.19.15] — 2026-08-31

### Fix: gramos de «Un día» no visibles en tabla
- `buscar_linea` prefiere filas visibles (no terminadas / trabajo activo)
- Al actualizar una línea terminada, se reabre para que aparezca
- Match de gramos existentes por folio+material exactos (no parcial)
- Toast confirma gramos guardados y total de la fila

## [3.19.14] — 2026-08-31

### Fix: gramos con un decimal (4.4, 3.1…)
- Inputs de avances y editar fila usaban `step=1` (solo enteros)
- Ahora `step=0.1` para permitir un decimal

## [3.19.13] — 2026-08-31

### Fix menú ⋯ de fila + columna compacta
- Reescrito `row_menu.js` con delegación de eventos
- `folio_actions` ya no intercepta clics del menú de fila
- Columna de acciones más estrecha; botón ⋮ estilizado
- Panel del menú en portal fijo (no se recorta)

## [3.19.12] — 2026-08-31

### Fix: error interno en /produccion
- Contexto incompleto (faltaba `materiales` en TemplateResponse)
- `n_lote_inactivos` calculado en Python (no Jinja selectattr)
- `_ctx` más defensivo ante valores raros

## [3.19.11] — 2026-08-31

### Terminar folio en lote
- Botón «Terminar lote (N con 3+ semanas)» en Sin avance
- Cierra todos los inactivos con más de 2 semanas sin gramos
- Reactivar individual sigue disponible

## [3.19.10] — 2026-08-31

### Fix fatal: arranque del servidor
- `app/api/routes.py`: `from __future__` debe ir al inicio (código de catálogos estaba antes y rompía el import)

## [3.19.9] — 2026-08-31

### Catálogos desde BD
- Nueva sección **Catálogos** (materiales/tarifas + modelos)
- Desplegables de Plata leen  activo
- Al elegir material se sugiere $/g desde BD
- CRUD vía UI (ya no solo HeidiSQL)

## [3.19.8] — 2026-08-31

### Varios avances en un día + totales al editar
- Modal **＋ Un día**: varios gramajes parciales que se suman con vista previa
- Opción «Sumar a lo ya capturado este día»
- Editar fila: total de gramos y efectivo estimado en vivo

## [3.19.7] — 2026-08-31

### Fix duro: Terminar / Reactivar
- Nuevo `folio_actions.js` con delegación de eventos (capture)
- Botones con `data-prod-id` / `data-action` (no dependen de onclick roto)
- Toast siempre con fallback a `alert`
- Clicks no se pierden por overlays del panel «Sin avance»

## [3.19.6] — 2026-08-31

### Fix: botón Terminar en Sin avance
- Terminar funciona aunque la línea no tenga trabajo_id (marca [terminado] en la línea)
- API con códigos 400/500 claros; JS valida prodId
- Reactivar limpia la marca en producción

## [3.19.5] — 2026-08-31

### Sin avance: tiempo de inactividad
- Cada folio muestra cuántas semanas seguidas lleva sin gramos
- Texto de última actividad (semana + gramos) cuando hay historial
- Orden: más tiempo inactivo primero

## [3.19.4] — 2026-08-31

### Plata: edición temporal desde dashboard
- «Completar ayer» / avisos de día abren Plata con `dia=` y desbloquean esa columna solo en la visita
- Filtro de filas sin gramos de ese día + banner de sesión
- Folios / sin firmar / sin hoy siguen filtrando y resaltando

## [3.19.3] — 2026-08-29

### Launcher: minimizar → bandeja (opcional)
- Al minimizar, si la opción está activa, pasa a la bandeja y avisa la primera vez
- Checkbox: *Al minimizar → bandeja* (desmarcar = se queda en la barra de tareas)
- Menú de bandeja ampliado: mostrar, iniciar/detener servidor, navegador, API, backup, carpeta, salir
- Preferencia guardada en `config.ini` [launcher]

## [3.19.2] — 2026-08-29

### Launcher: ícono en barra de tareas + botón Bandeja
- `AppUserModelID` propio (ya no se agrupa como Python genérico)
- Botón **Bandeja** visible en Sistema
- Ícono reforzado (iconbitmap + iconphoto)

## [3.19.1] — 2026-08-29

### Launcher: sin consola, bandeja e ícono
- `start.bat` / `start_silent.vbs` sin mensajes si hay Python (pyw/pythonw/venv)
- Ícono colorido (moneda/nómina + check) en `logo.ico` / ventana / acceso directo
- Botón **Bandeja**: oculta el centro de control en el área de notificación
- Acceso directo prioriza `pythonw` + `launcher.py`

## [3.19.0] — 2026-08-29

### Fase A (cimiento hacia 4.0)
- Migraciones versionadas al arranque (`schema_migrations` + `db/schema/001+`)
- Tests: export en ceros, migrate parser, umbral consistencia
- Arranque silencioso: `start.bat` + `start_silent.vbs` (sin consola); `start_dev.bat` con consola
- Paquete de íconos SVG en `/static/icons/`
- Dev: **Reparación inteligente** + comandos útiles (migrar, sync, huérfanos, APIs)

## [3.18.14] — 2026-08-29

### Dashboard compacto + deep links
- «Qué revisar hoy» colapsable y en filas compactas
- «Revisión de datos» colapsable y **Ocultar por hoy**
- Botones llevan a Plata con filtro (`sin_hoy`, `sin_firma`) o `q=folio` y resaltan la fila

## [3.18.13] — 2026-08-29

### Consistencia: recalcular sí limpia lo reparable
- Separa avisos **reparables** (resumen, enlaces) vs **manuales** (folios en varias personas)
- «Recalcular totales» actualiza resúmenes + enlaza trabajador_id; los folios duplicados **no** se borran solos
- Folios solo se revisan en semanas recientes (no spam de semana histórica id=1)
- Mensaje claro tras reparar: cuántos se corrigieron y cuántos quedan

## [3.18.12] — 2026-08-29

### Fix
- `dashboard.html`: `{% endif %}` faltante en banner de consistencia (TemplateSyntaxError)

## [3.18.11] — 2026-08-29

### Dashboard: totales vivos + motor de consistencia
- PLT/PIT/TLL del dashboard se calculan desde captura real (no solo `resumen_nominas`)
- Al **cerrar semana** se recalcula y guarda el resumen
- Motor de consistencia: avisa desfaces resumen↔captura, folios duplicados, líneas sin enlace
- Botón **Recalcular totales** en el dashboard

## [3.18.10] — 2026-08-28

### Export: regla fija “en 0 no se exporta”
- **Pita:** solo filas con efectivo > 0
- **Taller:** solo filas con sueldo/extras/total > 0
- Aviso antes de exportar (cuántas van / cuántas se omiten; bloqueo si todas están en 0)

## [3.18.9] — 2026-08-28

### Taller: sueldo fijo desde catálogo
- Badge Fijo/Var ya toma `sueldo_modo` del trabajador aunque falte `trabajador_id` en la línea
- Enlace automático por nombre + ubicación
- Al agregar línea, resuelve trabajador y copia sueldo base si es fijo

## [3.18.8] — 2026-08-28

### Torcedores en nómina Taller
- Van en bloque aparte en el Excel (después del resto del taller)
- Pago = **pitas × $3.20** (precio editable)
- Campo **Pitas** en UI y migración `005_taller_pitas_torcedor.sql`

## [3.18.7] — 2026-08-28

### Unir fichas compacto + similares + descartar
- Panel colapsable (menos espacio)
- Detecta nombres similares en la misma ubicación
- **Descartar** oculta la sugerencia 7 días (vuelve a salir después)
- Barra de acciones fija en Trabajadores (estilo Plata)

## [3.18.6] — 2026-08-28

### Export Pita/Taller = tabla en pantalla
- Pita ya no exige efectivo > 0 (exportaba vacío con montos en 0)
- Taller exporta todas las filas con nombre (igual que la UI)

## [3.18.5] — 2026-08-28

### Fix Pita/Taller
- `listar_por_semana` de Pita y Taller ya no reciben `incluir_terminados` (solo aplica a Plata)

## [3.18.4] — 2026-08-28

### Folios terminados: ocultar, purgar y reactivar
- Al marcar terminado se oculta de la captura (se conservan gramos para el pago)
- Lista colapsable de terminados con **Reactivar**
- Purga automática a los 7 días sin actividad (historial de nómina intacto)

## [3.18.3] — 2026-08-28

### Plata: menos ruido, captura a mano
- Avisos de folios colapsados en una sola línea (expandir solo si hace falta)
- Barra ＋ Un día / Fila / Cerrar… fija junto a la tabla al hacer scroll

## [3.18.2] — 2026-08-28

### Unir fichas y marcar terminado en la UI diaria
- **Trabajadores**: panel «Unir fichas duplicadas» (principal vs baja) sin pasar por Dev
- **Plata**: avisos de folios sin avance / reasignación + «Marcar folio terminado» en el menú de fila
- API: `POST /api/produccion/linea/{id}/terminar`, `GET /api/trabajadores/duplicados`

## [3.18.1] — 2026-08-28

### UX fusión, reasignaciones y asistente
- Fusión de duplicados con labels claros (principal vs baja)
- Folios sin avance con botón «Marcar terminado» y enlace a Plata
- Detección de reasignaciones (folio con avance que cambió de persona)
- Página `/asistente` (wizard) + badge **Ayuda**

## [3.18.0] — 2026-08-28

### Inteligencia operativa + fusión + aprendizaje
- Folio compartido: sin rayas/fondo rosa; solo subrayado del folio
- Folios sin avance (posible fin o reasignación)
- Fusión de trabajadores duplicados en toda la BD
- Script `db/schema/004_aprendizaje_merge.sql`

## [3.17.10] — 2026-08-26

### Fix visual tablas Plata
- Folio duplicado: barra solo en el borde de la fila (ya no rayas rosa en cada columna)
- Encabezados alineados con clases de columna; sin sticky lateral fantasma

## [3.17.9] — 2026-08-26

### Export Excel de trabajadores
- `GET /api/export/trabajadores` (todos) y `?activos=1` (solo activos)
- Botones **Excel** / **Excel activos** en la página Trabajadores

## [3.17.8] — 2026-08-26

### Dev: huérfanos, semana, migraciones, folios dup + orden tablas
- Reparar vínculos huérfanos; semana actual (crear si falta); columnas de migración
- Folios repetidos entre trabajadores (Dev + resalte en Plata)
- Orden asc/desc por columna + Reset orden (Plata, Trabajadores, …)

## [3.17.7] — 2026-08-26

### Panel Dev reubicado y útil
- Acceso **solo** junto a versión / IP (badge), fuera del menú de captura
- Panel con KPIs (BD, desajustes, conteos), integridad, esquema, acciones de sync
- Sin botón Dev duplicado en Trabajadores ni en la nav principal

## [3.17.6] — 2026-08-26

### Sync real + lectura desde catálogo + Dev
- **Plata/Pita/Taller**: al listar, `nombre`/`ubic` salen del catálogo (`JOIN trabajadores`)
- Sync más agresivo: por `trabajador_id` y por nombre único
- Página **Dev** (`/dev`): desajustes, muestra Vela, tipos de columna, botón sincronizar
- Commit explícito tras sync

## [3.17.5] — 2026-08-26

### Sincronización catálogo → nóminas
- Al editar un trabajador, se propagan `nombre` y `ubic` a `produccion_plata`, `produccion_pita` y `nomina_taller`
- Taller también actualiza `puesto`
- API: `POST /api/trabajadores/{id}/sincronizar` y `POST /api/trabajadores/sincronizar-todo`
- Botón **Sincronizar nóminas** en Trabajadores (repara datos ya guardados)

## [3.17.4] — 2026-08-24

### QR aislado (sin Jinja)
- Módulo `app/web/qr_pages.py`: HTMLResponse puro para QR individual, lote y móvil
- Evita TypeError de TemplateResponse al abrir `/trabajadores/{id}/qr`

## [3.17.3] — 2026-08-24

### Estabilidad del dashboard y contexto de plantillas
- Causa: `_plain_row` convertía dicts anidados a `str` → error `str has no attribute 'actual'`
- Nuevo módulo `app/web/context.py` con normalización **recursiva** (Decimal/date, sin aplanar mal)
- Guard en plantilla de tendencias; listado trabajadores tolerante a fallos SQL

## [3.17.2] — 2026-08-24

### QR y sueldo taller usables
- Corregido error de plantilla al abrir QR (`_ctx` + filas planas)
- QR individual + **QR de todos** (`/trabajadores/qr-lote`)
- Desempeño en modal (ya no solo alert)
- Selector Fijo/Variable y sueldo base en la tabla (TLL)

## [3.17.1] — 2026-08-24

### Hotfix UI / robustez 3.17
- Formulario trabajadores: campos sueldo_modo / sueldo_base (faltaban en HTML)
- Fallbacks SQL si no se ha corrido migración 003
- Badges fijo/var en Taller; colspan y estilos
- set_activo / desempeño tolerantes a falta de `terminado_en`

## [3.17.0] — 2026-08-24

### Taller fijo/variable, folios y QR
- `sueldo_modo` / `sueldo_base` en trabajadores (migración `003_taller_fijo_folio_qr.sql`)
- Duplicar semana Taller: fijos copian sueldo; variables en blanco
- Folio terminado (`terminado_en`) + menú «¿Terminó el folio?»
- Desempeño por trabajador (API + botón en lista)
- QR por trabajador (`/trabajadores/{id}/qr`) y vista móvil `/m/t/{id}`

## [3.16.4] — 2026-08-23

### Integridad y paridad escritorio/web
- Doc `docs/INTEGRIDAD_Y_PARIDAD.md`
- GUI escritorio: **Abrir web** y diálogo de paridad (qué falta vs web)
- HTTPS/móvil: documentado como pendiente (vista reducida, no sitio completo)

## [3.16.3] — 2026-08-23

### Launcher: estado real del servidor
- Verde solo si el **puerto responde** (no basta el proceso)
- Al iniciar: libera el puerto de instancias previas
- Sin `--reload` (más estable en Windows)
- Si no arranca: muestra cola del log y limpia
- Navegador abre `127.0.0.1` (no localhost ambiguo)

## [3.16.2] — 2026-08-23

### start.bat + integración
- `start.bat` arranca el launcher con `.venv` (pythonw) o fallback `py`/`python`
- Acceso directo e Inicio de Windows apuntan a `start.bat` + `logo.ico`
- README: tabla de arranque integrado

## [3.16.1] — 2026-08-23

### Icono de acceso directo
- `app/web/static/logo.ico` multi-tamaño (16–256) a partir del logo del taller
- Accesos de Escritorio e Inicio de Windows usan el icono

## [3.16.0] — 2026-08-23

### Launcher moderno + backup + inicio Windows
- UI del launcher simplificada (servidor, BD, sistema)
- **Backup al cerrar** y **Backup ahora** → carpeta `backups/`
- Opción **Iniciar con Windows** (carpeta Startup)
- README completo: portable, scripts, backup, pendientes (start.bat + ico)

## [3.15.0] — 2026-08-23

### Portable + acceso directo Windows
- scripts/create_desktop_shortcut.ps1
- scripts/make_portable.ps1
- scripts/verify_env.ps1
- Launcher: Acceso directo y Verificar

## [3.14.1] — 2026-08-23

### Semanas en tarjetas (acciones visibles)
- Rediseño: ya no usa tabla compacta (ocultaba botones)
- Acciones: Editar, Alinear a actual, Abrir Plata/Pita/Taller, Eliminar, Cerrar/Reabrir
- Avisos según si es actual, tiene datos o está vacía

## [3.14.0] — 2026-08-23

### Gestión de semanas
- Página `/semanas`: listar, editar código/fechas, eliminar vacías
- **Alinear a actual**: corrige fechas a sáb–vie de hoy sin perder datos
- Bloqueo de borrado si hay líneas Plata/Pita/Taller

## [3.13.4] — 2026-08-22

### Corrección de semanas sáb–vie
- Al duplicar, la semana siguiente ya no se salta (bug cuando fecha_fin no era viernes)
- Búsqueda de destino por **fechas**, no solo por código
- Código con mes si cruza de mes (`29/08-04/09`)
- API `PATCH /api/semanas/{id}` para corregir código/fechas

## [3.13.3] — 2026-08-22

### Captura manual + fix popup
- Captura manual incluye columna **$/Gr**
- Los modales ya no se cierran al seleccionar texto en un campo

## [3.13.2] — 2026-08-22

### Nómina en blanco para captura manual
- Export Excel estilo formal **sin precios** (solo gramos + Total Gr con fórmula)
- Incluye todas las líneas de la semana y **una fila en blanco extra por trabajador**
- Botón **Captura manual** en Plata · `/api/export/produccion/{id}/captura-manual`

## [3.13.1] — 2026-08-22

### Excel formal con fórmulas
- Plata: Total Gr = `SUM` días; Efectivo = Total Gr × $/Gr; totales y SUMIF por material
- Taller: Total = Sueldo + Extras; fila TOTAL con `SUM`
- Pita: TOTAL Efectivo con `SUM`
- Resumen: gran total con `SUM`

## [3.13.0] — 2026-08-22

### Bloque A — captura diaria + gramos a 1 decimal
- Gramos y precios: `step=0.1` (flechas de 0.1, no 0.01)
- Confirmación si gramos raros vs promedio / umbral
- Deshacer último gramo (botón ↩)
- Enter en Solo hoy / Plata avanza al siguiente pendiente
- Página `/historial/{semana_id}` (ya no JSON crudo)
- Script SQL `002_historial.sql` si falta la tabla

## [3.12.2] — 2026-08-22

### No re-duplicar semanas ya copiadas
- Si el destino ya tiene las líneas, no crea duplicados (`ya_duplicada`)
- Plata solo copia líneas de la semana origen (no todo el catálogo)
- Mensaje claro con omitidas vs creadas

## [3.12.1] — 2026-08-22

### Cerrar semana en todas las áreas + duplicar con opciones
- Cerrar / Reabrir en **Pita** y **Taller** (semana global)
- Duplicar: las tres áreas o solo la actual
- Bloqueo de edición si la semana está cerrada
- `semana_ops.js` compartido

## [3.12.0] — 2026-08-22

### Paridad escritorio ↔ web
- Pestañas: Inicio, Solo hoy, Plata, Pita, Taller, Folios, Trabajadores, Resumen
- Temas Oscuro / Claro / Taller (mismos nombres que la web)
- Solo hoy / Pita / Taller leen la misma BD vía `app`
- Barra: fecha, versión, tema, buscar, URL web

## [3.11.3] — 2026-08-22

### Fix menú recortado + columna estrecha
- Menú de fila renderizado en `body` con `position:fixed` (ya no queda dentro de la fila / overflow)
- Columna ⋯ fijada a 28px en Plata y Taller

## [3.11.2] — 2026-08-22

### Fix menú ⋯ + umbral de rarezas
- Menú de fila: ya se abre (no se cierra en el mismo clic)
- Columna más estrecha; botón ⋯ con tooltip claro
- Umbral de rarezas configurable en Inicio (API `/api/ops/settings`)

## [3.11.1] — 2026-08-22

### Acciones compactas (⋮) + doble clic en nombre
- Columna ACC reducida a un solo ⋮ (Plata, Pita, Taller, Folios)
- Menú: Editar fila… / Eliminar (o Desactivar en Folios)
- Doble clic en el nombre abre el mismo modal de edición
- Se conservan edición por celda (gramos, inline Pita/Taller)

## [3.11.0] — 2026-08-22

### Plata edición + Trabajos como catálogo
- Plata: columna Acciones clara (✎ editar fila / × eliminar), ayuda de captura
- **Trabajos → Folios**: catálogo de folios activos (ya no duplica la matriz de Plata)
- Editar/desactivar trabajos; gramos de hoy solo informativos
- Cerrar hoy + suministro se mantienen en Folios

## [3.10.0] — 2026-08-22

### Fix Decimal + dashboard vivo + solo hoy
- Corregido `TypeError: Decimal is not JSON serializable` en `|tojson`
- Tendencias: % vs semana anterior, sparkline, top materiales
- Vista **Solo hoy** (`/solo-hoy`): captura rápida del día
- API tendencias y solo-hoy

## [3.9.0] — 2026-08-22

### Edición de fila completa (popup)
- Botón ✎ en **Plata, Pita y Taller** abre modal con todos los campos de la línea
- PATCH fila completa Plata (`/api/produccion/linea/{id}`)
- `row_edit.js` compartido; cierra y recarga al guardar

## [3.8.1] — 2026-08-21

### Fix edición inline Taller/Pita
- `readonly` HTML se quita/pone correctamente al editar
- Evita carrera blur tras `confirm()`
- Botón ✎ en cada celda editable (además de doble clic)
- HTML `colgroup` corregido en tabla Taller

## [3.8.0] — 2026-08-21

### Pronóstico, duplicar 3 nóminas y alertas de cierre
- **Pronóstico de cierre Plata**: estima gramos/$ con promedio diario de días capturados
- **Duplicar → sig. semana** en Inicio, Plata, Pita y Taller (PLT + PIT + TLL)
- Alertas: semana vencida sin cerrar, último día de semana, **día anterior sin gramos** en Plata
- API: `GET /api/insights/pronostico/{id}`, `POST /api/insights/duplicar/{id}`

## [3.7.0] — 2026-08-21

### Inteligencia operativa (reglas + estadísticas)
- **Qué revisar hoy** en el dashboard (semana, gramos de hoy, firmas, PLT sin línea)
- **Autocompletar** folio/modelo/material/tarifa al elegir trabajador (último trabajo o producción)
- **Checklist pre-export** Formal Excel Plata (líneas con gramos, firmas, rarezas ±30 % vs historial)
- API: `/api/insights/hoy`, `/api/insights/sugerir-trabajo`, `/api/insights/rarezas/{id}`, `/api/insights/checklist/{id}`

## [3.6.2] — 2026-08-21

### Edición de campos robusta
- Parseo numérico seguro, solo claves enviadas en PATCH
- Escape restaura valor; sin cambios no llama API
- `cell_edit.js` compartido Pita/Taller

## [3.5.0] — 2026-08-21

### Edición inline + temas
- Pita/Taller: celdas editables con doble clic + confirmación
- Temas: Oscuro, Claro, Taller (persistidos en localStorage)
- PATCH `/api/nomina-pita/linea/{id}` y `/api/nomina-taller/linea/{id}`

## [3.4.2] — 2026-08-21

### Export limpio
- Filas sin gramos en ningún día no salen en Excel/PDF/CSV formal de Plata
- Taller/Pita: se omiten líneas con total/efectivo en cero

## [3.4.1] — 2026-08-21

### Export Excel formal por área
- Taller / Pita / Resumen 3 nóminas imprimibles
- Endpoints export nomina-taller, nomina-pita, resumen

## [3.4.0] — 2026-08-21

### Nóminas Taller (TLL) y Pita (PIT)
- Tablas `nomina_taller` y `produccion_pita` + migración `001_nomina_taller_pita.sql`
- Vistas por área: `v_trabajadores_plt/pit/tll`, `v_totales_semana`
- Web: `/nomina-taller`, `/nomina-pita`, API resumen tres nóminas
- Excel: hojas Nomina-TLL y Nomina-PIT + instrucciones
- Trabajadores unificados; tipo define el área

## [3.3.1] — 2026-08-21

### UX para usuarios poco experimentados
- Guía de 4 pasos en Inicio (se puede ocultar)
- Consejos en Producción, Trabajadores y Trabajos
- Botones más grandes; estados vacíos con instrucciones
- Textos en español sencillo

## [3.3.0] — 2026-08-21

### Trabajadores: edición, cambios y bajas
- Web: modal editar / nuevo, Baja y Reactivar
- API: PUT/PATCH, POST baja, POST activar
- Desktop: diálogo editar, baja y reactivar (doble clic en fila)

## [3.2.4] — 2026-08-21

### Revisión exhaustiva
- **CRÍTICO:** `autocommit=True` en conexiones MySQL (app + desktop) — los INSERT ya persisten
- Plantilla producción: `{% endif %}` faltante en toolbar
- Formularios inline duplicados eliminados (quedan popups)
- `api/duplicar` valida semana origen
- Alias de días (sab→gm_sab) en desktop
- Error 1146 (tabla faltante) se registra como warning

## [3.2.3] — 2026-08-21

### UI web más fluida
- Microinteracciones en botones (hover/active)
- Modal y toast animados
- Flash en celda/fila al guardar gramos
- KPI pulse + columna trabajador sticky
- `prefers-reduced-motion` respetado

## [3.2.2] — 2026-08-21

- Solo SQL `000_fajos_central_completo.sql` (incluye `cierre_dia`)
- Excel: trabajadores faltantes en catálogo desde producción
- Encabezados de tabla fijos al scroll (web)
- Agregar día / fila en popup modal

## [3.2.1] — 2026-08-21

### Corregido
- IndentationError en launcher (bloque LAN)
- `cierre_dia`: crear tabla automáticamente / no romper avisos
- Captura un solo día: actualiza línea existente + selector de trabajos
- `submitUnDia` restaurado en web + filtros de tabla

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
