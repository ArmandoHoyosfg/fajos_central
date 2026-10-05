-- ============================================================
-- FAJOS CENTRAL — ESQUEMA + DATOS (reinstalación completa)
-- Fuente: NOMINA_FAJOS_OPTIMIZADA_2026_V3.xlsx
-- Modelo: trabajadores → trabajos (folio/modelo/material) → produccion_plata
-- HeidiSQL: base fajos_central → cargar → F9
-- ============================================================

CREATE DATABASE IF NOT EXISTS fajos_central
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE fajos_central;
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP VIEW IF EXISTS v_trabajadores_plt_activos;
DROP VIEW IF EXISTS v_trabajadores_plt;
DROP VIEW IF EXISTS v_trabajadores_pit;
DROP VIEW IF EXISTS v_trabajadores_tll;
DROP VIEW IF EXISTS v_trabajadores_por_area;
DROP VIEW IF EXISTS v_totales_semana;
DROP VIEW IF EXISTS v_produccion_semana;
DROP VIEW IF EXISTS v_trabajos_activos;
DROP TABLE IF EXISTS historial_produccion;
DROP TABLE IF EXISTS import_log;
DROP TABLE IF EXISTS cierre_dia;
DROP TABLE IF EXISTS suministro_diario;
DROP TABLE IF EXISTS produccion_pita;
DROP TABLE IF EXISTS nomina_taller;
DROP TABLE IF EXISTS produccion_plata;
DROP TABLE IF EXISTS trabajos;
DROP TABLE IF EXISTS resumen_nominas;
DROP TABLE IF EXISTS semanas;
DROP TABLE IF EXISTS trabajadores;
DROP TABLE IF EXISTS modelos;
DROP TABLE IF EXISTS tarifas_material;

-- ---------- CATALOGOS ----------
CREATE TABLE trabajadores (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre_mostrar VARCHAR(80) NOT NULL,
  nombre_completo VARCHAR(120) DEFAULT NULL,
  ubic INT UNSIGNED NOT NULL,
  tipo VARCHAR(20) NOT NULL DEFAULT 'PLT',
  puesto VARCHAR(60) DEFAULT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  fecha_incorporacion DATE DEFAULT NULL,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_nombre_ubic (nombre_mostrar, ubic),
  KEY idx_tipo (tipo),
  KEY idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE modelos (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  modelo VARCHAR(60) NOT NULL,
  tipo VARCHAR(10) NOT NULL DEFAULT 'PLT',
  material_default VARCHAR(20) DEFAULT NULL,
  tarifa_default DECIMAL(8,2) DEFAULT NULL,
  notas VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_modelo_tipo (modelo, tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tarifas_material (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  material VARCHAR(20) NOT NULL,
  tarifa_por_gramo DECIMAL(8,2) NOT NULL,
  descripcion VARCHAR(80) DEFAULT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uk_material (material)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE semanas (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(20) NOT NULL,
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  anio SMALLINT NOT NULL DEFAULT 2026,
  notas VARCHAR(255) DEFAULT NULL,
  cerrada TINYINT(1) NOT NULL DEFAULT 0,
  cerrada_en TIMESTAMP NULL DEFAULT NULL,
  cerrada_por VARCHAR(80) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_codigo_anio (codigo, anio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Trabajo en progreso: folio + modelo + material ligado a un trabajador
CREATE TABLE trabajos (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  trabajador_id INT UNSIGNED NOT NULL,
  folio VARCHAR(40) DEFAULT NULL,
  modelo VARCHAR(60) DEFAULT NULL,
  material VARCHAR(20) DEFAULT NULL,
  tarifa_gr DECIMAL(8,2) DEFAULT NULL,
  activo TINYINT(1) NOT NULL DEFAULT 1 COMMENT '1=en progreso',
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_trabajador (trabajador_id),
  KEY idx_folio (folio),
  KEY idx_activo (activo),
  CONSTRAINT fk_trabajo_trab FOREIGN KEY (trabajador_id)
    REFERENCES trabajadores(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Asignaciones folio/modelo/material por trabajador (trabajos en progreso)';

CREATE TABLE produccion_plata (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id INT UNSIGNED NOT NULL,
  trabajador_id INT UNSIGNED NOT NULL COMMENT 'Siempre ligado al catálogo',
  trabajo_id INT UNSIGNED DEFAULT NULL COMMENT 'Liga al trabajo (folio/modelo)',
  nombre VARCHAR(80) NOT NULL COMMENT 'Copia denormalizada para reportes',
  ubic INT UNSIGNED NOT NULL,
  folio VARCHAR(40) DEFAULT NULL,
  modelo VARCHAR(60) DEFAULT NULL,
  material VARCHAR(20) DEFAULT NULL,
  tarifa_gr DECIMAL(8,2) DEFAULT NULL,
  gm_sab DECIMAL(8,2) DEFAULT NULL,
  gm_dom DECIMAL(8,2) DEFAULT NULL,
  gm_lun DECIMAL(8,2) DEFAULT NULL,
  gm_mar DECIMAL(8,2) DEFAULT NULL,
  gm_mie DECIMAL(8,2) DEFAULT NULL,
  gm_jue DECIMAL(8,2) DEFAULT NULL,
  gm_vie DECIMAL(8,2) DEFAULT NULL,
  total_gramos DECIMAL(10,2) GENERATED ALWAYS AS (
    COALESCE(gm_sab,0)+COALESCE(gm_dom,0)+COALESCE(gm_lun,0)+
    COALESCE(gm_mar,0)+COALESCE(gm_mie,0)+COALESCE(gm_jue,0)+COALESCE(gm_vie,0)
  ) STORED,
  efectivo DECIMAL(12,2) GENERATED ALWAYS AS (
    ROUND((COALESCE(gm_sab,0)+COALESCE(gm_dom,0)+COALESCE(gm_lun,0)+
           COALESCE(gm_mar,0)+COALESCE(gm_mie,0)+COALESCE(gm_jue,0)+COALESCE(gm_vie,0))
          * COALESCE(tarifa_gr,0), 2)
  ) STORED,
  firmado TINYINT(1) NOT NULL DEFAULT 0,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_semana (semana_id),
  KEY idx_trabajador (trabajador_id),
  KEY idx_trabajo (trabajo_id),
  KEY idx_nombre_ubic (nombre, ubic),
  CONSTRAINT fk_prod_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_prod_trab FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE RESTRICT,
  CONSTRAINT fk_prod_trabajo FOREIGN KEY (trabajo_id) REFERENCES trabajos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE nomina_taller (
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
  CONSTRAINT fk_tll_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_tll_trab FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE produccion_pita (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id INT UNSIGNED NOT NULL,
  trabajador_id INT UNSIGNED DEFAULT NULL,
  nombre VARCHAR(80) NOT NULL,
  ubic INT UNSIGNED NOT NULL,
  modelo VARCHAR(80) DEFAULT NULL,
  folio VARCHAR(40) DEFAULT NULL,
  material VARCHAR(40) DEFAULT NULL,
  producto VARCHAR(60) DEFAULT 'Cinturón',
  pitas DECIMAL(12,2) DEFAULT NULL,
  efectivo DECIMAL(12,2) NOT NULL DEFAULT 0,
  firmado TINYINT(1) NOT NULL DEFAULT 0,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_semana (semana_id),
  KEY idx_trab (trabajador_id),
  CONSTRAINT fk_pit_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_pit_trab FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE resumen_nominas (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id INT UNSIGNED NOT NULL,
  nomina_plt DECIMAL(12,2) DEFAULT 0,
  nomina_pit DECIMAL(12,2) DEFAULT 0,
  nomina_tll DECIMAL(12,2) DEFAULT 0,
  total_semana DECIMAL(12,2) GENERATED ALWAYS AS (
    COALESCE(nomina_plt,0)+COALESCE(nomina_pit,0)+COALESCE(nomina_tll,0)
  ) STORED,
  notas VARCHAR(255) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_semana (semana_id),
  CONSTRAINT fk_resumen_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE historial_produccion (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  produccion_id INT UNSIGNED NOT NULL,
  semana_id INT UNSIGNED NOT NULL,
  campo VARCHAR(32) NOT NULL,
  valor_anterior VARCHAR(80) DEFAULT NULL,
  valor_nuevo VARCHAR(80) DEFAULT NULL,
  origen VARCHAR(40) NOT NULL DEFAULT 'app',
  usuario VARCHAR(80) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_prod (produccion_id),
  KEY idx_semana (semana_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


CREATE TABLE cierre_dia (
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

CREATE TABLE suministro_diario (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  fecha DATE NOT NULL,
  trabajador_id INT UNSIGNED DEFAULT NULL,
  trabajo_id INT UNSIGNED DEFAULT NULL,
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
  KEY idx_fecha (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE import_log (
  id INT UNSIGNED NOT NULL AUTO_INCREMENT,
  archivo VARCHAR(255) NOT NULL,
  modo VARCHAR(20) NOT NULL,
  resumen_json MEDIUMTEXT,
  ok TINYINT(1) NOT NULL DEFAULT 1,
  mensaje VARCHAR(500) DEFAULT NULL,
  creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE OR REPLACE VIEW v_trabajos_activos AS
SELECT t.id AS trabajo_id, t.folio, t.modelo, t.material, t.tarifa_gr, t.activo,
       tr.id AS trabajador_id, tr.nombre_mostrar, tr.ubic, tr.tipo
FROM trabajos t
JOIN trabajadores tr ON tr.id = t.trabajador_id
WHERE t.activo = 1 AND tr.activo = 1;

CREATE OR REPLACE VIEW v_trabajadores_plt_activos AS
SELECT * FROM trabajadores
WHERE activo = 1 AND (tipo LIKE '%PLT%' OR tipo = 'Mixto');

SET FOREIGN_KEY_CHECKS = 1;

-- ========== DATOS DESDE EXCEL V3 ==========

INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion) VALUES ('AG3', 12.0, 'Plata AG3 estándar');
INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion) VALUES ('AG4', 13.0, 'Plata AG4');
INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion) VALUES ('DOL', 13.0, 'Dorado / Metal dorado');
INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion) VALUES ('DLO', 13.0, 'Dorado (variante)');

INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('SECUENCIA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CUBOS', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CINCO CORDONES', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CENTELLA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CENTELLAS', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('ROMBOS', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('SANTA MARÍA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('PAVO', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('PETATILLO', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CHINELA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CHINELA GUÍA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('COPA CABANA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('GUÍA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('AROS', 'PLT', 'AG3', 13.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('QUIMERA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('MIL HOJAS', 'PLT', 'AG3', 15.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('TOQUILLA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('REPARACIÓN', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('VIRGEN', 'PLT', 'AG3', 14.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('PUNTO HUICHOL', 'PLT', 'AG3', 17.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CADENA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('HEBILLA', 'PLT', 'AG3', 12.0, 'Por gramo');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('AROS', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('MIL CRUCES', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('CINCO CORDONES', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('GUÍA FLORES', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('QUIMERA', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('COPA CABANA', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('RANCHO', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('MIL HOJAS', 'PIT', 'PITA 3X3/4X4/6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('FUNDA PARA NAVAJA', 'PIT', 'PITA 4X4/6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('GUÍA OVALO', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('MOSAICO', 'PIT', 'PITA 6X6', NULL, 'Precio variable');
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES ('GRECAS', 'PIT', 'PITA 6X6', NULL, 'Precio variable');

INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Adrián', 'Adrián', 737, 'PLT', NULL, 1, '2025-01-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Adrián Emilio López Sánchez', 'Adrián Emilio López Sánchez', 737, 'PIT', NULL, 1, '2025-02-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Alejandro', 'Alejandro', 663, 'PLT', NULL, 1, '2025-01-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Alejandro López Alatorre', 'Alejandro López Alatorre', 467, 'TLL', 'Ventana', 1, '2024-11-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ángel', 'Ángel', 762, 'PLT/PIT', NULL, 1, '2025-01-20');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ángel (756)', 'Ángel', 756, 'PIT', NULL, 1, '2025-03-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Arturo', 'Arturo', 487, 'PLT', NULL, 1, '2025-01-12');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Brian', 'Brian', 776, 'PLT/PIT', NULL, 1, '2025-01-08');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Cristian (815)', 'Cristian', 815, 'PLT', NULL, 1, '2025-01-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Cristian (832)', 'Cristian', 832, 'PLT', NULL, 1, '2025-02-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Cristian (332)', 'Cristian', 332, 'PLT', NULL, 1, '2025-01-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Diego (487)', 'Diego', 487, 'PLT', NULL, 1, '2025-01-07');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Diego (552)', 'Diego', 552, 'PLT', NULL, 1, '2025-02-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Erick Valerio Quezada', 'Erick Valerio Quezada', 827, 'PLT', NULL, 1, '2025-01-22');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ernesto Munguía Hernández', 'Ernesto Munguía Hernández', 844, 'PLT', NULL, 1, '2025-01-25');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Esteban Adrián', 'Esteban Adrián', 487, 'PLT', NULL, 1, '2025-03-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Felipe Coronado Covarrubias', 'Felipe Coronado Covarrubias', 571, 'PLT', NULL, 1, '2025-01-14');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Francisco', 'Francisco', 1048, 'PLT', NULL, 1, '2025-01-30');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Francisco Javier Chávez Domínguez', 'Francisco Javier Chávez Domínguez', 388, 'TLL', 'Montador', 1, '2024-10-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Héctor Melecio', 'Héctor Melecio', 852, 'PIT', NULL, 1, '2025-02-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Héctor Miranda', 'Héctor Miranda', 337, 'PLT', NULL, 1, '2025-01-11');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Hugo Alejandro', 'Hugo Alejandro', 366, 'PLT', NULL, 1, '2025-01-09');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Jorge', 'Jorge', 867, 'PLT', NULL, 1, '2025-01-16');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Jorge Alberto', 'Jorge Alberto', 563, 'PLT', NULL, 1, '2025-01-13');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José (572)', 'José', 572, 'PLT', NULL, 1, '2025-01-06');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Alberto', 'José Alberto', 634, 'PIT', NULL, 1, '2025-02-20');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José de los Santos', 'José de los Santos', 822, 'PLT', NULL, 1, '2025-01-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Luis Vela', 'José Luis Vela', 428, 'PLT', NULL, 1, '2025-01-19');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Martínez', 'José Martínez', 372, 'PLT', NULL, 1, '2025-01-04');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Omar', 'José Omar', 732, 'PLT', NULL, 1, '2025-01-21');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Juan (876)', 'Juan', 876, 'PLT', NULL, 1, '2025-01-23');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Juan Diego', 'Juan Diego', 672, 'PLT', NULL, 1, '2025-01-24');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Juan (584)', 'Juan', 584, 'PLT', NULL, 1, '2025-02-08');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Luis (833)', 'Luis', 833, 'PLT', NULL, 1, '2025-01-26');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Manuel Ramírez', 'Manuel Ramírez', 482, 'PLT', NULL, 1, '2025-01-27');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Martín López', 'Martín López', 815, 'PLT', NULL, 1, '2025-01-28');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Octavio González', 'Octavio González', 888, 'PLT', NULL, 1, '2025-01-29');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Octavio González', 'Octavio González', 264, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Óscar Adrián Gutiérrez Pérez', 'Óscar Adrián Gutiérrez Pérez', 633, 'TLL', 'Montador', 1, '2024-12-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Pedro Martínez García', 'Pedro Martínez García', 487, 'PLT', NULL, 1, '2025-01-03');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Pedro Rivera', 'Pedro Rivera', 533, 'PLT', NULL, 1, '2025-01-31');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ricardo', 'Ricardo', 868, 'PLT', NULL, 1, '2025-02-02');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ricardo Tapetillo', 'Ricardo Tapetillo', 817, 'PLT', NULL, 1, '2025-02-03');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Salvador (622)', 'Salvador', 622, 'PIT', NULL, 1, '2025-02-04');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Saúl Jaramillo Andrade', 'Saúl Jaramillo Andrade', 973, 'PLT', NULL, 1, '2025-02-06');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Sergio', 'Sergio', 832, 'PLT', NULL, 1, '2025-02-07');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Uriel Andrés', 'Uriel Andrés', 843, 'PLT', NULL, 1, '2025-02-09');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('William', 'William', 776, 'PLT/PIT', NULL, 1, '2025-02-11');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Mario', 'Mario', 257, 'PLT', NULL, 1, '2025-02-12');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Luis Armando Galicia Toralex', 'Luis Armando Galicia Toralex', 336, 'PLT', NULL, 1, '2025-02-13');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Eduardo', 'Eduardo Siordia', 337, 'PLT', NULL, 1, '2025-02-14');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Everardo Muñoz', 'Everardo Muñoz', 344, 'PLT', NULL, 1, '2025-02-16');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Óscar Carranza', 'Óscar Carranza', 353, 'PLT', NULL, 1, '2025-02-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Hugo Noé', 'Hugo Noé', 355, 'PLT', NULL, 1, '2025-02-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Hugo (355)', 'Hugo', 355, 'PLT', NULL, 1, '2025-02-19');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Antonio', 'Antonio', 372, 'PLT', NULL, 1, '2025-02-21');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Edgar', 'Edgar', 381, 'PLT', NULL, 1, '2025-02-22');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Felipe (417)', 'Felipe', 417, 'PLT', NULL, 1, '2025-02-23');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Vicente Yahir Domínguez', 'Vicente Yahir Domínguez', 428, 'PLT', NULL, 1, '2025-02-24');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Jesús', 'Jesús', 437, 'PLT', NULL, 1, '2025-02-25');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ismael Bernal', 'Ismael Bernal', 462, 'PLT', NULL, 1, '2025-02-26');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Luis Íñiguez', 'Luis Íñiguez', 473, 'PLT', NULL, 1, '2025-02-27');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Rubén', 'Rubén', 475, 'PLT', NULL, 1, '2025-02-28');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Iván Díaz', 'Iván Díaz', 487, 'PLT', NULL, 1, '2025-03-02');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Cervando Leos', 'Cervando Leos', 578, 'PLT', NULL, 1, '2025-03-03');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Benjamín (578)', 'Benjamín', 578, 'PLT', NULL, 1, '2025-03-04');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Miguel Ortiz Méndez', 'Miguel Ortiz Méndez', 584, 'PLT', NULL, 1, '2025-03-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Jaime', 'Jaime', 682, 'PLT', NULL, 1, '2025-03-06');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Molina', 'Molina', 754, 'PLT', NULL, 1, '2025-03-07');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Daniel', 'Daniel', 772, 'PLT', NULL, 1, '2025-03-08');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Carlos Anguiano', 'Carlos Anguiano', 777, 'PLT', NULL, 1, '2025-03-09');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Julio (828)', 'Julio', 828, 'PLT', NULL, 1, '2025-03-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Luis Tamayo', 'José Luis Tamayo', 366, 'TLL', 'Montador', 1, '2024-09-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Valentín Machuca', 'Valentín Machuca', 421, 'TLL', 'Aseo', 1, '2024-10-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Jonathan Valderra Reyes', 'Jonathan Valderra Reyes', 424, 'TLL', 'Burbuja', 1, '2024-11-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Salvador Preciado Gutiérrez', 'Salvador Preciado Gutiérrez', 528, 'TLL', 'Ventana', 1, '2024-12-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Benjamín Ezequiel Ramos Hernández', 'Benjamín Ezequiel Ramos Hernández', 578, 'TLL', 'Detallador', 1, '2025-01-02');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Víctor Flores Gámez', 'Víctor Flores Gámez', 584, 'TLL', 'Rayador', 1, '2025-01-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Óscar Eduardo Razo Valadez', 'Óscar Eduardo Razo Valadez', 616, 'TLL', 'Burbuja', 1, '2025-02-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Román Flores Flores', 'José Román Flores Flores', 657, 'TLL', 'Ventana', 1, '2024-11-20');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Nemecio Rincón Martínez', 'Nemecio Rincón Martínez', 884, 'TLL', 'Montador', 1, '2024-10-20');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Marco Antonio López Aguilera', 'Marco Antonio López Aguilera', 882, 'TLL', 'Montador', 1, '2024-12-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Carlos Francisco Trinidad', 'Carlos Francisco Trinidad', 1067, 'TLL', 'Detallador', 1, '2025-01-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ricardo Vargas Hernández', 'Ricardo Vargas Hernández', 741, 'TLL', 'Rayador', 1, '2025-02-10');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Gerónimo Cruz Cabrera', 'Gerónimo Cruz Cabrera', 455, 'TLL', 'Torcedor', 1, '2024-09-15');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Martín Sánchez Serio', 'Martín Sánchez Serio', 854, 'TLL', 'Torcedor', 1, '2024-10-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Luis Carrillo', 'José Luis Carrillo', 862, 'TLL', 'Torcedor', 1, '2024-11-01');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Moisés Martínez Juárez', 'José Moisés Martínez Juárez', 644, 'TLL', 'Torcedor', 1, '2025-01-05');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Alejandro Villanueva', 'Alejandro Villanueva', 324, 'PLT', NULL, 1, '2026-08-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Carlos (335)', 'Carlos Alberto', 335, 'PLT', NULL, 1, '2026-08-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Hector', 'Hector', 337, 'PLT', NULL, 1, '2026-08-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Oscar (353)', 'Oscar', 353, 'PLT', NULL, 1, '2026-08-17');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Trinidad', 'Trinidad', 371, 'Mixto', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Hugo (741)', 'Hugo', 741, 'PLT/PIT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Alfredo (757)', 'Alfredo', 757, 'PLT/PIT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Juan (515)', 'Juan', 515, 'PLT/PIT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Noé (565)', 'Noé', 565, 'PLT/PIT', NULL, 1, '2026-08-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Oscar (737)', 'Oscar', 737, 'PLT/PIT', NULL, 1, '2026-08-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José (216)', 'José', 216, 'PLT/PIT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José Antonio', 'José Antonio', 315, 'PLT/PIT', NULL, 1, '2026-08-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Luis (474)', 'Luis', 474, 'PLT/PIT', NULL, 1, '2026-08-18');
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Ángel (762)', 'Ángel (762)', 762, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Eduardo Siordia', 'Eduardo Siordia', 337, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Octavio (264)', 'Octavio (264)', 264, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('José (644)', 'José (644)', 644, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Antonio', 'Antonio', 315, 'PLT', NULL, 1, NULL);
INSERT INTO trabajadores (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES ('Gerónimo Cruz', 'Gerónimo Cruz', 455, 'PLT', NULL, 1, NULL);

INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES
  ('16-22', '2026-08-16', '2026-08-22', 2026, 'Agosto 2026');
SET @semana_id = LAST_INSERT_ID();

-- Adrián ubic 737 folio ST-196
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Adrián' AND ubic=737 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-196', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Adrián', 737,
  'ST-196', 'Rombos', 'AG3', 12.0,
  NULL, NULL, 3.9, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Alejandro ubic 663 folio ST-170
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Alejandro' AND ubic=663 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-170', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Alejandro', 663,
  'ST-170', 'Cubos', 'AG3', 12.0,
  4.6, NULL, 3.5, 4.5, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ángel (762) ubic 762 folio P-215
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ángel (762)' AND ubic=762 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-215', 'Mil Hojas', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ángel (762)', 762,
  'P-215', 'Mil Hojas', 'AG3', 16.0,
  5.3, 3.8, 12.5, 3.5, 9.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ángel (762) ubic 762 folio P-340
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ángel (762)' AND ubic=762 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-340', 'Bolso', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ángel (762)', 762,
  'P-340', 'Bolso', 'AG3', 12.0,
  NULL, NULL, 13.0, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Arturo ubic 487 folio ST-199
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Arturo' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-199', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Arturo', 487,
  'ST-199', 'Rombos', 'AG3', 12.0,
  3.8, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Arturo ubic 487 folio P-341
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Arturo' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-341', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Arturo', 487,
  'P-341', 'Centellas', 'AG3', 12.0,
  NULL, NULL, NULL, 6.7, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Brian ubic 776 folio F-019-X
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Brian' AND ubic=776 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-X', 'Aros', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Brian', 776,
  'F-019-X', 'Aros', 'AG3', 14.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Brian ubic 776 folio P-327
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Brian' AND ubic=776 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-327', 'Animales', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Brian', 776,
  'P-327', 'Animales', 'AG3', 13.0,
  NULL, NULL, NULL, NULL, 4.8, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cristian (815) ubic 815 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cristian (815)' AND ubic=815 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cristian (815)', 815,
  'P-310', 'Diamante', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cristian (815) ubic 815 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cristian (815)' AND ubic=815 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cristian (815)', 815,
  'P-310', 'Diamante', 'DOL', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cristian (832) ubic 832 folio ST-206
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cristian (832)' AND ubic=832 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-206', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cristian (832)', 832,
  'ST-206', 'Centellas', 'AG3', 12.0,
  3.8, NULL, 4.2, 6.8, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cristian (332) ubic 332 folio ST-149
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cristian (332)' AND ubic=332 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-149', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cristian (332)', 332,
  'ST-149', 'Centella', 'AG3', 12.0,
  3.0, 3.7, 3.2, NULL, 3.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Diego (487) ubic 487 folio ST-227
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Diego (487)' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-227', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Diego (487)', 487,
  'ST-227', 'Centella', 'AG3', 12.0,
  8.9, NULL, 3.6, 6.9, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Diego (487) ubic 487 folio Texana
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Diego (487)' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'Texana', 'Pavo', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Diego (487)', 487,
  'Texana', 'Pavo', 'DOL', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Diego (552) ubic 552 folio ST-226
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Diego (552)' AND ubic=552 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-226', NULL, 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Diego (552)', 552,
  'ST-226', NULL, 'AG3', 12.0,
  NULL, NULL, 3.2, 7.5, 9.1, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Erick Valerio Quezada ubic 827 folio ST-229
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Erick Valerio Quezada' AND ubic=827 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-229', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Erick Valerio Quezada', 827,
  'ST-229', 'Cubos', 'AG3', 12.0,
  8.2, 7.1, NULL, 8.3, 6.1, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ernesto Munguía Hernández ubic 844 folio P-292
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ernesto Munguía Hernández' AND ubic=844 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-292', 'Aros', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ernesto Munguía Hernández', 844,
  'P-292', 'Aros', 'AG3', 14.0,
  NULL, 5.3, NULL, 9.2, 3.8, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Esteban Adrián ubic 487 folio ST-203
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Esteban Adrián' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-203', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Esteban Adrián', 487,
  'ST-203', 'Centella', 'AG3', 12.0,
  3.0, 7.3, NULL, 7.7, 2.4, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Felipe Coronado Covarrubias ubic 571 folio ST-212
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Felipe Coronado Covarrubias' AND ubic=571 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-212', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Felipe Coronado Covarrubias', 571,
  'ST-212', 'Centella', 'AG3', 12.0,
  3.5, 8.5, 2.9, 8.3, 4.2, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Héctor Miranda ubic 337 folio F-010
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Héctor Miranda' AND ubic=337 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-010', 'Aros', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Héctor Miranda', 337,
  'F-010', 'Aros', 'AG3', 14.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Héctor Miranda ubic 337 folio F-019-3
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Héctor Miranda' AND ubic=337 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-3', 'Mil Cruces', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Héctor Miranda', 337,
  'F-019-3', 'Mil Cruces', 'AG3', 16.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hugo Alejandro ubic 366 folio F-023-A
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hugo Alejandro' AND ubic=366 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-A', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hugo Alejandro', 366,
  'F-023-A', 'Centellas', 'AG3', 12.0,
  7.8, 4.6, 7.3, 8.9, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Jorge ubic 867 folio P-309
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Jorge' AND ubic=867 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-309', 'Gallo', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Jorge', 867,
  'P-309', 'Gallo', 'AG3', 13.0,
  3.1, 4.1, NULL, 3.7, 4.4, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Jorge ubic 867 folio P-309
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Jorge' AND ubic=867 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-309', 'Gallo', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Jorge', 867,
  'P-309', 'Gallo', 'DOL', 13.0,
  NULL, NULL, 5.1, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Jorge Alberto ubic 563 folio F-023-C
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Jorge Alberto' AND ubic=563 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-C', NULL, 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Jorge Alberto', 563,
  'F-023-C', NULL, 'AG3', 12.0,
  NULL, 5.4, 9.6, 4.5, 4.6, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José (572) ubic 572 folio ST-224
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José (572)' AND ubic=572 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-224', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José (572)', 572,
  'ST-224', 'Secuencia', 'AG3', 12.0,
  11.3, 7.6, 3.7, 10.8, 8.2, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José de los Santos ubic 822 folio F-19-9
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José de los Santos' AND ubic=822 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-19-9', 'Aros', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José de los Santos', 822,
  'F-19-9', 'Aros', 'AG3', 13.0,
  3.1, NULL, NULL, 7.7, 3.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Luis Vela ubic 428 folio P-236
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Luis Vela' AND ubic=428 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-236', 'Mil Cruces', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Luis Vela', 428,
  'P-236', 'Mil Cruces', 'AG3', 16.0,
  7.6, NULL, 3.7, 2.4, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Luis Vela ubic 428 folio P-338
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Luis Vela' AND ubic=428 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-338', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Luis Vela', 428,
  'P-338', 'Rombos', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, 4.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Martínez ubic 372 folio ST-228
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Martínez' AND ubic=372 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-228', 'Flor Azteca', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Martínez', 372,
  'ST-228', 'Flor Azteca', 'AG3', 12.0,
  12.0, 4.5, 3.8, 10.6, 6.3, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Martínez ubic 372 folio P-296-A
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Martínez' AND ubic=372 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-296-A', 'Guia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Martínez', 372,
  'P-296-A', 'Guia', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Martínez ubic 372 folio P-326
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Martínez' AND ubic=372 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-326', 'Petatillo', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Martínez', 372,
  'P-326', 'Petatillo', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Martínez ubic 372 folio REP
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Martínez' AND ubic=372 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'REP', 'Reparación', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Martínez', 372,
  'REP', 'Reparación', 'AG3', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (876) ubic 876 folio P-246
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (876)' AND ubic=876 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-246', 'Aros', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (876)', 876,
  'P-246', 'Aros', 'AG3', 14.0,
  NULL, NULL, 4.0, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (876) ubic 876 folio P-265
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (876)' AND ubic=876 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-265', 'Quimera', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (876)', 876,
  'P-265', 'Quimera', 'AG3', 16.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (876) ubic 876 folio F-019-Y
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (876)' AND ubic=876 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-Y', NULL, 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (876)', 876,
  'F-019-Y', NULL, 'AG3', 12.0,
  NULL, NULL, NULL, 9.9, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan Diego ubic 672 folio ST-207
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan Diego' AND ubic=672 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-207', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan Diego', 672,
  'ST-207', 'Rombos', 'AG3', 12.0,
  NULL, 7.7, NULL, 6.0, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan Diego ubic 672 folio None
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan Diego' AND ubic=672 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, NULL, 'H. N.', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan Diego', 672,
  NULL, 'H. N.', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, 3.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (584) ubic 584 folio None
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (584)' AND ubic=584 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, NULL, 'Calendario', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (584)', 584,
  NULL, 'Calendario', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, 8.4, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (584) ubic 584 folio P-248
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (584)' AND ubic=584 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-248', 'Mil Hojas', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (584)', 584,
  'P-248', 'Mil Hojas', 'AG3', 16.0,
  4.5, 4.7, 3.8, 4.5, 4.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Luis (833) ubic 833 folio ST-220
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Luis (833)' AND ubic=833 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-220', 'Cadena', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Luis (833)', 833,
  'ST-220', 'Cadena', 'AG3', 12.0,
  4.6, 4.1, NULL, 3.8, 8.2, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Manuel Ramírez ubic 482 folio ST-225
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Manuel Ramírez' AND ubic=482 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-225', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Manuel Ramírez', 482,
  'ST-225', 'Secuencia', 'AG3', 12.0,
  NULL, 7.5, 3.9, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Manuel Ramírez ubic 482 folio R-337
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Manuel Ramírez' AND ubic=482 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'R-337', 'Cartera', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Manuel Ramírez', 482,
  'R-337', 'Cartera', 'AG3', 12.0,
  3.9, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Martín López ubic 815 folio ST-209
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Martín López' AND ubic=815 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-209', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Martín López', 815,
  'ST-209', 'Cubos', 'AG3', 12.0,
  7.8, NULL, 4.7, 4.5, 3.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Pedro Martínez García ubic 487 folio ST-202
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Pedro Martínez García' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-202', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Pedro Martínez García', 487,
  'ST-202', 'Secuencia', 'AG3', 12.0,
  NULL, NULL, 3.8, 3.7, 3.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Pedro Martínez García ubic 487 folio F-019-7
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Pedro Martínez García' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-7', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Pedro Martínez García', 487,
  'F-019-7', 'Centella', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Pedro Rivera ubic 533 folio P-320
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Pedro Rivera' AND ubic=533 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-320', 'Grecas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Pedro Rivera', 533,
  'P-320', 'Grecas', 'AG3', 12.0,
  8.4, 9.0, 3.5, 12.4, 4.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo ubic 868 folio REP
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo' AND ubic=868 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'REP', 'Reparación', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo', 868,
  'REP', 'Reparación', 'AG3', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo ubic 868 folio P-302
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo' AND ubic=868 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-302', 'Versace', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo', 868,
  'P-302', 'Versace', 'DOL', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo ubic 868 folio P-318
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo' AND ubic=868 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-318', 'Aros', 'AG3', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo', 868,
  'P-318', 'Aros', 'AG3', 13.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo ubic 868 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo' AND ubic=868 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo', 868,
  'P-310', 'Diamante', 'DOL', 13.0,
  4.8, NULL, 9.3, 4.9, 2.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo ubic 868 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo' AND ubic=868 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo', 868,
  'P-310', 'Diamante', 'AG3', 12.0,
  5.0, 8.3, NULL, 4.1, 6.8, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo Tapetillo ubic 817 folio ST-223
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo Tapetillo' AND ubic=817 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-223', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo Tapetillo', 817,
  'ST-223', 'Rombos', 'AG3', 12.0,
  6.8, 8.4, NULL, 4.5, 3.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ricardo Tapetillo ubic 817 folio F-019-H
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ricardo Tapetillo' AND ubic=817 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-H', 'Guia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ricardo Tapetillo', 817,
  'F-019-H', 'Guia', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Sergio ubic 832 folio P-334
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Sergio' AND ubic=832 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-334', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Sergio', 832,
  'P-334', 'Cubos', 'AG3', 12.0,
  17.8, 3.5, 3.2, 7.0, 3.8, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Uriel Andrés ubic 843 folio ST-221
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Uriel Andrés' AND ubic=843 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-221', '5Cordones', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Uriel Andrés', 843,
  'ST-221', '5Cordones', 'AG3', 12.0,
  3.6, 8.2, NULL, 6.9, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- William ubic 776 folio ST-231
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='William' AND ubic=776 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-231', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'William', 776,
  'ST-231', 'Centellas', 'AG3', 12.0,
  NULL, NULL, NULL, 7.5, 3.3, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- William ubic 776 folio ST-216
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='William' AND ubic=776 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-216', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'William', 776,
  'ST-216', 'Centellas', 'AG3', 12.0,
  9.9, 5.5, 2.0, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Mario ubic 257 folio ST-0576
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Mario' AND ubic=257 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-0576', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Mario', 257,
  'ST-0576', 'Secuencia', 'AG3', 12.0,
  3.7, 4.7, NULL, 3.8, 4.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Eduardo Siordia ubic 337 folio ST-222
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Eduardo Siordia' AND ubic=337 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-222', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Eduardo Siordia', 337,
  'ST-222', 'Centellas', 'AG3', 12.0,
  9.8, 4.5, NULL, 9.0, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Everardo Muñoz ubic 344 folio F-19-S
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Everardo Muñoz' AND ubic=344 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-19-S', 'Infinito', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Everardo Muñoz', 344,
  'F-19-S', 'Infinito', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Everardo Muñoz ubic 344 folio P-332
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Everardo Muñoz' AND ubic=344 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-332', 'Cadena', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Everardo Muñoz', 344,
  'P-332', 'Cadena', 'AG3', 12.0,
  NULL, 4.1, 7.2, 7.3, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Óscar Carranza ubic 353 folio P-333
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Óscar Carranza' AND ubic=353 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-333', 'Mil Hojas', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Óscar Carranza', 353,
  'P-333', 'Mil Hojas', 'AG3', 16.0,
  4.5, 4.4, 4.6, 4.6, 3.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hugo Noé ubic 355 folio P-261
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hugo Noé' AND ubic=355 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-261', 'Metralleta', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hugo Noé', 355,
  'P-261', 'Metralleta', 'AG3', 12.0,
  NULL, 5.3, NULL, 8.4, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Antonio ubic 372 folio ST-208
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Antonio' AND ubic=372 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-208', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Antonio', 372,
  'ST-208', 'Centellas', 'AG3', 12.0,
  NULL, NULL, NULL, 3.0, 3.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Edgar ubic 381 folio ST-213
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Edgar' AND ubic=381 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-213', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Edgar', 381,
  'ST-213', 'Secuencia', 'AG3', 12.0,
  8.8, 1.7, NULL, 4.6, 8.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Edgar ubic 381 folio P-339
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Edgar' AND ubic=381 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-339', 'Rambo IV', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Edgar', 381,
  'P-339', 'Rambo IV', 'AG3', 12.0,
  NULL, 4.2, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Vicente Yahir Domínguez ubic 428 folio ST-197
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Vicente Yahir Domínguez' AND ubic=428 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-197', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Vicente Yahir Domínguez', 428,
  'ST-197', 'Cubos', 'AG3', 12.0,
  NULL, NULL, 3.6, 3.7, 4.4, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Jesús ubic 437 folio F-019-5
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Jesús' AND ubic=437 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-5', 'Infinito', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Jesús', 437,
  'F-019-5', 'Infinito', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Jesús ubic 437 folio ST-192
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Jesús' AND ubic=437 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-192', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Jesús', 437,
  'ST-192', 'Rombos', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Ismael Bernal ubic 462 folio F-019-1
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Ismael Bernal' AND ubic=462 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-1', 'Infinito', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Ismael Bernal', 462,
  'F-019-1', 'Infinito', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Iván Díaz ubic 487 folio F-023-D
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Iván Díaz' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-D', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Iván Díaz', 487,
  'F-023-D', 'Secuencia', 'AG3', 12.0,
  5.9, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Iván Díaz ubic 487 folio ST-219
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Iván Díaz' AND ubic=487 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-219', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Iván Díaz', 487,
  'ST-219', 'Cubos', 'AG3', 12.0,
  NULL, NULL, 3.3, 6.7, 6.1, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cervando Leos ubic 578 folio ST-204
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cervando Leos' AND ubic=578 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-204', 'Centella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cervando Leos', 578,
  'ST-204', 'Centella', 'AG3', 12.0,
  4.3, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cervando Leos ubic 578 folio F-019-K
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cervando Leos' AND ubic=578 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-K', NULL, 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cervando Leos', 578,
  'F-019-K', NULL, 'AG3', 12.0,
  NULL, 6.0, 6.0, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Cervando Leos ubic 578 folio ST-230
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Cervando Leos' AND ubic=578 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-230', 'Guia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Cervando Leos', 578,
  'ST-230', 'Guia', 'AG3', 12.0,
  NULL, NULL, NULL, 3.9, 6.6, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Benjamín (578) ubic 578 folio REP
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Benjamín (578)' AND ubic=578 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'REP', 'Reparación Concha', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Benjamín (578)', 578,
  'REP', 'Reparación Concha', 'AG3', 14.0,
  NULL, NULL, NULL, 3.0, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Miguel Ortiz Méndez ubic 584 folio P-317
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Miguel Ortiz Méndez' AND ubic=584 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-317', 'Aros', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Miguel Ortiz Méndez', 584,
  'P-317', 'Aros', 'AG3', 12.0,
  NULL, 9.5, 3.0, 3.3, 9.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Miguel Ortiz Méndez ubic 584 folio F-019-A
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Miguel Ortiz Méndez' AND ubic=584 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-A', 'Mil Cruces', 'AG3', 16.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Miguel Ortiz Méndez', 584,
  'F-019-A', 'Mil Cruces', 'AG3', 16.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Miguel Ortiz Méndez ubic 584 folio P-317
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Miguel Ortiz Méndez' AND ubic=584 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-317', 'Aros', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Miguel Ortiz Méndez', 584,
  'P-317', 'Aros', 'DOL', 13.0,
  NULL, NULL, 1.8, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Molina ubic 754 folio F-023-B
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Molina' AND ubic=754 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-B', 'Sentella', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Molina', 754,
  'F-023-B', 'Sentella', 'AG3', 12.0,
  NULL, NULL, 3.8, 4.1, 4.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Daniel ubic 772 folio ST-48
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Daniel' AND ubic=772 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-48', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Daniel', 772,
  'ST-48', 'Cubos', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Octavio (264) ubic 264 folio PT-328
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Octavio (264)' AND ubic=264 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'PT-328', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Octavio (264)', 264,
  'PT-328', 'Secuencia', 'AG3', 12.0,
  8.3, 1.9, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Octavio (264) ubic 264 folio PT-338
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Octavio (264)' AND ubic=264 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'PT-338', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Octavio (264)', 264,
  'PT-338', 'Rombos', 'AG3', 12.0,
  NULL, 4.9, 8.3, 4.4, 16.6, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Octavio (264) ubic 264 folio F-019-X
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Octavio (264)' AND ubic=264 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-X', 'Guia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Octavio (264)', 264,
  'F-019-X', 'Guia', 'AG3', 12.0,
  NULL, NULL, 4.5, 4.4, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hector ubic 337 folio F-019-3
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hector' AND ubic=337 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-3', NULL, NULL, NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hector', 337,
  'F-019-3', NULL, NULL, NULL,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Trinidad ubic 371 folio F-023-A
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Trinidad' AND ubic=371 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-A', 'Costura', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Trinidad', 371,
  'F-023-A', 'Costura', 'AG3', 12.0,
  3.6, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Trinidad ubic 371 folio REP
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Trinidad' AND ubic=371 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'REP', 'Reparación', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Trinidad', 371,
  'REP', 'Reparación', 'AG3', 12.0,
  NULL, 2.4, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hugo (741) ubic 741 folio P-311
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hugo (741)' AND ubic=741 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-311', 'Escalera', 'DOL', 13.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hugo (741)', 741,
  'P-311', 'Escalera', 'DOL', 13.0,
  NULL, 2.2, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hugo (741) ubic 741 folio F-023-F
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hugo (741)' AND ubic=741 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-F', NULL, 'AG3', NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hugo (741)', 741,
  'F-023-F', NULL, 'AG3', NULL,
  NULL, NULL, 4.5, 7.5, 6.3, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hugo (741) ubic 741 folio P-311
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hugo (741)' AND ubic=741 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-311', 'Escalera', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hugo (741)', 741,
  'P-311', 'Escalera', 'AG3', 12.0,
  4.0, NULL, 1.6, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Angel (756) ubic 756 folio None
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Angel (756)' AND ubic=756 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, NULL, 'Pulsera', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Angel (756)', 756,
  NULL, 'Pulsera', 'AG3', 12.0,
  NULL, NULL, NULL, 1.5, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Angel (756) ubic 756 folio EXT
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Angel (756)' AND ubic=756 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'EXT', 'Extensibles', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Angel (756)', 756,
  'EXT', 'Extensibles', 'AG3', 12.0,
  NULL, NULL, 2.3, 0.8, 0.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Alfredo (757) ubic 757 folio F-019-W
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Alfredo (757)' AND ubic=757 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-W', 'Versace', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Alfredo (757)', 757,
  'F-019-W', 'Versace', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Hector Melecio ubic 852 folio F-019-5
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Hector Melecio' AND ubic=852 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-5', 'Versace', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Hector Melecio', 852,
  'F-019-5', 'Versace', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (515) ubic 515 folio P-235
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (515)' AND ubic=515 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-235', 'Aros', 'AG3', 14.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (515)', 515,
  'P-235', 'Aros', 'AG3', 14.0,
  8.1, 6.8, 7.4, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (515) ubic 515 folio F-024
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (515)' AND ubic=515 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-024', 'Flor Azteca', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (515)', 515,
  'F-024', 'Flor Azteca', 'AG3', 12.0,
  NULL, NULL, 7.4, 14.4, 7.8, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (515) ubic 515 folio P-338
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (515)' AND ubic=515 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-338', 'Rombos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (515)', 515,
  'P-338', 'Rombos', 'AG3', 12.0,
  NULL, NULL, NULL, 3.3, 11.9, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Juan (515) ubic 515 folio F-019-5
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Juan (515)' AND ubic=515 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-5', 'Versace', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Juan (515)', 515,
  'F-019-5', 'Versace', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Noé (565) ubic 565 folio F-023-F
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Noé (565)' AND ubic=565 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-023-F', NULL, 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Noé (565)', 565,
  'F-023-F', NULL, 'AG3', 12.0,
  6.2, NULL, 7.7, 3.8, 10.6, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Noé (565) ubic 565 folio P-305
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Noé (565)' AND ubic=565 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-305', 'Almanaque', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Noé (565)', 565,
  'P-305', 'Almanaque', 'AG3', 12.0,
  5.5, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Alberto ubic 634 folio None
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Alberto' AND ubic=634 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, NULL, 'Precilla', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Alberto', 634,
  NULL, 'Precilla', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, 4.5, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José (644) ubic 644 folio ST-211
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José (644)' AND ubic=644 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-211', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José (644)', 644,
  'ST-211', 'Cubos', 'AG3', 12.0,
  6.7, 2.9, NULL, 3.1, 7.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Oscar (737) ubic 737 folio REP
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Oscar (737)' AND ubic=737 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'REP', 'Reparación', 'AG3', NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Oscar (737)', 737,
  'REP', 'Reparación', 'AG3', NULL,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Oscar (737) ubic 737 folio P-302
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Oscar (737)' AND ubic=737 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-302', 'Versace', 'DOL', NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Oscar (737)', 737,
  'P-302', 'Versace', 'DOL', NULL,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Oscar (737) ubic 737 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Oscar (737)' AND ubic=737 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'AG3', NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Oscar (737)', 737,
  'P-310', 'Diamante', 'AG3', NULL,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Oscar (737) ubic 737 folio P-310
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Oscar (737)' AND ubic=737 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-310', 'Diamante', 'DOL', NULL, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Oscar (737)', 737,
  'P-310', 'Diamante', 'DOL', NULL,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José (216) ubic 216 folio F-019-4
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José (216)' AND ubic=216 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-4', 'Rombo V', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José (216)', 216,
  'F-019-4', 'Rombo V', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- José Antonio ubic 315 folio ST-190
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='José Antonio' AND ubic=315 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-190', 'Cubos', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'José Antonio', 315,
  'ST-190', 'Cubos', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Antonio ubic 315 folio ST-214
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Antonio' AND ubic=315 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-214', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Antonio', 315,
  'ST-214', 'Secuencia', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Carlos (335) ubic 335 folio ST-217
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Carlos (335)' AND ubic=335 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-217', 'Secuencia', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Carlos (335)', 335,
  'ST-217', 'Secuencia', 'AG3', 12.0,
  11.7, 8.4, 3.2, 10.7, 3.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Carlos (335) ubic 335 folio F-019-11
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Carlos (335)' AND ubic=335 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F-019-11', 'Infinito', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Carlos (335)', 335,
  'F-019-11', 'Infinito', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Gerónimo Cruz ubic 455 folio F019-1
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Gerónimo Cruz' AND ubic=455 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'F019-1', 'Diamante', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Gerónimo Cruz', 455,
  'F019-1', 'Diamante', 'AG3', 12.0,
  NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Gerónimo Cruz ubic 455 folio P-215
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Gerónimo Cruz' AND ubic=455 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-215', 'Mil Hojas', 'AG3', 15.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Gerónimo Cruz', 455,
  'P-215', 'Mil Hojas', 'AG3', 15.0,
  3.7, 6.8, 3.3, 6.7, 6.7, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Luis (474) ubic 474 folio P-321
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Luis (474)' AND ubic=474 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'P-321', 'Grecas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Luis (474)', 474,
  'P-321', 'Grecas', 'AG3', 12.0,
  8.5, 3.8, NULL, 3.0, 3.0, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;
-- Salvador (622) ubic 622 folio ST-219
SET @tid = (SELECT id FROM trabajadores WHERE nombre_mostrar='Salvador (622)' AND ubic=622 LIMIT 1);
INSERT INTO trabajos (trabajador_id, folio, modelo, material, tarifa_gr, activo, notas)
SELECT @tid, 'ST-219', 'Centellas', 'AG3', 12.0, 1, NULL
FROM DUAL WHERE @tid IS NOT NULL;
SET @trab_id = LAST_INSERT_ID();
INSERT INTO produccion_plata
  (semana_id, trabajador_id, trabajo_id, nombre, ubic, folio, modelo, material, tarifa_gr,
   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas)
SELECT @semana_id, @tid, IF(@trab_id=0, NULL, @trab_id), 'Salvador (622)', 622,
  'ST-219', 'Centellas', 'AG3', 12.0,
  2.3, 0.5, NULL, NULL, NULL, NULL, NULL, NULL
FROM DUAL WHERE @tid IS NOT NULL;

INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES ('02-05', '2026-05-02', '2026-05-08', 2026, 'Ejemplo');
INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas) SELECT id, 25145.0, 9715.0, 29344.4, 'Ejemplo' FROM semanas WHERE codigo='02-05' AND anio=2026 ORDER BY id DESC LIMIT 1;
INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES ('16-05', '2026-05-16', '2026-05-22', 2026, 'Ejemplo');
INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas) SELECT id, 21771.9, 15102.0, 33504.4, 'Ejemplo' FROM semanas WHERE codigo='16-05' AND anio=2026 ORDER BY id DESC LIMIT 1;
INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES ('30-05', '2026-05-30', '2026-06-05', 2026, 'Ejemplo');
INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas) SELECT id, 25145.0, 15151.0, 27379.46, 'Ejemplo' FROM semanas WHERE codigo='30-05' AND anio=2026 ORDER BY id DESC LIMIT 1;
INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES ('18-07', '2026-07-18', '2026-07-24', 2026, 'Parcial');
INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas) SELECT id, NULL, 10341.0, 27806.0, 'Parcial' FROM semanas WHERE codigo='18-07' AND anio=2026 ORDER BY id DESC LIMIT 1;

INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas)
SELECT @semana_id, COALESCE(SUM(efectivo),0), 0, 0, 'Calculado desde produccion_plata'
FROM produccion_plata WHERE semana_id=@semana_id;

SELECT 'trabajadores' t, COUNT(*) n FROM trabajadores
UNION ALL SELECT 'trabajos', COUNT(*) FROM trabajos
UNION ALL SELECT 'produccion_plata', COUNT(*) FROM produccion_plata
UNION ALL SELECT 'modelos', COUNT(*) FROM modelos
UNION ALL SELECT 'semanas', COUNT(*) FROM semanas;

SELECT p.nombre, p.ubic, p.folio, p.modelo, p.material, p.trabajador_id, p.trabajo_id, p.total_gramos, p.efectivo
FROM produccion_plata p
WHERE p.semana_id=@semana_id
ORDER BY p.ubic, p.nombre
LIMIT 15;

SELECT 'OK — esquema con trabajos ligados a trabajadores + datos Excel V3' AS resultado;
