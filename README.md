# Fajos Central — Sistema de Nóminas

**Versión:** 3.16.1  
**Entorno:** Windows + PowerShell 7 + MariaDB/HeidiSQL  

Sistema de nóminas del **Taller de Fajos Central** (áreas **Plata**, **Pita** y **Taller**).

## Qué incluye

- **Launcher** Windows (Tk): iniciar/detener servidor, BD, backup, acceso directo, inicio con Windows
- Interfaz **web** en red local + API REST
- Captura diaria (gramos Plata, efectivo Pita, sueldos Taller)
- Export formal Excel/CSV/PDF, captura manual, Excel Master
- Gestión de **semanas** (editar, alinear a actual, eliminar vacías)
- Panel de avisos, rarezas, temas Oscuro / Claro / Taller

---

## Arranque rápido (tu PC)

```powershell
cd .\Documents\Proyectos Desarrollo\fajos_central\

# Primera vez
pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
copy config.ini.example config.ini
# Edita usuario/clave de MariaDB en config.ini o en el launcher

# Acceso directo en el Escritorio
pwsh -File .\scripts\create_desktop_shortcut.ps1

# Verificar entorno
pwsh -File .\scripts\verify_env.ps1

# Abrir centro de control
python .\launcher.py
```

En el launcher:

1. **Configurar** / **Probar** la base de datos  
2. **▶ Iniciar** el servidor y **🌐 Abrir** el navegador  
3. Opcional: **Iniciar con Windows**, **Backup al cerrar**

---

## Portable (copiar a otra PC, sin instalador)

```powershell
pwsh -File .\scripts\make_portable.ps1
```

Genera en el Escritorio `FajosCentral_portable_v…` (sin `.venv` ni `config.ini`).

**En el destino:**

1. Python 3.11+ (PATH + py launcher)  
2. MariaDB + ejecutar `db\schema\000_fajos_central_completo.sql` en HeidiSQL  
3. `pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1`  
4. `config.ini.example` → `config.ini`  
5. `pwsh -File .\scripts\create_desktop_shortcut.ps1`  
6. `python .\launcher.py`

---

## Scripts útiles (`scripts\`)

| Script | Uso |
|--------|-----|
| `setup_windows.ps1` (raíz) | Crea/repara `.venv` e instala dependencias |
| `create_desktop_shortcut.ps1` | Acceso directo en el Escritorio |
| `make_portable.ps1` | Carpeta limpia para copiar |
| `verify_env.ps1` | Checklist venv / config / app / schema |

---

## Backup

- **Backup al cerrar** (casilla en el launcher): al salir guarda en `backups\cierre_YYYYMMDD_HHMMSS\`:
  - `config.ini`
  - Excel **Master** de la BD (si la conexión responde)
  - `mysqldump` si el cliente está en el PATH (opcional)
- **Backup ahora**: mismo proceso sin salir
- Los formales exportados también se archivan en `exports\`

---

## Inicio con Windows

Casilla **Iniciar con Windows** en el launcher: crea o quita un acceso en la carpeta *Startup* del usuario (no requiere administrador). Abre el launcher al iniciar sesión; el servidor web no arranca solo hasta que pulses **Iniciar** (evita cargar la BD sin querer).

---

## Uso diario (web)

1. **Inicio** — panel *Qué revisar hoy*  
2. **Plata / Pita / Taller** — captura y export formal  
3. **Semanas** — alinear fechas, borrar vacías, cerrar/reabrir  
4. **Solo hoy** — captura rápida de gramos del día  

---

## Estructura

```
fajos_central/
├── launcher.py          # Centro de control
├── run.py               # Solo servidor CLI
├── config.ini.example
├── setup_windows.ps1
├── scripts/             # acceso directo, portable, verify
├── app/                 # FastAPI + web + servicios
├── db/schema/
├── backups/             # generadas al cerrar
├── exports/
└── desktop_legacy/      # GUI PySide6 (referencia)
```

---

## Pendiente / próximo

- `start.bat` — doble clic sin PowerShell  
- ~~Icono `.ico`~~ → `app/web/static/logo.ico` (regenerar acceso directo)

---

## Requisitos

- Python 3.10+  
- MariaDB (`fajos_central`)  
- `pip install -r requirements.txt` (vía `setup_windows.ps1`)
