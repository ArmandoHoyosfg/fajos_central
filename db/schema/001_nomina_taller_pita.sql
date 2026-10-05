-- ============================================================
-- Migración 001: Nóminas Taller (TLL) y Pita (PIT)
-- Trabajadores unificados; vistas por área.
-- HeidiSQL: ejecutar sobre fajos_central (F9)
-- ============================================================
USE fajos_central;
SET NAMES utf8mb4;

-- Nómina TALLER: sueldo semanal + extras (sin material)
CREATE TABLE IF NOT EXISTS nomina_taller (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id INT UNSIGNED NOT NULL,
  trabajador_id INT UNSIGNED DEFAULT NULL,
  nombre VARCHAR(80) NOT NULL,
  ubic INT UNSIGNED NOT NULL,
  puesto VARCHAR(60) DEFAULT NULL,
  sueldo DECIMAL(12,2) NOT NULL DEFAULT 0,
  extras DECIMAL(12,2) NOT NULL DEFAULT 0,
  total DECIMAL(12,2) GENERATED ALWAYS AS (COALESCE(sueldo,0)+COALESCE(extras,0)) STORED,
  firmado TINYINT(1) NOT NULL DEFAULT 0,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_semana (semana_id),
  KEY idx_trab (trabajador_id),
  KEY idx_ubic (ubic),
  CONSTRAINT fk_tll_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_tll_trab FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Producción PITA: modelo distinto, material tipo "PITA 6X6", producto, pitas, efectivo
CREATE TABLE IF NOT EXISTS produccion_pita (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id INT UNSIGNED NOT NULL,
  trabajador_id INT UNSIGNED DEFAULT NULL,
  nombre VARCHAR(80) NOT NULL,
  ubic INT UNSIGNED NOT NULL,
  modelo VARCHAR(80) DEFAULT NULL,
  folio VARCHAR(40) DEFAULT NULL,
  material VARCHAR(40) DEFAULT NULL COMMENT 'ej. PITA 6X6',
  producto VARCHAR(60) DEFAULT 'Cinturón',
  pitas DECIMAL(12,2) DEFAULT NULL COMMENT 'suele ir vacío',
  efectivo DECIMAL(12,2) NOT NULL DEFAULT 0,
  firmado TINYINT(1) NOT NULL DEFAULT 0,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_semana (semana_id),
  KEY idx_trab (trabajador_id),
  KEY idx_ubic (ubic),
  CONSTRAINT fk_pit_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_pit_trab FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Vistas por área (mismos trabajadores, filtro tipo)
CREATE OR REPLACE VIEW v_trabajadores_plt AS
  SELECT * FROM trabajadores
  WHERE activo = 1 AND (tipo LIKE '%PLT%' OR tipo = 'Mixto' OR tipo = 'MIXTO');

CREATE OR REPLACE VIEW v_trabajadores_pit AS
  SELECT * FROM trabajadores
  WHERE activo = 1 AND (tipo LIKE '%PIT%' OR tipo = 'Mixto' OR tipo = 'MIXTO');

CREATE OR REPLACE VIEW v_trabajadores_tll AS
  SELECT * FROM trabajadores
  WHERE activo = 1 AND (tipo LIKE '%TLL%' OR tipo = 'Mixto' OR tipo = 'MIXTO');

CREATE OR REPLACE VIEW v_trabajadores_por_area AS
  SELECT id, nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion,
    CASE
      WHEN tipo LIKE '%TLL%' THEN 'TLL'
      WHEN tipo LIKE '%PIT%' AND tipo NOT LIKE '%PLT%' THEN 'PIT'
      WHEN tipo LIKE '%PLT%' THEN 'PLT'
      ELSE 'OTRO'
    END AS area
  FROM trabajadores;

-- Totales por semana (unión resumen + detalle)
CREATE OR REPLACE VIEW v_totales_semana AS
SELECT
  s.id AS semana_id,
  s.codigo,
  s.fecha_inicio,
  s.fecha_fin,
  COALESCE(r.nomina_plt, (SELECT COALESCE(SUM(efectivo),0) FROM produccion_plata p WHERE p.semana_id = s.id), 0) AS nomina_plata,
  COALESCE(r.nomina_pit, (SELECT COALESCE(SUM(efectivo),0) FROM produccion_pita p WHERE p.semana_id = s.id), 0) AS nomina_pita,
  COALESCE(r.nomina_tll, (SELECT COALESCE(SUM(total),0) FROM nomina_taller t WHERE t.semana_id = s.id), 0) AS nomina_taller,
  (
    COALESCE(r.nomina_plt, (SELECT COALESCE(SUM(efectivo),0) FROM produccion_plata p WHERE p.semana_id = s.id), 0)
  + COALESCE(r.nomina_pit, (SELECT COALESCE(SUM(efectivo),0) FROM produccion_pita p WHERE p.semana_id = s.id), 0)
  + COALESCE(r.nomina_tll, (SELECT COALESCE(SUM(total),0) FROM nomina_taller t WHERE t.semana_id = s.id), 0)
  ) AS total_nomina
FROM semanas s
LEFT JOIN resumen_nominas r ON r.semana_id = s.id;

SELECT 'OK — tablas nomina_taller + produccion_pita + vistas por área' AS resultado;
