-- Cierre de día (ejecutar si la tabla no existe)
USE fajos_central;

CREATE TABLE IF NOT EXISTS cierre_dia (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha DATE NOT NULL,
  semana_id INT UNSIGNED DEFAULT NULL,
  campo_dia VARCHAR(16) NOT NULL COMMENT 'gm_sab…gm_vie',
  trabajos_total INT NOT NULL DEFAULT 0,
  trabajos_sin_gramos INT NOT NULL DEFAULT 0,
  total_gramos DECIMAL(12,2) DEFAULT 0,
  total_efectivo DECIMAL(12,2) DEFAULT 0,
  resumen_json MEDIUMTEXT,
  cerrado_por VARCHAR(80) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
