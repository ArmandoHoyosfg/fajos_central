-- ============================================================
-- 004 — Cierre de semana, historial de producción, suministro
-- Ejecutar en HeidiSQL sobre fajos_central
-- Si una columna ya existe, ignora el error de ese ALTER y sigue.
-- ============================================================
USE fajos_central;

-- Cierre de semana (ejecutar uno a uno si ALTER falla por duplicado)
ALTER TABLE semanas ADD COLUMN cerrada TINYINT(1) NOT NULL DEFAULT 0
  COMMENT '1 = bloqueada para edición' AFTER notas;
ALTER TABLE semanas ADD COLUMN cerrada_en TIMESTAMP NULL DEFAULT NULL AFTER cerrada;
ALTER TABLE semanas ADD COLUMN cerrada_por VARCHAR(80) NULL DEFAULT NULL AFTER cerrada_en;

CREATE TABLE IF NOT EXISTS historial_produccion (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,
  produccion_id   INT UNSIGNED NOT NULL,
  semana_id       INT UNSIGNED NOT NULL,
  campo           VARCHAR(32)  NOT NULL COMMENT 'gm_sab, tarifa_gr, folio, etc.',
  valor_anterior  VARCHAR(80)  DEFAULT NULL,
  valor_nuevo     VARCHAR(80)  DEFAULT NULL,
  origen          VARCHAR(40)  NOT NULL DEFAULT 'app',
  usuario         VARCHAR(80)  DEFAULT NULL,
  creado_en       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_prod (produccion_id),
  KEY idx_semana (semana_id),
  KEY idx_creado (creado_en)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS suministro_diario (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha DATE NOT NULL,
  trabajador_id INT UNSIGNED DEFAULT NULL,
  nombre VARCHAR(80) NOT NULL,
  ubic INT UNSIGNED NOT NULL,
  folio VARCHAR(40) DEFAULT NULL,
  modelo VARCHAR(60) DEFAULT NULL,
  material VARCHAR(20) DEFAULT NULL,
  gramos DECIMAL(8,2) DEFAULT NULL,
  notas VARCHAR(255) DEFAULT NULL,
  produccion_id INT UNSIGNED DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_fecha (fecha),
  KEY idx_nombre_ubic (nombre, ubic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

SELECT 'OK 004 — cierre, historial, suministro' AS resultado;
