
-- Historial de precios por combinación material + modelo
CREATE TABLE IF NOT EXISTS historial_precios (
  id INT AUTO_INCREMENT PRIMARY KEY,
  material VARCHAR(64) NOT NULL,
  modelo VARCHAR(128) NULL,
  tarifa_gr DECIMAL(10,2) NOT NULL,
  fuente VARCHAR(32) DEFAULT 'captura',
  semana_id INT NULL,
  prod_id INT NULL,
  creado_en TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_hp_mat (material),
  INDEX idx_hp_mat_mod (material, modelo),
  INDEX idx_hp_creado (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
