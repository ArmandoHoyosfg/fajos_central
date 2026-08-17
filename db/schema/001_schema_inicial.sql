-- ============================================================
-- TALLER DE FAJOS CENTRAL - Script para base de datos fajos_central
-- MariaDB / HeidiSQL
-- Ejecutar directamente sobre la base de datos fajos_central
-- ============================================================

USE fajos_central;

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ============================================================
-- 1. TABLA: trabajadores
-- Mismo nombre + distinta ubic = personas diferentes
-- ============================================================
DROP TABLE IF EXISTS produccion_plata;
DROP TABLE IF EXISTS resumen_nominas;
DROP TABLE IF EXISTS semanas;
DROP TABLE IF EXISTS trabajadores;
DROP TABLE IF EXISTS modelos;
DROP TABLE IF EXISTS tarifas_material;

CREATE TABLE trabajadores (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  nombre_mostrar    VARCHAR(80)  NOT NULL COMMENT 'Nombre corto para listas e impresión',
  nombre_completo   VARCHAR(120) DEFAULT NULL,
  ubic              INT UNSIGNED NOT NULL COMMENT 'Número de ubicación / puesto de trabajo',
  tipo              ENUM('PLT','PIT','TLL','PLT/PIT','Mixto') NOT NULL DEFAULT 'PLT',
  puesto            VARCHAR(40)  DEFAULT NULL COMMENT 'Solo relevante para TLL',
  activo            TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '1=Sí, 0=No',
  fecha_incorporacion DATE DEFAULT NULL,
  notas             VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_nombre_ubic (nombre_mostrar, ubic),
  KEY idx_tipo_activo (tipo, activo),
  KEY idx_ubic (ubic)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Catálogo maestro de trabajadores';

-- ============================================================
-- 2. TABLA: modelos
-- ============================================================
CREATE TABLE modelos (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  modelo            VARCHAR(60)  NOT NULL,
  tipo              ENUM('PLT','PIT') NOT NULL,
  material_default  VARCHAR(30)  DEFAULT NULL,
  tarifa_default    DECIMAL(8,2) DEFAULT NULL COMMENT 'Por gramo (PLT) o referencia (PIT)',
  notas             VARCHAR(120) DEFAULT NULL,
  activo            TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uk_modelo_tipo (modelo, tipo),
  KEY idx_tipo (tipo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Catálogo de modelos de fajos';

-- ============================================================
-- 3. TABLA: tarifas_material
-- ============================================================
CREATE TABLE tarifas_material (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  material          VARCHAR(20)  NOT NULL,
  tarifa_por_gramo  DECIMAL(8,2) NOT NULL,
  descripcion       VARCHAR(80)  DEFAULT NULL,
  activo            TINYINT(1)   NOT NULL DEFAULT 1,
  PRIMARY KEY (id),
  UNIQUE KEY uk_material (material)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Tarifas de labor por material (PLT)';

-- ============================================================
-- 4. TABLA: semanas (cabecera de cada semana de nómina)
-- ============================================================
CREATE TABLE semanas (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  codigo            VARCHAR(20)  NOT NULL COMMENT 'Ej: 02-05, 16-05, 18-07',
  fecha_inicio      DATE         NOT NULL,
  fecha_fin         DATE         NOT NULL,
  anio              SMALLINT     NOT NULL DEFAULT 2026,
  notas             VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_codigo_anio (codigo, anio)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Semanas de nómina';

-- ============================================================
-- 5. TABLA: produccion_plata
-- Detalle de trabajo en plata (gramos diarios)
-- ============================================================
CREATE TABLE produccion_plata (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id         INT UNSIGNED NOT NULL,
  trabajador_id     INT UNSIGNED DEFAULT NULL COMMENT 'FK opcional si ya está en catálogo',
  nombre            VARCHAR(80)  NOT NULL COMMENT 'Se guarda el nombre por si cambia el catálogo',
  ubic              INT UNSIGNED NOT NULL,
  folio             VARCHAR(30)  DEFAULT NULL,
  modelo            VARCHAR(60)  DEFAULT NULL,
  material          VARCHAR(20)  DEFAULT NULL,
  tarifa_gr         DECIMAL(8,2) DEFAULT NULL COMMENT '$ por gramo',
  gm_sab            DECIMAL(8,2) DEFAULT NULL,
  gm_dom            DECIMAL(8,2) DEFAULT NULL,
  gm_lun            DECIMAL(8,2) DEFAULT NULL,
  gm_mar            DECIMAL(8,2) DEFAULT NULL,
  gm_mie            DECIMAL(8,2) DEFAULT NULL,
  gm_jue            DECIMAL(8,2) DEFAULT NULL,
  gm_vie            DECIMAL(8,2) DEFAULT NULL,
  total_gramos      DECIMAL(10,2) GENERATED ALWAYS AS (
                      COALESCE(gm_sab,0)+COALESCE(gm_dom,0)+COALESCE(gm_lun,0)+
                      COALESCE(gm_mar,0)+COALESCE(gm_mie,0)+COALESCE(gm_jue,0)+COALESCE(gm_vie,0)
                    ) STORED,
  efectivo          DECIMAL(12,2) GENERATED ALWAYS AS (
                      ROUND( (COALESCE(gm_sab,0)+COALESCE(gm_dom,0)+COALESCE(gm_lun,0)+
                              COALESCE(gm_mar,0)+COALESCE(gm_mie,0)+COALESCE(gm_jue,0)+COALESCE(gm_vie,0)
                             ) * COALESCE(tarifa_gr,0) , 2)
                    ) STORED,
  firmado           TINYINT(1)   NOT NULL DEFAULT 0,
  notas             VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_semana (semana_id),
  KEY idx_trabajador (trabajador_id),
  KEY idx_nombre_ubic (nombre, ubic),
  CONSTRAINT fk_prod_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE,
  CONSTRAINT fk_prod_trabajador FOREIGN KEY (trabajador_id) REFERENCES trabajadores(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Producción semanal de plata (gramos). Total y efectivo calculados automáticamente';

-- ============================================================
-- 6. TABLA: resumen_nominas (totales por semana)
-- ============================================================
CREATE TABLE resumen_nominas (
  id                INT UNSIGNED NOT NULL AUTO_INCREMENT,
  semana_id         INT UNSIGNED NOT NULL,
  nomina_plt        DECIMAL(12,2) DEFAULT 0.00,
  nomina_pit        DECIMAL(12,2) DEFAULT 0.00,
  nomina_tll        DECIMAL(12,2) DEFAULT 0.00,
  total_semana      DECIMAL(12,2) GENERATED ALWAYS AS (
                      COALESCE(nomina_plt,0)+COALESCE(nomina_pit,0)+COALESCE(nomina_tll,0)
                    ) STORED,
  notas             VARCHAR(255) DEFAULT NULL,
  creado_en         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_semana (semana_id),
  CONSTRAINT fk_resumen_semana FOREIGN KEY (semana_id) REFERENCES semanas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='Resumen de totales de nómina por semana';

SET FOREIGN_KEY_CHECKS = 1;

-- ============================================================
-- DATOS INICIALES
-- ============================================================

-- ----- tarifas_material -----
INSERT INTO tarifas_material (material, tarifa_por_gramo, descripcion) VALUES
('AG3', 12.00, 'Plata AG3 estándar'),
('AG4', 13.00, 'Plata AG4'),
('DOL', 13.00, 'Dorado / Metal dorado'),
('DLO', 13.00, 'Dorado (variante)');

-- ----- modelos -----
INSERT INTO modelos (modelo, tipo, material_default, tarifa_default, notas) VALUES
('SECUENCIA',       'PLT', 'AG3', 12.00, 'Por gramo'),
('CUBOS',           'PLT', 'AG3', 12.00, 'Por gramo'),
('CINCO CORDONES',  'PLT', 'AG3', 12.00, 'Por gramo'),
('CENTELLA',        'PLT', 'AG3', 12.00, 'Por gramo'),
('CENTELLAS',       'PLT', 'AG3', 12.00, 'Por gramo'),
('ROMBOS',          'PLT', 'AG3', 12.00, 'Por gramo'),
('SANTA MARÍA',     'PLT', 'AG3', 12.00, 'Por gramo'),
('PAVO',            'PLT', 'AG3', 12.00, 'Por gramo'),
('PETATILLO',       'PLT', 'AG3', 12.00, 'Por gramo'),
('CHINELA',         'PLT', 'AG3', 12.00, 'Por gramo'),
('CHINELA GUÍA',    'PLT', 'AG3', 12.00, 'Por gramo'),
('COPA CABANA',     'PLT', 'AG3', 12.00, 'Por gramo'),
('GUÍA',            'PLT', 'AG3', 12.00, 'Por gramo'),
('AROS',            'PLT', 'AG3', 13.00, 'Por gramo'),
('QUIMERA',         'PLT', 'AG3', 12.00, 'Por gramo'),
('MIL HOJAS',       'PLT', 'AG3', 15.00, 'Por gramo'),
('TOQUILLA',        'PLT', 'AG3', 12.00, 'Por gramo'),
('REPARACIÓN',      'PLT', 'AG3', 12.00, 'Por gramo'),
('VIRGEN',          'PLT', 'AG3', 14.00, 'Por gramo'),
('PUNTO HUICHOL',   'PLT', 'AG3', 17.00, 'Por gramo'),
('CADENA',          'PLT', 'AG3', 12.00, 'Por gramo'),
('HEBILLA',         'PLT', 'AG3', 12.00, 'Por gramo'),
('AROS',            'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('MIL CRUCES',      'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('CINCO CORDONES',  'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('GUÍA FLORES',     'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('QUIMERA',         'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('COPA CABANA',     'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('RANCHO',          'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('MIL HOJAS',       'PIT', 'PITA 3X3/4X4/6X6', NULL, 'Precio variable'),
('FUNDA PARA NAVAJA','PIT','PITA 4X4/6X6', NULL, 'Precio variable'),
('GUÍA OVALO',      'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('MOSAICO',         'PIT', 'PITA 6X6', NULL, 'Precio variable'),
('GRECAS',          'PIT', 'PITA 6X6', NULL, 'Precio variable');

-- ----- trabajadores -----
INSERT INTO trabajadores (id, nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion) VALUES
(1,  'Adrián',                          'Adrián',                          737, 'PLT',     NULL, 1, '2025-01-15'),
(2,  'Adrián Emilio López Sánchez',     'Adrián Emilio López Sánchez',     737, 'PIT',     NULL, 1, '2025-02-01'),
(3,  'Alejandro',                       'Alejandro',                       663, 'PLT',     NULL, 1, '2025-01-10'),
(4,  'Alejandro López Alatorre',        'Alejandro López Alatorre',        467, 'TLL',     'Ventana', 1, '2024-11-01'),
(5,  'Ángel',                           'Ángel',                           762, 'PLT/PIT', NULL, 1, '2025-01-20'),
(6,  'Ángel (756)',                     'Ángel',                           756, 'PIT',     NULL, 1, '2025-03-01'),
(7,  'Arturo',                          'Arturo',                          487, 'PLT',     NULL, 1, '2025-01-12'),
(8,  'Brian',                           'Brian',                           776, 'PLT/PIT', NULL, 1, '2025-01-08'),
(9,  'Cristian (815)',                  'Cristian',                        815, 'PLT',     NULL, 1, '2025-01-05'),
(10, 'Cristian (832)',                  'Cristian',                        832, 'PLT',     NULL, 1, '2025-02-10'),
(11, 'Cristian (332)',                  'Cristian',                        332, 'PLT',     NULL, 1, '2025-01-18'),
(12, 'Diego (487)',                     'Diego',                           487, 'PLT',     NULL, 1, '2025-01-07'),
(13, 'Diego (552)',                     'Diego',                           552, 'PLT',     NULL, 1, '2025-02-15'),
(14, 'Erick Valerio Quezada',           'Erick Valerio Quezada',           827, 'PLT',     NULL, 1, '2025-01-22'),
(15, 'Ernesto Munguía Hernández',       'Ernesto Munguía Hernández',       844, 'PLT',     NULL, 1, '2025-01-25'),
(16, 'Esteban Adrián',                  'Esteban Adrián',                  487, 'PLT',     NULL, 1, '2025-03-01'),
(17, 'Felipe Coronado Covarrubias',     'Felipe Coronado Covarrubias',     571, 'PLT',     NULL, 1, '2025-01-14'),
(18, 'Francisco',                       'Francisco',                       1048,'PLT',     NULL, 1, '2025-01-30'),
(19, 'Francisco Javier Chávez Domínguez','Francisco Javier Chávez Domínguez',388,'TLL',    'Montador', 1, '2024-10-15'),
(20, 'Héctor Melecio',                  'Héctor Melecio',                  852, 'PIT',     NULL, 1, '2025-02-05'),
(21, 'Héctor Miranda',                  'Héctor Miranda',                  337, 'PLT',     NULL, 1, '2025-01-11'),
(22, 'Hugo Alejandro',                  'Hugo Alejandro',                  366, 'PLT',     NULL, 1, '2025-01-09'),
(23, 'Jorge',                           'Jorge',                           867, 'PLT',     NULL, 1, '2025-01-16'),
(24, 'Jorge Alberto',                   'Jorge Alberto',                   563, 'PLT',     NULL, 1, '2025-01-13'),
(25, 'José',                            'José',                            572, 'PLT',     NULL, 1, '2025-01-06'),
(26, 'José Alberto',                    'José Alberto',                    634, 'PIT',     NULL, 1, '2025-02-20'),
(27, 'José de los Santos',              'José de los Santos',              822, 'PLT',     NULL, 1, '2025-01-17'),
(28, 'José Luis Vela',                  'José Luis Vela',                  428, 'PLT',     NULL, 1, '2025-01-19'),
(29, 'José Martínez',                   'José Martínez',                   372, 'PLT',     NULL, 1, '2025-01-04'),
(30, 'José Omar',                       'José Omar',                       732, 'PLT',     NULL, 1, '2025-01-21'),
(31, 'Juan (876)',                      'Juan',                            876, 'PLT',     NULL, 1, '2025-01-23'),
(32, 'Juan Diego',                      'Juan Diego',                      672, 'PLT',     NULL, 1, '2025-01-24'),
(33, 'Juan (584)',                      'Juan',                            584, 'PLT',     NULL, 1, '2025-02-08'),
(34, 'Luis (833)',                      'Luis',                            833, 'PLT',     NULL, 1, '2025-01-26'),
(35, 'Manuel Ramírez',                  'Manuel Ramírez',                  482, 'PLT',     NULL, 1, '2025-01-27'),
(36, 'Martín López',                    'Martín López',                    815, 'PLT',     NULL, 1, '2025-01-28'),
(37, 'Octavio González',                'Octavio González',                888, 'PLT',     NULL, 1, '2025-01-29'),
(38, 'Óscar Adrián Gutiérrez Pérez',    'Óscar Adrián Gutiérrez Pérez',    633, 'TLL',     'Montador', 1, '2024-12-01'),
(39, 'Pedro Martínez García',           'Pedro Martínez García',           487, 'PLT',     NULL, 1, '2025-01-03'),
(40, 'Pedro Rivera',                    'Pedro Rivera',                    533, 'PLT',     NULL, 1, '2025-01-31'),
(41, 'Ricardo',                         'Ricardo',                         868, 'PLT',     NULL, 1, '2025-02-02'),
(42, 'Ricardo Tapetillo',               'Ricardo Tapetillo',               817, 'PLT',     NULL, 1, '2025-02-03'),
(43, 'Salvador',                        'Salvador',                        622, 'PIT',     NULL, 1, '2025-02-04'),
(44, 'Saúl Jaramillo Andrade',          'Saúl Jaramillo Andrade',          973, 'PLT',     NULL, 1, '2025-02-06'),
(45, 'Sergio',                          'Sergio',                          832, 'PLT',     NULL, 1, '2025-02-07'),
(46, 'Uriel Andrés',                    'Uriel Andrés',                    843, 'PLT',     NULL, 1, '2025-02-09'),
(47, 'William',                         'William',                         776, 'PLT/PIT', NULL, 1, '2025-02-11'),
(48, 'Mario',                           'Mario',                           257, 'PLT',     NULL, 1, '2025-02-12'),
(49, 'Luis Armando Galicia Toralex',    'Luis Armando Galicia Toralex',    336, 'PLT',     NULL, 1, '2025-02-13'),
(50, 'Eduardo',                         'Eduardo',                         337, 'PLT',     NULL, 1, '2025-02-14'),
(51, 'Everardo Muñoz',                  'Everardo Muñoz',                  344, 'PLT',     NULL, 1, '2025-02-16'),
(52, 'Óscar Carranza',                  'Óscar Carranza',                  353, 'PLT',     NULL, 1, '2025-02-17'),
(53, 'Hugo Noé',                        'Hugo Noé',                        355, 'PLT',     NULL, 1, '2025-02-18'),
(54, 'Hugo (355)',                      'Hugo',                            355, 'PLT',     NULL, 1, '2025-02-19'),
(55, 'Antonio',                         'Antonio',                         372, 'PLT',     NULL, 1, '2025-02-21'),
(56, 'Edgar',                           'Edgar',                           381, 'PLT',     NULL, 1, '2025-02-22'),
(57, 'Felipe (417)',                    'Felipe',                          417, 'PLT',     NULL, 1, '2025-02-23'),
(58, 'Vicente Yahir Domínguez',         'Vicente Yahir Domínguez',         428, 'PLT',     NULL, 1, '2025-02-24'),
(59, 'Jesús',                           'Jesús',                           437, 'PLT',     NULL, 1, '2025-02-25'),
(60, 'Ismael Bernal',                   'Ismael Bernal',                   462, 'PLT',     NULL, 1, '2025-02-26'),
(61, 'Luis Íñiguez',                    'Luis Íñiguez',                    473, 'PLT',     NULL, 1, '2025-02-27'),
(62, 'Rubén',                           'Rubén',                           475, 'PLT',     NULL, 1, '2025-02-28'),
(63, 'Iván Díaz',                       'Iván Díaz',                       487, 'PLT',     NULL, 1, '2025-03-02'),
(64, 'Cervando Leos',                   'Cervando Leos',                   578, 'PLT',     NULL, 1, '2025-03-03'),
(65, 'Benjamín (578)',                  'Benjamín',                        578, 'PLT',     NULL, 1, '2025-03-04'),
(66, 'Miguel Ortiz Méndez',             'Miguel Ortiz Méndez',             584, 'PLT',     NULL, 1, '2025-03-05'),
(67, 'Jaime',                           'Jaime',                           682, 'PLT',     NULL, 1, '2025-03-06'),
(68, 'Molina',                          'Molina',                          754, 'PLT',     NULL, 1, '2025-03-07'),
(69, 'Daniel',                          'Daniel',                          772, 'PLT',     NULL, 1, '2025-03-08'),
(70, 'Carlos Anguiano',                 'Carlos Anguiano',                 777, 'PLT',     NULL, 1, '2025-03-09'),
(71, 'Julio (828)',                     'Julio',                           828, 'PLT',     NULL, 1, '2025-03-10'),
(72, 'José Luis Tamayo',                'José Luis Tamayo',                366, 'TLL',     'Montador', 1, '2024-09-01'),
(73, 'Valentín Machuca',                'Valentín Machuca',                421, 'TLL',     'Aseo', 1, '2024-10-01'),
(74, 'Jonathan Valderra Reyes',         'Jonathan Valderra Reyes',         424, 'TLL',     'Burbuja', 1, '2024-11-15'),
(75, 'Salvador Preciado Gutiérrez',     'Salvador Preciado Gutiérrez',     528, 'TLL',     'Ventana', 1, '2024-12-10'),
(76, 'Benjamín Ezequiel Ramos Hernández','Benjamín Ezequiel Ramos Hernández',578,'TLL',   'Detallador', 1, '2025-01-02'),
(77, 'Víctor Flores Gámez',             'Víctor Flores Gámez',             584, 'TLL',     'Rayador', 1, '2025-01-15'),
(78, 'Óscar Eduardo Razo Valadez',      'Óscar Eduardo Razo Valadez',      616, 'TLL',     'Burbuja', 1, '2025-02-01'),
(79, 'José Román Flores Flores',        'José Román Flores Flores',        657, 'TLL',     'Ventana', 1, '2024-11-20'),
(80, 'Nemecio Rincón Martínez',         'Nemecio Rincón Martínez',         884, 'TLL',     'Montador', 1, '2024-10-20'),
(81, 'Marco Antonio López Aguilera',    'Marco Antonio López Aguilera',    882, 'TLL',     'Montador', 1, '2024-12-05'),
(82, 'Carlos Francisco Trinidad',       'Carlos Francisco Trinidad',       1067,'TLL',     'Detallador', 1, '2025-01-10'),
(83, 'Ricardo Vargas Hernández',        'Ricardo Vargas Hernández',        741, 'TLL',     'Rayador', 1, '2025-02-10'),
(84, 'Gerónimo Cruz Cabrera',           'Gerónimo Cruz Cabrera',           455, 'TLL',     'Torcedor', 1, '2024-09-15'),
(85, 'Martín Sánchez Serio',            'Martín Sánchez Serio',            854, 'TLL',     'Torcedor', 1, '2024-10-05'),
(86, 'José Luis Carrillo',              'José Luis Carrillo',              862, 'TLL',     'Torcedor', 1, '2024-11-01'),
(87, 'José Moisés Martínez Juárez',     'José Moisés Martínez Juárez',     644, 'TLL',     'Torcedor', 1, '2025-01-05');

ALTER TABLE trabajadores AUTO_INCREMENT = 88;

-- ----- semanas de ejemplo -----
INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas) VALUES
('02-05', '2026-05-02', '2026-05-08', 2026, 'Ejemplo mayo'),
('16-05', '2026-05-16', '2026-05-22', 2026, 'Ejemplo mayo'),
('30-05', '2026-05-30', '2026-06-05', 2026, 'Ejemplo mayo'),
('18-07', '2026-07-18', '2026-07-24', 2026, 'Parcial julio');

-- ----- resumen_nominas de ejemplo -----
INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas) VALUES
(1, 25145.00,  9715.00, 29344.40, 'Ejemplo'),
(2, 21771.90, 15102.00, 33504.40, 'Ejemplo'),
(3, 25145.00, 15151.00, 27379.46, 'Ejemplo'),
(4, NULL,     10341.00, 27806.00, 'Parcial');

-- ============================================================
-- VISTAS ÚTILES
-- ============================================================

CREATE OR REPLACE VIEW v_trabajadores_plt_activos AS
SELECT id, nombre_mostrar, nombre_completo, ubic, tipo, fecha_incorporacion
FROM trabajadores
WHERE activo = 1
  AND (tipo = 'PLT' OR tipo = 'PLT/PIT' OR tipo = 'Mixto')
ORDER BY nombre_mostrar, ubic;

CREATE OR REPLACE VIEW v_resumen_produccion_semana AS
SELECT
  s.codigo,
  s.fecha_inicio,
  s.fecha_fin,
  COUNT(p.id)                    AS lineas,
  SUM(p.total_gramos)            AS total_gramos,
  SUM(p.efectivo)                AS total_efectivo
FROM semanas s
LEFT JOIN produccion_plata p ON p.semana_id = s.id
GROUP BY s.id, s.codigo, s.fecha_inicio, s.fecha_fin;

-- ============================================================
-- FIN
-- ============================================================
SELECT 'Tablas creadas correctamente en fajos_central' AS mensaje;
