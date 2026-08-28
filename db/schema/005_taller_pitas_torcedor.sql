-- Pitas para Torcedores en nómina de taller (pago = pitas × precio)
-- Precio típico: 3.20 por pita
ALTER TABLE nomina_taller
  ADD COLUMN IF NOT EXISTS pitas DECIMAL(12,2) NULL DEFAULT NULL AFTER extras,
  ADD COLUMN IF NOT EXISTS precio_pita DECIMAL(12,4) NULL DEFAULT 3.2000 AFTER pitas;
