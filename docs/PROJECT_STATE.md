# PROJECT_STATE — Fajos Central

> Archivo de checkpoint legible por humanos e IAs.
> Actualizar este archivo en cada hito relevante del proyecto.
> Última actualización: 2026-09-22 | Versión app: **3.25.6**
> **Entorno del usuario (obligatorio tener en cuenta):** Windows 10/11 + **PowerShell 7** + HeidiSQL/MariaDB.

---

## 0. Entorno de desarrollo y ejecución (OBLIGATORIO)

| Elemento | Valor |
|----------|--------|
| SO | **Windows** (10 u 11) |
| Shell | **PowerShell 7** (`pwsh`) — no asumir bash/Linux |
| Python | 3.10+ (recomendado instalado con `py -3`) |
| Base de datos | MariaDB + **HeidiSQL** |
| Repo | https://github.com/ArmandoHoyosfg/fajos_central.git |

### Implicaciones para código y scripts
- Rutas: preferir `pathlib.Path`; no hardcodear `/home/...`.
- Activar venv: `.\.venv\Scripts\Activate.ps1`
- Si falla la política de ejecución: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
- Arranque recomendado: `pwsh -File .\start.ps1` o `python launcher.py`
- Setup primera vez: `pwsh -File .\setup_windows.ps1`
- Matar procesos del servidor en Windows: `taskkill` (ya usado en `launcher.py`)
- No documentar solo comandos Linux; siempre incluir equivalente PowerShell 7.

### Comandos habituales (PowerShell 7)

```powershell
cd ruta\a\fajos_central
# Import Excel (simulación luego --apply)
python scripts\import_excel.py .\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx

pwsh -File .\setup_windows.ps1   # primera vez
pwsh -File .\start.ps1           # launcher GUI
python launcher.py
python run.py
pytest
git push -u origin main --tags
```

---

## 1. Qué es este proyecto

Sistema de **nóminas y producción** del **Taller de Fajos Central** (bordado en plata / pita / taller).

Objetivos:
- Digitalizar la captura diaria y semanal de gramos/producción
- Calcular efectivo automáticamente (gramos × tarifa)
- Generar hojas imprimibles (captura + formal con firma)
- Catálogos maestros (trabajadores, modelos, tarifas)
- Acceso web en red local (LAN) + API REST
- Exportar a Excel, CSV, PDF, JSON

Stack actual:
- **Backend/Web:** Python 3.10+, FastAPI, Jinja2, uvicorn
- **BD:** MariaDB (`fajos_central`)
- **Desktop legacy:** PySide6 (carpeta `desktop_legacy/`)
- **Launcher:** `launcher.py` (tkinter) + `start.ps1` / `setup_windows.ps1` (Windows PowerShell 7)
- **Tests:** pytest
- **Repo GitHub:** https://github.com/ArmandoHoyosfg/fajos_central.git

---

## 2. Estructura del repositorio

```
fajos_central/
├── VERSION, CHANGELOG.md, README.md
├── launcher.py, run.py, start.ps1, setup_windows.ps1
├── requirements.txt, pytest.ini, .env.example
├── app/                    # App principal FastAPI
│   ├── core/               # config, exceptions, logging
│   ├── db/                 # connection, repository
│   ├── services/           # dashboard, export multi-formato
│   ├── api/                # rutas REST + páginas HTML
│   └── web/templates/      # dashboard, trabajadores, produccion
├── db/schema/001_schema_inicial.sql
├── tests/
├── templates_excel/        # Excel optimizado de referencia
├── scripts/                # CLI automatización
├── desktop_legacy/         # GUI PySide6
└── docs/
    └── PROJECT_STATE.md    # ESTE ARCHIVO
```

---

## 3. Modelo de negocio (importante)

### 3.1 Trabajadores
- **Mismo nombre + distinta UBIC = personas diferentes** (conservar ambas).
- La UBIC **no es única**: varios trabajadores pueden compartir el mismo número de ubicación en la hoja de suministro.
- Clave lógica recomendada: `(nombre_mostrar, ubic)` o `id` autoincremental.
- Tipos: `PLT` (plata), `PIT` (pita), `TLL` (taller), `PLT/PIT`, `Mixto`.
- Campo `activo` + `fecha_incorporacion`.

### 3.2 Formato real que llenan a mano a diario — **SUMINISTRO**

Documento físico diario (foto de referencia 2026-08-15):

| Campo en papel | Significado |
|----------------|-------------|
| Título | **SUMINISTRO** |
| FECHA | Día del registro (ej. 15-08-26) |
| Día de la semana | Ej. Sábado |
| UBIC. | Número de ubicación |
| NOMBRE / BORDADOR | Nombre del trabajador |
| No. FOLIO / No. PEDIDO | Folio del trabajo (ej. ST-0576, P-328, F-019-3) |
| AG3 (varias columnas) | Lecturas parciales de gramos del día; a veces suman (ej. 3.7+4.6=8.3) |
| OBSERVACIONES | Notas, totales parciales en gramos |
| Totales cabecera | Ej. TOTAL AG3 = 243.5 ; DOL = 48 |

Notas operativas del papel:
- Hay filas resaltadas (folios tipo `F-xxx`) con tratamiento especial visual.
- Un trabajador puede aparecer en **varios folios**.
- El avance se anota **por día**; la nómina formal semanal concentra totales y firma.
- Materiales principales observados: **AG3**, **DOL** (y variantes en catálogo).

### 3.3 Flujo de nómina semanal (Excel / sistema)

1. **Captura** (`Nomina-Imprimir`): nombres+ubic prellenados, folio/modelo/material/$/gr y gramos por día (Sáb–Vie) manuales. **Sin totales.**
2. **Formal** (`Nomina-Formal`): se llena sola desde captura; calcula Total Gramos y Efectivo; columna Firma; imprimible.
3. **Resumen**: totales PLT + PIT + TLL por semana.

Regla de cálculo PLT:
```
total_gramos = suma(gm_sab … gm_vie)
efectivo = total_gramos × tarifa_gr
```
En MariaDB estas columnas son **GENERATED STORED**.

### 3.4 Tarifas material (referencia)
- AG3 ≈ $12/g
- AG4 / DOL / DLO ≈ $13/g
- Algunos modelos tienen tarifa distinta (MIL HOJAS 15, VIRGEN 14, PUNTO HUICHOL 17, etc.)

---

## 4. Base de datos (MariaDB)

Base: `fajos_central`

Tablas:
- `trabajadores`
- `modelos`
- `tarifas_material`
- `semanas`
- `produccion_plata` (detalle diario/semanal de gramos; totales generados)
- `resumen_nominas`

Vistas:
- `v_trabajadores_plt_activos`
- `v_resumen_produccion_semana`

Script: `db/schema/001_schema_inicial.sql` (ejecutar en HeidiSQL sobre la BD ya creada).

---

## 5. Cómo correr en Windows (PowerShell 7)

```powershell
cd ruta\a\fajos_central
# Import Excel (simulación luego --apply)
python scripts\import_excel.py .\templates_excel\NOMINA_FAJOS_OPTIMIZADA_2026.xlsx

pwsh -File .\setup_windows.ps1    # primera vez
# Si bloquea scripts:
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# Editar .env (usuario/clave MariaDB)

pwsh -File .\start.ps1            # abre launcher GUI
# o: python launcher.py
```

Launcher permite: iniciar/detener servidor, abrir navegador, app desktop legacy, abrir carpeta.

URL local: `http://127.0.0.1:8000`  
Otros PCs en la red: `http://IP_DEL_SERVIDOR:8000`  
API docs: `/docs`

---

## 6. Historial de versiones

| Versión | Qué incluye |
|---------|-------------|
| 1.0.0 | Excel optimizado, SQL inicial, CLI, prototipo PySide6 |
| 2.0.0 | Consolidación en una carpeta; FastAPI web; export multi-formato; tests; errores estructurados |
| 2.1.0 | Launcher GUI (tkinter) |
| 2.1.1 | Scripts PowerShell 7; log de servidor en Windows |
| 2.2.0 | Import seguro Excel; captura web producción; schema suministro |
| 2.3.0 | UI dark-first + logo; HTTPS local opcional con redirección |
| 3.x | Evolución continua: migraciones al arranque, motor de consistencia, Dev panel, launcher bandeja, export multi-formato, tests |

Tags git: `v2.0.0`, `v2.1.0`, `v2.1.1`

> **Nota 2026-09-22:** La versión real del proyecto es **3.25.6** (ver `app/__init__.py` y `VERSION`).
> La tabla anterior refleja solo los hitos documentados hasta 2.3.0. Para el historial completo ver `CHANGELOG.md`.

---

## 7. Decisiones de diseño vigentes

- Fuente de verdad del código: carpeta **`fajos_central`** (no usar copias sueltas antiguas).
- Web primero (LAN); desktop PySide6 es **legacy/referencia**.
- Errores de negocio: JSON con `code`, `message`, `user_message`, `details`, `cause` (útil para humanos e IAs).
- No versionar `.env`, `logs/`, `exports/`, `.venv/`.

---

## 8. Pendientes / roadmap sugerido

- [x] Captura web de producción semanal (crear semana, alta/baja líneas, export)
- [ ] Captura diaria tipo **SUMINISTRO** (UI sobre tablas suministro_*)
- [x] Modelo SQL **suministro_diario / suministro_detalle / import_log** (schema 002)
- [ ] UI web del suministro diario
- [ ] PIT y TLL con el mismo rigor que PLT
- [ ] Cierre de semana + estado de firmas
- [ ] Auth simple en red local
- [x] Importación segura Excel → MariaDB (dry-run + apply, script PowerShell)
- [ ] Alinear catálogo trabajadores con nombres/ubic del papel (ej. Trinidad 376, Carlos Abel 416, etc.)

---

## 9. Instrucciones para la siguiente IA / desarrollador

1. Leer este archivo completo antes de cambiar esquema o UI.
2. Respetar la regla **nombre+ubic = persona**; no fusionar por nombre solo.
3. El papel diario es **SUMINISTRO** (gramos del día + folio); la nómina formal es **semanal**.
4. Entorno del usuario: **Windows + PowerShell 7 + HeidiSQL/MariaDB** (ver sección 0). No asumir bash, Linux ni macOS como entorno principal.
5. Repo remoto: `https://github.com/ArmandoHoyosfg/fajos_central.git`
6. Tras cambios relevantes: actualizar `VERSION`, `CHANGELOG.md` y **esta sección 6–8**.
7. **La versión de referencia es la de `app/__init__.py`** (`__version__`). `VERSION`, `README.md` y este archivo deben coincidir con ella. Si hay discrepancia, `app/__init__.py` gana.

### Contexto de conversación (resumen)
- Se optimizó un Excel de nóminas multi-hoja caótico.
- Formal debe calcularse sola desde la captura; ambas imprimibles.
- Se migró a MariaDB + Python + web FastAPI.
- Usuario prefiere robustez, UI intuitiva, tests y reportes de error claros.
- Formulario real diario enviado: hoja SUMINISTRO 15-08-26 (AG3/DOL, folios ST/P/F, observaciones).

---

## 10. Checkpoint de sesión — 2026-09-22

**Versión actual:** 3.25.6
**Objetivo de la sesión:** Refactor estructural en bloques de trabajo ≤ 1 hora, con timer de calibración.

### Bloques planeados (en orden de ejecución)

| # | Bloque | Estado | Tiempo real | Notas |
|---|--------|--------|-------------|-------|
| 0 | Calibración + timer (`scripts/task_timer.py`) | ✅ | ~15 min* | Script probado, registra en `logs/task_timer_*.jsonl` |
| 1 | Refrescar `PROJECT_STATE.md` | ✅ | **~60 min** | Versión + fecha + tabla de hitos + instrucción #7 + sección 10 |
| 2 | Unificar versión (README / VERSION / `__init__.py`) | ✅ | **~45 min** | README 3.22.0→3.25.6; CHANGELOG reordenado + entry 3.25.6; VERSION ya coincidía |
| 3 | Mover `cierre_dia` al sistema de migraciones | ⏳ | — | Eliminar `CREATE TABLE` de `dia_service.py` |
| 4 | Dividir `routes.py` en routers por dominio | ⏳ | — | El más valioso; requiere pytest en verde antes/después |
| 5 | Verificación final + cierre | ⏳ | — | pytest completo + timer + git status |

> \* **Tiempo real** = desde que el usuario envía el mensaje hasta que termina la respuesta de la IA.
> Incluye: procesamiento del prompt, lectura de archivos, planificación, edición, verificación, debug y respuesta final.
> NO es lo mismo que el "duración" del script `task_timer.py` (que solo mide el proceso Python).

### Calibración de esta máquina (medida 2026-09-22)

**A. Overhead de procesos Python (tiempo de I/O real en la máquina):**
| Métrica | Tiempo |
|---------|--------|
| Import dependencias (fastapi+pydantic+pandas) | ~2.2 s |
| Import `app.main` completo | ~0.7 s |
| pytest `--collect-only` (19 tests) | ~0.8 s |
| Overhead de arranque Python por proceso | ~0.2 s |

**B. Tiempo real de bloques de trabajo (medido por el usuario, 2026-09-22):**
| Bloque | Tipo de trabajo | Tiempo real (usuario → IA → usuario) |
|--------|----------------|---------------------------------------|
| 0 | Crear script + debug (encoding Win) + calibración | ~15 min |
| 1 | Refrescar docs (leer + 4 edits + verificación + 2 debug encoding) | **~60 min** |

> **⚠️ Lección crítica de calibración (2026-09-22):**
> El tiempo real de un bloque de trabajo en esta máquina es **10–20× mayor** que la suma de los procesos Python.
> El overhead dominante NO es la CPU de la máquina, sino:
> - **Procesamiento del prompt por la IA** (lectura, razonamiento, planificación)
> - **Lectura de archivos** (cada `read_file_lines` tiene latencia de red/almacenamiento)
> - **Ediciones** (cada `edit_file_tool` / `replace_file` implica round-trip)
> - **Verificaciones** (cada `shell_command` arranca un proceso Python completo: ~0.2–3 s)
> - **Debug iterativo** (los errores de encoding en Windows costaron 2 iteraciones extra en cada bloque)
>
> **Regla de calibración actualizada:**
> - Bloque de **solo docs** (1 archivo, pocos edits): **~45–90 min**
> - Bloque de **código + verificación** (import + pytest): **~60–120 min**
> - Bloque de **refactor estructural** (mover código entre archivos): **~90–180 min**
>
> **Recomendación de planificación:**
> - No asumir que un bloque "pequeño" dura 5–10 min. En esta máquina, **todo bloque real dura mínimo 30–45 min**.
> - Para sesiones de 1 hora, planificar **1 solo bloque** bien definido, no varios.
> - Incluir siempre **margen de 2×** en la estimación.
> - El encoding de Windows (cp1252) es una fuente constante de debug: siempre usar `python -X utf8` o el timer (que ya fuerza UTF-8).

> **Uso del timer:** `python scripts/task_timer.py --task "Nombre del bloque" --body --save logs`
> Registros: `logs/task_timer_YYYYmmdd.jsonl`
> **Nota:** el timer mide solo el proceso Python, NO el tiempo total del bloque. Para el tiempo real, usar la hora del reloj del usuario.

---

*Fin del checkpoint. Mantener este archivo en `docs/PROJECT_STATE.md`.*
