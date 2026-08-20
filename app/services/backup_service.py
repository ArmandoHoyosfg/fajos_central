"""Copias de seguridad al exportar formal."""
from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from app.core.config import BASE_DIR
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BackupService:
    def __init__(self, exports_dir: Path | None = None):
        self.exports_dir = exports_dir or (BASE_DIR / "exports")
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def guardar_export(
        self,
        origen: Path | bytes,
        *,
        codigo_semana: str = "",
        extension: str = ".xlsx",
        prefijo: str = "formal",
    ) -> Path:
        """
        Guarda una copia fechada en exports/.
        Si origen es Path, copia el archivo; si es bytes, escribe el contenido.
        """
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cod = (codigo_semana or "semana").replace(" ", "_")
        name = f"{prefijo}_{cod}_{stamp}{extension}"
        dest = self.exports_dir / name
        if isinstance(origen, (bytes, bytearray)):
            dest.write_bytes(origen)
        else:
            shutil.copy2(Path(origen), dest)
        logger.info("Backup export → %s", dest)
        return dest
