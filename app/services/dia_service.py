"""Cierre de día, avisos y suministro."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.core.dias import DAY_LABELS, col_hoy, valor_gramos
from app.core.calendar_util import encontrar_semana_actual, sugerir_codigo_semana, today
from app.db.connection import Database, get_db
from app.db.repository import SemanasRepo, TrabajosRepo
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class DiaService:
    def __init__(self, db: Database | None = None):
        self.db = db or get_db()

    def ensure_cierre_table(self) -> None:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS cierre_dia (
                      id INT UNSIGNED NOT NULL AUTO_INCREMENT,
                      fecha DATE NOT NULL,
                      semana_id INT UNSIGNED DEFAULT NULL,
                      campo_dia VARCHAR(16) NOT NULL,
                      trabajos_total INT NOT NULL DEFAULT 0,
                      trabajos_sin_gramos INT NOT NULL DEFAULT 0,
                      total_gramos DECIMAL(12,2) DEFAULT 0,
                      total_efectivo DECIMAL(12,2) DEFAULT 0,
                      resumen_json MEDIUMTEXT,
                      cerrado_por VARCHAR(80) DEFAULT NULL,
                      creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                      PRIMARY KEY (id),
                      UNIQUE KEY uk_fecha (fecha)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """
                )
        except Exception as e:
            logger.warning("ensure cierre_dia: %s", e)

    def estado_hoy(self, ref: date | None = None) -> dict[str, Any]:
        ref = ref or today()
        try:
            self.ensure_cierre_table()
        except Exception:
            pass
        col = col_hoy(ref)
        sem_repo = SemanasRepo(self.db)
        semanas = sem_repo.listar()
        actual = encontrar_semana_actual(semanas, ref)
        trabajos = []
        if actual:
            trabajos = TrabajosRepo(self.db).listar_con_semana(int(actual["id"]), solo_activos=True)
        sin = [t for t in trabajos if valor_gramos(t, col) <= 0]
        gr = sum(valor_gramos(t, col) for t in trabajos)
        ef = 0.0
        for t in trabajos:
            g = valor_gramos(t, col)
            try:
                ef += g * float(t.get("tarifa_gr") or 0)
            except (TypeError, ValueError):
                pass
        cerrado = self.esta_cerrado(ref)
        return {
            "fecha": ref.isoformat(),
            "campo_dia": col,
            "label_dia": DAY_LABELS.get(col, col),
            "semana": actual,
            "semana_existe": actual is not None,
            "trabajos_total": len(trabajos),
            "trabajos_sin_gramos": len(sin),
            "faltantes": [
                {
                    "nombre": t.get("nombre"),
                    "ubic": t.get("ubic"),
                    "folio": t.get("folio"),
                    "modelo": t.get("modelo"),
                }
                for t in sin[:50]
            ],
            "total_gramos_hoy": round(gr, 2),
            "total_efectivo_hoy": round(ef, 2),
            "cerrado": cerrado,
            "trabajos": trabajos,
        }

    def esta_cerrado(self, ref: date | None = None) -> bool:
        ref = ref or today()
        try:
            self.ensure_cierre_table()
            with self.db.cursor() as cur:
                cur.execute("SELECT id FROM cierre_dia WHERE fecha = %s", (ref.isoformat(),))
                return cur.fetchone() is not None
        except Exception as e:
            logger.debug("esta_cerrado: %s", e)
            return False

    def cerrar_hoy(self, ref: date | None = None, usuario: str | None = "app") -> dict:
        self.ensure_cierre_table()
        st = self.estado_hoy(ref)
        ref = ref or today()
        payload = {
            "faltantes": st["faltantes"],
            "label_dia": st["label_dia"],
        }
        with self.db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO cierre_dia
                  (fecha, semana_id, campo_dia, trabajos_total, trabajos_sin_gramos,
                   total_gramos, total_efectivo, resumen_json, cerrado_por)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                  trabajos_total=VALUES(trabajos_total),
                  trabajos_sin_gramos=VALUES(trabajos_sin_gramos),
                  total_gramos=VALUES(total_gramos),
                  total_efectivo=VALUES(total_efectivo),
                  resumen_json=VALUES(resumen_json),
                  cerrado_por=VALUES(cerrado_por)
                """,
                (
                    ref.isoformat(),
                    st["semana"]["id"] if st["semana"] else None,
                    st["campo_dia"],
                    st["trabajos_total"],
                    st["trabajos_sin_gramos"],
                    st["total_gramos_hoy"],
                    st["total_efectivo_hoy"],
                    json.dumps(payload, ensure_ascii=False),
                    usuario,
                ),
            )
        st["cerrado"] = True
        return st

    def avisos_apertura(self) -> list[str]:
        msgs = []
        st = self.estado_hoy()
        if not st["semana_existe"]:
            cod, sab, vie = sugerir_codigo_semana()
            msgs.append(
                f"No hay semana creada para hoy. Sugerida: {cod} ({sab} → {vie}). "
                "Usa «★ Semana actual»."
            )
        if st["semana_existe"] and st["trabajos_total"] and st["trabajos_sin_gramos"]:
            msgs.append(
                f"Hay {st['trabajos_sin_gramos']} de {st['trabajos_total']} trabajos "
                f"sin gramos de {st['label_dia']}."
            )
        if st["cerrado"]:
            msgs.append(f"El día {st['fecha']} ya está cerrado.")
        return msgs


def siguiente_rango_semana(fecha_fin: date) -> tuple[str, date, date]:
    """Compat: delega en calendar_util (normaliza sáb–vie)."""
    from app.core.calendar_util import siguiente_rango_semana as _sr
    return _sr(fecha_fin)
