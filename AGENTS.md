# Guía para agentes de IA (local o remota)

> Objetivo: que un modelo **local** (p. ej. Bionic Studio) pueda modificar este proyecto
> sin cargar el monolito completo. Trabaja **por archivo pequeño** y **un cambio a la vez**.

## Reglas de oro (léelas siempre)

1. **No reescribas un archivo completo** si solo hay que tocar una función.
2. **Un dominio = un archivo**. Busca primero en la tabla de abajo.
3. **No toques** `app/api/routes_monolith.py.bak` ni `app/db/repository_monolith.py.bak` (solo respaldo).
4. **Imports públicos estables**:
   - `from app.api.routes import router`
   - `from app.db.repository import ProduccionRepo, TrabajadoresRepo, ...`
5. Tras cambiar Python: verifica sintaxis mentalmente; no inventes columnas SQL.
6. **Offline**: no uses CDN. Íconos en `/static/vendor/lucide.min.js` y `/static/icons/`.
7. Encoding: UTF-8. En Windows los `.bat` ya fuerzan `PYTHONUTF8=1`.

## Mapa rápido (dónde editar)

| Quiero cambiar… | Archivo |
|-----------------|--------|
| Ruta HTTP / página web | `app/api/routers/<dominio>.py` |
| Helpers de plantillas | `app/api/helpers.py` |
| Consultas SQL / datos | `app/db/repos/<dominio>.py` |
| Export Excel/PDF | `app/services/export_service.py` + `app/services/export/` (helpers, captura, suministro; resto aún en fachada) |
| Cierre de día | `app/services/dia_service.py` + `db/schema/006_cierre_dia.sql` |
| Migración SQL nueva | `db/schema/00N_nombre.sql` (siguiente número libre) |
| Plantilla HTML | `app/web/templates/*.html` |
| CSS / JS | `app/web/static/` |
| Filtro Jinja tojson | `app/web/jinja_ext.py` |
| Launcher Windows | `launcher.py` |
| Versión visible | `VERSION` y `app/__init__.py` |

### Routers (`app/api/routers/`)

| Archivo | Dominio |
|---------|---------|
| `pages.py` | Dashboard, buscar, suministro, health |
| `trabajadores.py` | Alta/baja/QR/sync |
| `produccion.py` | Plata, gramos, días, folios |
| `semanas.py` | Semanas e historial |
| `nominas.py` | Taller y Pita |
| `export.py` | Descargas Excel |
| `dev.py` | Herramientas Dev |
| `insights.py` | Insights / ops |
| `catalogos.py` | Materiales y modelos |

### Repos (`app/db/repos/`)

| Archivo | Clase |
|---------|--------|
| `trabajadores.py` | `TrabajadoresRepo` |
| `produccion.py` | `ProduccionRepo` |
| `trabajos.py` | `TrabajosRepo` |
| `semanas.py` | `SemanasRepo` |
| `nomina_taller.py` | `NominaTallerRepo` |
| `produccion_pita.py` | `ProduccionPitaRepo` |
| `catalogos.py` | `CatalogosRepo` |
| `historial_precios.py` | `HistorialPreciosRepo` |
| `dashboard.py` / `resumen.py` | Totales y dashboard |

## Flujo de trabajo recomendado (modelo local lento)

1. Leer **solo** `AGENTS.md` + el archivo del dominio (≤ 400–900 líneas).
2. Localizar la función con búsqueda de nombre (`def listar_`, `def duplicar_`).
3. Editar **una función**.
4. Anotar en `CHANGELOG.md` una línea bajo la versión actual.
5. No regenerar ZIP ni tocar otros dominios en el mismo paso.

## Checklist antes de terminar un cambio

- [ ] ¿El import público sigue funcionando? (`repository` / `routes` reexportan)
- [ ] ¿No añadí CDN externos?
- [ ] ¿SQL compatible con MariaDB (no PostgreSQL)?
- [ ] ¿Mensajes de error en español claro para el usuario?

## Contexto de negocio (mínimo)

- **Plata**: gramos por día × $/gr → efectivo. Folios se pueden **terminar** y no deben duplicarse a la semana siguiente.
- **Pita**: cinturones / pitas; export limpia sin ceros vacíos.
- **Taller**: sueldo fijo o variable; torcedores = pitas × $3.20.
- Semana de captura: sábado–viernes; **pago el sábado** siguiente. Cierre/impresión: viernes.

## Archivos que NO debes inflar

- `app/__init__.py` — solo `__version__`
- `launcher.py` — solo si el cambio es del launcher


## Duplicados de trabajadores
Solo misma **ubic** + nombre igual/parecido. Distinta ubic = personas distintas.

## DEV BD segura
- SELECT: `app/services/dev_db_service.py` allowlist.
- No añadir UPDATE/DELETE libres; solo REPAIRS en código.

## Tests
- `tests/test_aprendizaje_rules.py` — reglas de nombres/ubic sin BD.
- Preferir pytest: `python -m pytest tests/ -q`
