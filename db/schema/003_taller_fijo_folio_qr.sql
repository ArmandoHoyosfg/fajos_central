-- v3.17: sueldo fijo/variable (taller), fin de folio, base para QR
-- Ejecutar en HeidiSQL sobre fajos_central (idempotente donde sea posible).

-- Trabajadores: modo de sueldo (solo aplica a TLL; otros lo ignoran)
SET @col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'trabajadores' AND COLUMN_NAME = 'sueldo_modo'
);
SET @sql := IF(@col = 0,
  'ALTER TABLE trabajadores ADD COLUMN sueldo_modo ENUM(''fijo'',''variable'') NOT NULL DEFAULT ''variable'' AFTER puesto',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SET @col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'trabajadores' AND COLUMN_NAME = 'sueldo_base'
);
SET @sql := IF(@col = 0,
  'ALTER TABLE trabajadores ADD COLUMN sueldo_base DECIMAL(12,2) NULL DEFAULT NULL AFTER sueldo_modo',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Trabajos: fecha de cierre del folio
SET @col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'trabajajos' AND COLUMN_NAME = 'terminado_en'
);
SET @sql := IF(@col = 0,
  'ALTER TABLE trabajos ADD COLUMN terminado_en TIMESTAMP NULL DEFAULT NULL AFTER activo',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Código estable para QR (opcional; si NULL se usa id)
SET @col := (
  SELECT COUNT(*) FROM information_schema.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'trabajadores' AND COLUMN_NAME = 'codigo_qr'
);
SET @sql := IF(@col = 0,
  'ALTER TABLE trabajadores ADD COLUMN codigo_qr VARCHAR(32) NULL DEFAULT NULL AFTER notas',
  'SELECT 1');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- Rellenar codigo_qr para existentes
UPDATE trabajadores SET codigo_qr = CONCAT('FC', LPAD(id, 6, '0'))
WHERE codigo_qr IS NULL OR codigo_qr = '';

-- Taller por defecto: si tienen puesto típico de sueldo fijo, el usuario ajusta;
-- no asumimos fijos automáticamente.
