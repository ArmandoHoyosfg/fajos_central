# Archivos de la carpeta principal — ¿para qué sirve cada uno?

Proyecto: **fajos_central** · Entorno: **Windows + PowerShell 7**

Ruta típica: `...\fajos_central\`

---

## Cómo empezar (lo habitual)

| Acción | Qué usar |
|--------|----------|
| Uso diario | `python launcher.py` o `pwsh -File .\start.ps1` |
| Primera instalación | `pwsh -File .\setup_windows.ps1` |
| Base de datos | HeidiSQL + scripts en `db\schema\` |

---

## Archivos en la raíz

### `launcher.py`  ★ principal
**Centro de control gráfico.** Desde aquí puedes:
- Iniciar / detener el servidor web
- Abrir la web en el navegador
- Abrir la **app de escritorio** (PySide6)
- Abrir el Excel de nóminas
- Importar Excel a MariaDB (simulación o aplicar)
- Abrir carpeta del proyecto, guía de uso y scripts SQL

```powershell
python launcher.py
```

### `start.ps1`
Atajo de PowerShell 7: activa el `.venv` si existe y lanza `launcher.py`.

```powershell
pwsh -File .\start.ps1
```

### `setup_windows.ps1`
Instalación inicial en Windows: crea `.venv`, instala `requirements.txt`, copia `.env.example` → `.env`.

```powershell
pwsh -File .\setup_windows.ps1
```

### `run.py`
Arranca solo el servidor web por consola (sin ventana del launcher). Útil para depurar.

```powershell
python run.py
```

### `requirements.txt`
Lista de librerías Python de la app web (FastAPI, MariaDB, Excel, PDF, tests…).  
No instales a mano: usa `setup_windows.ps1` o `pip install -r requirements.txt`.

### `config.ini`  ★ conexión a la base de datos
Archivo **local** con usuario, contraseña y servidor MariaDB.

- Se crea desde el launcher: **Configurar conexión (usuario / contraseña)**
- O copia `config.ini.example` → `config.ini` y edítalo
- **No se sube a Git** (contiene la contraseña)
- Lo usan la web, el import y la app de escritorio

### `config.ini.example`
Plantilla sin contraseña. Ejemplo de estructura del `config.ini`.

### `.env.example`
Plantilla de configuración (host, puerto, usuario BD…).  
Cópiala a `.env` y pon tu contraseña de MariaDB. **No subas `.env` a Git.**

### `.env` (lo creas tú)
Configuración real del equipo. El launcher y la app la leen al iniciar.

### `VERSION`
Número de versión actual del proyecto (ej. `2.2.0`).

### `CHANGELOG.md`
Historial de cambios por versión.

### `README.md`
Resumen del proyecto, instalación y enlaces rápidos.

### `pytest.ini`
Configuración de pruebas automáticas. Uso avanzado:

```powershell
pytest
```

### `.gitignore`
Indica a Git qué no versionar (`.env`, logs, venv, etc.).

---

## Carpetas importantes

| Carpeta | Uso |
|---------|-----|
| `app\` | Código de la aplicación web (API + pantallas) |
| `db\schema\` | Scripts SQL para HeidiSQL (`001_...`, `002_...`) |
| `templates_excel\` | Excel optimizado de nóminas (captura + formal) |
| `scripts\` | Utilidades CLI (`import_excel.py`) |
| `desktop_legacy\` | App de escritorio PySide6 (opcional) |
| `docs\` | Guías: `USO.md`, `ARCHIVOS_RAIZ.md`, `PROJECT_STATE.md` |
| `tests\` | Pruebas automatizadas |
| `logs\` | Se crea al usar el launcher (logs del servidor) |

---

## Flujo recomendado

1. **Una vez:** `setup_windows.ps1` → editar `.env` → ejecutar SQL en HeidiSQL.  
2. **Cada día:** `launcher.py` → Iniciar servidor web → trabajar en el navegador.  
3. **Opcional:** App de escritorio desde el mismo launcher.  
4. **Importar Excel:** botón de simulación → revisar → botón aplicar.  

---

*Documento orientado a operadores del taller y a quien mantenga el sistema.*
