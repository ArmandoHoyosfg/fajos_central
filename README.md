# Fajos Central — Sistema de Nóminas

**Versión:** 2.1.0  

Sistema de nóminas del **Taller de Fajos Central**.

- Interfaz web accesible en la red local
- API REST
- Dashboard con KPIs
- Exportación a Excel, CSV, PDF y JSON
- Base de datos MariaDB
- Tests con pytest
- Errores estructurados (humanos + IA)

---

## Estructura del proyecto

```
fajos_central/
├── VERSION                 # Versión actual (semver)
├── CHANGELOG.md
├── README.md
├── requirements.txt
├── pytest.ini
├── launcher.py             # Launcher GUI (iniciar/detener servidor)
├── run.py                  # Arranque del servidor web (CLI)
├── .env.example
├── app/                    # Aplicación principal (FastAPI + web)
│   ├── core/               # Config, excepciones, logging
│   ├── db/                 # Conexión y repositorios
│   ├── services/           # Dashboard, export multi-formato
│   ├── api/                # Rutas REST y páginas
│   └── web/templates/      # HTML
├── tests/                  # Pytest
├── db/schema/              # Scripts SQL versionados
├── templates_excel/        # Excel optimizado de referencia
├── scripts/                # Utilidades CLI
└── desktop_legacy/         # GUI PySide6 (referencia / legado)
```

---

## Requisitos

- Python 3.10+
- MariaDB con la base `fajos_central`

## Instalación

```bash
cd fajos_central
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env con usuario y contraseña de MariaDB
```

### Base de datos

En HeidiSQL (o cliente SQL), ejecuta:

```
db/schema/001_schema_inicial.sql
```

(sobre la base `fajos_central` ya creada).

## Ejecutar

```bash
python run.py
```

| URL | Descripción |
|-----|-------------|
| http://localhost:8000 | Dashboard |
| http://localhost:8000/trabajadores | Catálogo |
| http://localhost:8000/produccion | Producción / nómina |
| http://localhost:8000/docs | API interactiva |
| http://IP_LAN:8000 | Acceso desde otros equipos de la red |

## Exportar nómina

```
GET /api/export/produccion/{semana_id}?fmt=xlsx
GET /api/export/produccion/{semana_id}?fmt=csv
GET /api/export/produccion/{semana_id}?fmt=pdf
GET /api/export/produccion/{semana_id}?fmt=json
```

## Tests

```bash
pytest
pytest --cov=app
```

## Versionado

- Formato: **SemVer** (`MAJOR.MINOR.PATCH`) en el archivo `VERSION`
- Historial de cambios: `CHANGELOG.md`
- Repositorio Git inicializado en esta carpeta

| Versión | Notas |
|---------|--------|
| 2.0.0 | Web FastAPI, dashboard, multi-export, tests, consolidación del proyecto |
| 1.x | Excel optimizado + scripts CLI + GUI PySide6 (en `desktop_legacy/`) |

## Errores estructurados

```json
{
  "error": true,
  "code": "NOT_FOUND",
  "message": "Trabajador id=99 no existe.",
  "user_message": "No se encontró el recurso solicitado.",
  "http_status": 404,
  "details": { "trabajador_id": 99 }
}
```

Códigos: `NOT_FOUND`, `VALIDATION_ERROR`, `DATABASE_ERROR`, `EXPORT_ERROR`, `CONFLICT`, `INTERNAL_ERROR`.
