-- Historial de cambios de producción (idempotente)
CREATE TABLE IF NOT EXISTS historial_produccion (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  produccion_id INT NOT NULL,
  semana_id INT NOT NULL,
  campo VARCHAR(32) NOT NULL,
  valor_anterior VARCHAR(64) NULL,
  valor_nuevo VARCHAR(64) NULL,
  origen VARCHAR(32) DEFAULT 'app',
  usuario VARCHAR(64) NULL,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_hist_semana (semana_id, creado_en),
  INDEX idx_hist_prod (produccion_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
