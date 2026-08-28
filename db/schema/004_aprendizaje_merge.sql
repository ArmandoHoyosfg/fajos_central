-- v3.18: aprendizaje ligero + soporte fusión trabajadores
-- Ejecutar en HeidiSQL sobre fajos_central

CREATE TABLE IF NOT EXISTS aprendizaje_eventos (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  tipo VARCHAR(40) NOT NULL COMMENT 'folio_inactivo|folio_reasignado|merge|error_app|captura|cierre',
  entidad VARCHAR(40) DEFAULT NULL COMMENT 'trabajador|folio|semana|app',
  entidad_id INT UNSIGNED DEFAULT NULL,
  semana_id INT UNSIGNED DEFAULT NULL,
  payload_json TEXT DEFAULT NULL,
  peso DECIMAL(6,2) NOT NULL DEFAULT 1.00,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tipo (tipo),
  KEY idx_entidad (entidad, entidad_id),
  KEY idx_semana (semana_id),
  KEY idx_creado (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS aprendizaje_stats (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  clave VARCHAR(80) NOT NULL COMMENT 'ej. avg_g_trabajador_12, folio_ST-222_ultimo',
  valor_num DECIMAL(14,4) DEFAULT NULL,
  valor_txt VARCHAR(255) DEFAULT NULL,
  muestras INT UNSIGNED NOT NULL DEFAULT 1,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_clave (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Opcional: marca de folio terminado en produccion si no existe en trabajos
-- (trabajos.terminado_en ya existe en 003)
