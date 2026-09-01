# Integridad y paridad (v3.16.x)

## Verificación estática (2026-08-23)

- Compilación / AST de `app/`, `launcher.py`, `desktop_legacy/`: sin errores de sintaxis.
- Plantillas web ↔ archivos en `static/`: sin referencias rotas detectadas.
- `etiqueta_semana` presente en desktop calendar_util.

## HTTPS y móvil (pendiente — no implementar aún)

- Objetivo futuro: HTTPS en LAN (certs autofirmados: `scripts/generate_ssl_certs.py`) para que el móvil no bloquee contenido “inseguro” en algunos contextos.
- **No** se quiere el sitio completo en el teléfono: solo funciones acotadas (estado del día, cargar gramos, avisos).
- Hoy el acceso móvil puede hacerse por HTTP a `http://IP:8000` si la red lo permite; HTTPS mejorará confianza del navegador.

## Paridad escritorio (PySide6) vs web

| Función | Escritorio | Web |
|---------|------------|-----|
| Solo hoy / gramos día | Sí | Sí |
| Plata captura | Sí | Sí (+ rarezas, undo, Enter) |
| Pita / Taller | Parcial | Completo |
| Trabajadores / Folios | Sí | Sí |
| Cerrar/reabrir semana | Sí (Plata) | Sí (todas) |
| Gestión Semanas (alinear/editar/borrar) | No | Sí `/semanas` |
| Captura manual Excel | Limitado | Sí |
| Insights / checklist formal | Parcial | Completo |
| Backup al cerrar | Launcher | — |
| Red local multi-equipo | Vía web | Sí |

**Criterio:** la web + launcher son la referencia. El escritorio es atajo de captura en el PC del taller.

## Launcher (estado del servidor)

Desde 3.16.3: estado verde solo si el puerto responde; libera puerto al iniciar; sin `--reload`; abre `127.0.0.1`.

## Cómo validar en tu PC

1. `setup_windows.cmd` o Bypass + setup
2. Launcher → Probar BD → Iniciar → debe ponerse verde y abrir el navegador
3. Escritorio: Ayuda → paridad / Abrir web
