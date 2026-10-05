# Esquema Fajos Central

## Relación

trabajadores 1—N trabajos (folio/modelo/material)
trabajadores 1—N produccion_plata (siempre con trabajador_id)
trabajos 1—N produccion_plata (trabajo_id)

## Reinstalación

`db/schema/000_fajos_central_completo.sql` en HeidiSQL (borra y recrea con Excel V3).
