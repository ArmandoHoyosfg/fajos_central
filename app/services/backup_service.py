"""Copias de seguridad al exportar formal y al cerrar el launcher."""
from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import BASE_DIR
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BackupService:
    def __init__(self, exports_dir: Path | None = None):
        self.exports_dir = exports_dir or (BASE_DIR / "exports")
        self.backup_dir = BASE_DIR / "backups"
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def guardar_export(
        self,
        origen: Path | bytes,
        *,
        codigo_semana: str = "",
        extension: str = ".xlsx",
        prefijo: str = "formal",
    ) -> Path:
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

    def backup_cierre(
        self,
        *,
        incluir_master: bool = True,
        db_cfg: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Backup al cerrar el launcher:
        - Copia config.ini (sin log)
        - Excel Master de la BD (si posible)
        - mysqldump si el cliente está en PATH (opcional)
        """
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = self.backup_dir / f"cierre_{stamp}"
        folder.mkdir(parents=True, exist_ok=True)
        result: dict[str, Any] = {"ok": True, "folder": str(folder), "files": [], "errors": []}

        # config.ini
        cfg = BASE_DIR / "config.ini"
        if cfg.exists():
            dest = folder / "config.ini"
            shutil.copy2(cfg, dest)
            result["files"].append(str(dest.name))

        # meta
        meta = {
            "stamp": stamp,
            "base_dir": str(BASE_DIR),
        }
        (folder / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        result["files"].append("meta.json")

        # Master Excel
        if incluir_master:
            try:
                from app.services.export_service import ExportService

                content, _mt, fname = ExportService().export_master()
                path = folder / (fname if fname.endswith(".xlsx") else f"master_{stamp}.xlsx")
                path.write_bytes(content)
                result["files"].append(path.name)
            except Exception as e:
                logger.warning("Backup master falló: %s", e)
                result["errors"].append(f"master: {e}")

        # mysqldump opcional
        if db_cfg:
            try:
                dump = self._try_mysqldump(folder, db_cfg, stamp)
                if dump:
                    result["files"].append(dump.name)
            except Exception as e:
                logger.warning("mysqldump: %s", e)
                result["errors"].append(f"mysqldump: {e}")

        result["ok"] = len(result["files"]) > 0
        logger.info("Backup cierre → %s (%s archivos)", folder, len(result["files"]))
        return result

    def _try_mysqldump(
        self, folder: Path, db_cfg: dict[str, Any], stamp: str
    ) -> Path | None:
        host = str(db_cfg.get("host") or "localhost")
        port = str(db_cfg.get("port") or 3306)
        user = str(db_cfg.get("user") or "root")
        password = str(db_cfg.get("password") or "")
        database = str(db_cfg.get("database") or "fajos_central")
        out = folder / f"{database}_{stamp}.sql"
        cmd = [
            "mysqldump",
            f"-h{host}",
            f"-P{port}",
            f"-u{user}",
            database,
            "--single-transaction",
            "--routines",
            "--events",
        ]
        env = None
        # Preferir archivo temporal de defaults para no exponer password en process list si es posible
        # Simplicidad: MYSQL_PWD (documentado; solo en proceso corto)
        import os

        env = os.environ.copy()
        if password:
            env["MYSQL_PWD"] = password
        try:
            with open(out, "wb") as f:
                r = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    env=env,
                    timeout=120,
                )
            if r.returncode != 0:
                out.unlink(missing_ok=True)
                err = (r.stderr or b"").decode("utf-8", errors="replace")[:300]
                raise RuntimeError(err or f"code {r.returncode}")
            return out
        except FileNotFoundError:
            return None
