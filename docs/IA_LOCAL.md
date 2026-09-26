# Cómo trabajar este repo con una IA local (Bionic Studio, etc.)

Los modelos locales tienen **contexto corto** y son **lentos**. Este proyecto está partido a propósito.

## Qué abrir en el chat

| Tarea | Adjunta solo |
|-------|----------------|
| Bug en Plata / gramos | `app/api/routers/produccion.py` + `app/db/repos/produccion.py` |
| Trabajadores / sueldo fijo | `routers/trabajadores.py` + `repos/trabajadores.py` |
| Export Excel | el método concreto en `export_service.py` (busca `def _xlsx_` / `def export_`) |
| Íconos / UI | `templates/base.html` + `static/app.css` |
| Migración BD | un solo `db/schema/00N_*.sql` |

Siempre puedes adjuntar también `AGENTS.md` (corto).

## Prompt tipo (cópialo)

```
Lee AGENTS.md. Necesito un cambio MÍNIMO en el archivo [X].
No reescribas el archivo completo.
No toques otros dominios.
Al final lista: archivo tocado, función, riesgo.
```

## Qué no pedir a la IA local en un solo paso

- "Refactoriza todo el backend"
- "Reescribe export_service"
- "Sincroniza toda la app con el Excel"

Divide en 2–4 pasos y verifica en la UI entre medias.

## Offline

Íconos Lucide van en `app/web/static/vendor/lucide.min.js` (sin internet).
Si no se ven: confirma que ese archivo existe y que `base.html` apunta a `/static/vendor/lucide.min.js`.
