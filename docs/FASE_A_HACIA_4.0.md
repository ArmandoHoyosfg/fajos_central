# Fase A → hacia 4.0

## Incluido en 3.19.0

1. **Migraciones al arranque** (`app/db/migrate.py`)
   - Tabla `schema_migrations`
   - Aplica `db/schema/001_*.sql` … automáticamente al iniciar el servidor
   - `000_*.sql` no se re-aplica (bootstrap)

2. **Tests**
   - `tests/test_export_zeros.py` — regla “en 0 no exporta”
   - `tests/test_migrate.py` — parser de scripts
   - `tests/test_consistency_rules.py` — umbral de desfase
   - Ejecutar: `pytest -q`

3. **Backup** (ya en launcher)
   - Opción “Backup al cerrar” + “Backup ahora”
   - Master Excel + config

4. **Sin consola en uso diario**
   - `start.bat` → `pythonw` + `start_silent.vbs` (sin ventana negra)
   - `start_dev.bat` → consola visible (diagnóstico)

5. **Íconos** en `app/web/static/icons/`
   - dashboard, workers, plata, pita, taller, repair, server, dev, backup, check…

6. **Panel Dev ampliado** (`/dev`)
   - Reparación inteligente (pipeline completo)
   - Solo migraciones
   - Comandos: sync, huérfanos, semana actual, API, docs, master Excel

## Pendiente para 4.0.0 final

- Empaquetado portable Windows (carpeta única + acceso directo con logo.ico)
- Suite de tests con BD de prueba
- Móvil mínimo + HTTPS documentado
- Wizard de primer uso
