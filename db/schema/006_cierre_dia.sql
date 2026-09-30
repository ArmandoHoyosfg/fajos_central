-- 006_cierre_dia.sql
-- Tabla de cierre de día (antes se creaba en runtime desde dia_service).
-- Idempotente: CREATE TABLE IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS cierre_dia (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha DATE NOT NULL,
  semana_id INT UNSIGNED DEFAULT NULL,
  campo_dia VARCHAR(16) NOT NULL COMMENT 'gm_sab, gm_dom, ... gm_vie',
  cerrado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  cerrado_por VARCHAR(64) DEFAULT NULL,
  resumen_json TEXT DEFAULT NULL COMMENT 'totales / quién falta al cerrar',
  notas VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_cierre_fecha (fecha),
  KEY idx_cierre_semana (semana_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
