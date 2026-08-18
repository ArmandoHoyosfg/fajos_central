-- ============================================================
-- 002 — Suministro diario + índices de apoyo a importación
-- Ejecutar sobre fajos_central (HeidiSQL / MariaDB)
-- ============================================================
USE fajos_central;

-- Cabecera de suministro diario (equivalente a la hoja de papel del día)
CREATE TABLE IF NOT EXISTS suministro_diario (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha             DATE         NOT NULL,
  material          VARCHAR(20)  NOT NULL DEFAULT 'AG3',
  notas             VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_fecha_material (fecha, material)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Cabecera del suministro diario (papel del día)';

-- Detalle del suministro (una fila por bordador/folio del día)
CREATE TABLE IF NOT EXISTS suministro_detalle (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  suministro_id     INT UNSIGNED NOT NULL,
  trabajador_id     INT UNSIGNED DEFAULT NULL,
  nombre            VARCHAR(80)  NOT NULL,
  ubic              INT UNSIGNED NOT NULL,
  folio             VARCHAR(30)  DEFAULT NULL,
  modelo            VARCHAR(60)  DEFAULT NULL,
  -- lecturas parciales del día (como en el papel AG3)
  lectura_1         DECIMAL(8,2) DEFAULT NULL,
  lectura_2         DECIMAL(8,2) DEFAULT NULL,
  lectura_3         DECIMAL(8,2) DEFAULT NULL,
  lectura_4         DECIMAL(8,2) DEFAULT NULL,
  total_gramos      DECIMAL(10,2) GENERATED ALWAYS AS (
                      COALESCE(lectura_1,0)+COALESCE(lectura_2,0)+COALESCE(lectura_3,0)+COALESCE(lectura_4,0)
                    ) STORED,
  observaciones     VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_suministro (suministro_id),
  KEY idx_nombre_ubic (nombre, ubic),
  CONSTRAINT fk_sum_det_cab FOREIGN KEY (suministro_id)
    REFERENCES suministro_diario(id) ON DELETE CASCADE,
  CONSTRAINT fk_sum_det_trab FOREIGN KEY (trabajador_id)
    REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Detalle diario de suministro (gramos del día)';

-- Log de importaciones (trazabilidad / seguridad)
CREATE TABLE IF NOT EXISTS import_log (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  archivo           VARCHAR(255) NOT NULL,
  modo              VARCHAR(20)  NOT NULL COMMENT 'dry_run | apply',
  resumen_json      TEXT,
  ok                TINYINT(1)   NOT NULL DEFAULT 1,
  mensaje           VARCHAR(500) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Historial de importaciones Excel';

SELECT 'Migración 002 aplicada (suministro + import_log)' AS mensaje;
