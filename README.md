# Fajos Central — Sistema de Nóminas

**Versión:** 3.14.1  
**Entorno principal:** Windows + PowerShell 7 + MariaDB/HeidiSQL  

Sistema de nóminas del **Taller de Fajos Central** (Plata, Pita y Taller).

## Qué incluye

- Interfaz web en la red local (HTTPS recomendado) + launcher Windows
- API REST y dashboard con KPIs
- Captura diaria de gramos (Plata), efectivo (Pita) y sueldos (Taller)
- Exportación formal Excel/CSV/PDF y **Excel Master** (toda la BD)
- Inteligencia operativa ligera:
  - Panel **Qué revisar hoy**
  - Autocompletar trabajos al agregar líneas
  - Checklist y rarezas antes de exportar formal
  - Pronóstico de cierre y duplicar semana (3 áreas)
  - Alertas de cierre de semana y día anterior en Plata
- Temas visuales: Oscuro, Claro, Taller
- Tests con pytest y errores estructurados

---

## Estructura del proyecto

```
fajos_central/
├── VERSION                 # Semver actual
├── CHANGELOG.md
├── README.md
├── requirements.txt
├── launcher.py             # Control principal (servidor + config BD)
├── run.py                  # Arranque CLI del servidor
├── app/                    # FastAPI + web + servicios
│   ├── core/
│   ├── db/
│   ├── services/           # dashboard, export, insights, día…
│   ├── api/
│   └── web/
├── tests/
├── db/schema/              # SQL (000 completo, migraciones)
├── templates_excel/
└── desktop_legacy/         # GUI PySide6 de referencia
```

---

## Requisitos

- Python 3.10+
- MariaDB con la base `fajos_central`
- Dependencias: `pip install -r requirements.txt`

---

## Arranque rápido (Windows / PowerShell 7)

1. Configura la BD en el **launcher** (usuario, contraseña, host, puerto).
2. Ejecuta el esquema si es necesario: `db/schema/000_fajos_central_completo.sql` en HeidiSQL.
3. Desde la carpeta del proyecto:

```powershell
python .\launcher.py
```

O solo el servidor:

```powershell
python .\run.py
```

Abre la URL que muestra el launcher (IP local + puerto).

---


---

## Portable y acceso directo (Windows)

### En tu PC

```powershell
pwsh -ExecutionPolicy Bypass -File .\setup_windows.ps1
pwsh -File .\scripts\create_desktop_shortcut.ps1
pwsh -File .\scriptserify_env.ps1
```

En el **launcher**: Utilidades → **Acceso directo** y **Verificar**.

### Carpeta portable (copiar a otra PC)

```powershell
pwsh -File .\scripts\make_portable.ps1
```


## Uso diario

1. **Inicio** — revisa el panel *Qué revisar hoy*.
2. **Plata** — captura gramos (＋ Un día / celdas). Al exportar formal verás un checklist.
3. **Pita / Taller** — líneas de efectivo y sueldos; edición con doble clic.
4. Exporta **Formal** por área; el **resumen de 3 nóminas** está en Taller.
5. **Master Excel** — respaldo completo de la base desde Inicio.

---

## API de insights (v3.7)

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/insights/hoy` | Avisos del día |
| `GET /api/insights/sugerir-trabajo?trabajador_id=` | Último folio/modelo/material |
| `GET /api/insights/rarezas/{semana_id}` | Desvíos ±30 % vs historial |
| `GET /api/insights/checklist/{semana_id}` | Checklist pre-export |

---

## Licencia / uso

Uso interno del Taller de Fajos Central.
