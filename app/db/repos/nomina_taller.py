"""Repositorio: NominaTallerRepo."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Optional

from app.core.exceptions import DatabaseError, NotFoundError, ValidationAppError
from app.core.logging_config import get_logger
from app.db.connection import Database, get_db
from app.db.repos.base import BaseRepo, _parse_fecha_sql

logger = get_logger(__name__)

class NominaTallerRepo(BaseRepo):
    """Nómina de taller: sueldo + extras. Torcedores: pago = pitas × precio_pita (defecto 3.2)."""

    PRECIO_PITA_DEFAULT = 3.2

    @classmethod
    def precio_pita_default(cls) -> float:
        """Catálogo PITA → historial PITA/torcedor → 3.20. Siempre editable en UI."""
        # 1) Catálogo materiales
        try:
            from app.db.repository import CatalogosRepo
            mats = CatalogosRepo().listar_materiales(solo_activos=True) or []
            for m in mats:
                nom = str(m.get("material") or "").strip().upper()
                if nom == "PITA":
                    t = m.get("tarifa_por_gramo")
                    if t is None:
                        t = m.get("tarifa_gr")
                    if t is not None and float(t) > 0:
                        return float(t)
        except Exception:
            pass
        # 2) Historial
        try:
            from app.db.repository import HistorialPreciosRepo
            sug = HistorialPreciosRepo().sugerir("PITA", "torcedor")
            if sug is not None and float(sug) > 0:
                return float(sug)
            sug = HistorialPreciosRepo().sugerir("PITA", None)
            if sug is not None and float(sug) > 0:
                return float(sug)
        except Exception:
            pass
        return float(cls.PRECIO_PITA_DEFAULT)

    @staticmethod
    def es_torcedor(puesto: str | None) -> bool:
        p = (puesto or "").strip().lower()
        return "torcedor" in p

    def listar_por_semana(self, semana_id: int, **_kwargs) -> list[dict]:
        with self.db.cursor() as cur:
            rows = []
            try:
                cur.execute(
                    """
                    SELECT n.id, n.semana_id, n.trabajador_id,
                           COALESCE(tr.nombre_mostrar, n.nombre) AS nombre,
                           COALESCE(tr.ubic, n.ubic) AS ubic,
                           COALESCE(tr.puesto, n.puesto) AS puesto,
                           n.sueldo, n.extras, n.total, n.firmado, n.notas,
                           n.pitas, n.precio_pita,
                           COALESCE(tr.sueldo_modo, 'variable') AS sueldo_modo,
                           tr.sueldo_base
                    FROM nomina_taller n
                    LEFT JOIN trabajadores tr ON (
                        (n.trabajador_id IS NOT NULL AND tr.id = n.trabajador_id)
                        OR (
                            (n.trabajador_id IS NULL OR n.trabajador_id = 0)
                            AND tr.nombre_mostrar = n.nombre
                            AND tr.ubic = n.ubic
                        )
                    )
                    WHERE n.semana_id = %s
                    ORDER BY
                      CASE WHEN LOWER(COALESCE(tr.puesto, n.puesto, '')) LIKE '%%torcedor%%' THEN 1 ELSE 0 END,
                      COALESCE(tr.ubic, n.ubic),
                      COALESCE(tr.nombre_mostrar, n.nombre)
                    """,
                    (semana_id,),
                )
                rows = list(cur.fetchall() or [])
            except Exception:
                cur.execute(
                    """
                    SELECT id, semana_id, trabajador_id, nombre, ubic, puesto,
                           sueldo, extras, total, firmado, notas
                    FROM nomina_taller
                    WHERE semana_id = %s
                    ORDER BY ubic, nombre
                    """,
                    (semana_id,),
                )
                rows = list(cur.fetchall() or [])
            return self._enriquecer_taller_lineas(rows)


    def _enriquecer_taller_lineas(self, rows: list[dict]) -> list[dict]:
        """
        Asegura sueldo_modo/sueldo_base desde el catálogo.
        Si falta trabajador_id, intenta enlazar por nombre + ubic y lo guarda.
        """
        if not rows:
            return rows
        # índice de trabajadores
        by_id: dict[int, dict] = {}
        by_key: dict[tuple, dict] = {}
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, nombre_mostrar, ubic, puesto, sueldo_modo, sueldo_base, tipo, activo
                    FROM trabajadores
                    """
                )
                for t in cur.fetchall() or []:
                    by_id[int(t["id"])] = t
                    k = (
                        str(t.get("nombre_mostrar") or "").strip().lower(),
                        int(t.get("ubic") or 0),
                    )
                    by_key[k] = t
        except Exception:
            pass

        for r in rows:
            tid = r.get("trabajador_id")
            t = by_id.get(int(tid)) if tid is not None else None
            if t is None:
                k = (
                    str(r.get("nombre") or "").strip().lower(),
                    int(r.get("ubic") or 0),
                )
                t = by_key.get(k)
                if t is not None:
                    r["trabajador_id"] = int(t["id"])
                    # backfill silencioso
                    try:
                        with self.db.cursor() as cur:
                            cur.execute(
                                "UPDATE nomina_taller SET trabajador_id=%s WHERE id=%s AND (trabajador_id IS NULL OR trabajador_id=0)",
                                (int(t["id"]), int(r["id"])),
                            )
                    except Exception:
                        pass
            if t is not None:
                modo = str(t.get("sueldo_modo") or "variable").strip().lower()
                r["sueldo_modo"] = "fijo" if modo == "fijo" else "variable"
                r["sueldo_base"] = t.get("sueldo_base")
                if not r.get("puesto") and t.get("puesto"):
                    r["puesto"] = t.get("puesto")
            else:
                modo = str(r.get("sueldo_modo") or "variable").strip().lower()
                r["sueldo_modo"] = "fijo" if modo == "fijo" else "variable"
                r.setdefault("sueldo_base", None)
            r.setdefault("pitas", None)
            r.setdefault("precio_pita", self.precio_pita_default())
            r["es_torcedor"] = self.es_torcedor(r.get("puesto"))
            # Fijo: si sueldo en 0, aplicar base del catálogo (memoria + BD)
            try:
                if r["sueldo_modo"] == "fijo" and r.get("sueldo_base") is not None:
                    base_f = float(r["sueldo_base"])
                    cur_sueldo = float(r.get("sueldo") or 0)
                    if cur_sueldo == 0 and base_f > 0:
                        r["sueldo"] = base_f
                        extras = float(r.get("extras") or 0)
                        r["total"] = base_f + extras
                        r["sueldo_sugerido"] = base_f
                        try:
                            with self.db.cursor() as cur:
                                cur.execute(
                                    """
                                    UPDATE nomina_taller
                                       SET sueldo = %s,
                                           total = %s + COALESCE(extras, 0)
                                     WHERE id = %s
                                       AND COALESCE(firmado, 0) = 0
                                       AND COALESCE(sueldo, 0) = 0
                                    """,
                                    (base_f, base_f, int(r["id"])),
                                )
                        except Exception:
                            pass
            except (TypeError, ValueError):
                pass
        return rows

    def totales(self, semana_id: int) -> dict:
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS lineas,
                       COALESCE(SUM(sueldo),0) AS sum_sueldo,
                       COALESCE(SUM(extras),0) AS sum_extras,
                       COALESCE(SUM(total),0) AS total
                FROM nomina_taller WHERE semana_id = %s
                """,
                (semana_id,),
            )
            return cur.fetchone() or {}

    def _calc_torcedor(self, data: dict, *, forzar: bool = False) -> dict:
        """Sueldo torcedor = pitas × precio (defecto $3.20).

        *forzar*: True cuando el usuario edita pitas (aunque puesto en nomina_taller
        esté vacío y el puesto real venga del catálogo de trabajadores).
        """
        if "pitas" not in data:
            return data
        puesto = data.get("puesto")
        if not forzar and not self.es_torcedor(str(puesto) if puesto is not None else None):
            return data
        try:
            raw = data.get("pitas")
            if raw is None or str(raw).strip() == "":
                return data
            pitas = float(raw)
        except (TypeError, ValueError):
            return data
        precio = data.get("precio_pita")
        try:
            precio = float(precio) if precio is not None and str(precio).strip() != "" else self.precio_pita_default()
        except (TypeError, ValueError):
            precio = self.precio_pita_default()
        data = dict(data)
        data["precio_pita"] = precio
        data["sueldo"] = round(pitas * precio, 2)
        return data

    def _resolve_trabajador_id(self, data: dict) -> dict:
        if data.get("trabajador_id"):
            return data
        nombre = str(data.get("nombre") or "").strip()
        ubic = data.get("ubic")
        if not nombre or ubic is None:
            return data
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT id, sueldo_modo, sueldo_base, puesto FROM trabajadores WHERE nombre_mostrar=%s AND ubic=%s LIMIT 1",
                    (nombre, int(ubic)),
                )
                t = cur.fetchone()
                if t:
                    data = dict(data)
                    data["trabajador_id"] = int(t["id"])
                    if not data.get("puesto") and t.get("puesto"):
                        data["puesto"] = t.get("puesto")
                    if data.get("sueldo") in (None, "", 0, 0.0) and str(t.get("sueldo_modo") or "").lower() == "fijo" and t.get("sueldo_base") is not None:
                        data["sueldo"] = float(t["sueldo_base"])
        except Exception:
            pass
        return data

    def insertar(self, semana_id: int, data: dict) -> int:
        data = self._resolve_trabajador_id(dict(data))
        data = self._calc_torcedor(data, forzar=bool(data.get('pitas') is not None))
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO nomina_taller
                      (semana_id, trabajador_id, nombre, ubic, puesto, sueldo, extras, pitas, precio_pita, firmado, notas)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        semana_id,
                        data.get("trabajador_id"),
                        data["nombre"],
                        data["ubic"],
                        data.get("puesto"),
                        float(data.get("sueldo") or 0),
                        float(data.get("extras") or 0),
                        data.get("pitas"),
                        data.get("precio_pita") or self.precio_pita_default(),
                        1 if data.get("firmado") else 0,
                        data.get("notas"),
                    ),
                )
            except Exception:
                cur.execute(
                    """
                    INSERT INTO nomina_taller
                      (semana_id, trabajador_id, nombre, ubic, puesto, sueldo, extras, firmado, notas)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        semana_id,
                        data.get("trabajador_id"),
                        data["nombre"],
                        data["ubic"],
                        data.get("puesto"),
                        float(data.get("sueldo") or 0),
                        float(data.get("extras") or 0),
                        1 if data.get("firmado") else 0,
                        data.get("notas"),
                    ),
                )
            return cur.lastrowid

    def obtener(self, row_id: int) -> dict | None:
        """Fila de nómina; puesto efectivo = fila o catálogo de trabajadores."""
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT n.id, n.semana_id, n.trabajador_id, n.nombre, n.ubic,
                           COALESCE(tr.puesto, n.puesto) AS puesto,
                           n.puesto AS puesto_fila,
                           n.sueldo, n.extras, n.total, n.firmado, n.notas,
                           n.pitas, n.precio_pita
                    FROM nomina_taller n
                    LEFT JOIN trabajadores tr ON (
                        (n.trabajador_id IS NOT NULL AND tr.id = n.trabajador_id)
                        OR (
                            (n.trabajador_id IS NULL OR n.trabajador_id = 0)
                            AND tr.nombre_mostrar = n.nombre AND tr.ubic = n.ubic
                        )
                    )
                    WHERE n.id=%s
                    LIMIT 1
                    """,
                    (row_id,),
                )
                row = cur.fetchone()
                if row:
                    return row
            except Exception:
                pass
            try:
                cur.execute(
                    """
                    SELECT id, semana_id, trabajador_id, nombre, ubic, puesto,
                           sueldo, extras, total, firmado, notas, pitas, precio_pita
                    FROM nomina_taller WHERE id=%s
                    """,
                    (row_id,),
                )
            except Exception:
                cur.execute(
                    """
                    SELECT id, semana_id, trabajador_id, nombre, ubic, puesto,
                           sueldo, extras, total, firmado, notas
                    FROM nomina_taller WHERE id=%s
                    """,
                    (row_id,),
                )
            return cur.fetchone()

    def actualizar(self, row_id: int, data: dict) -> None:
        """Actualiza campos. Si llegan pitas → sueldo = pitas × precio (def. 3.2)."""
        data = dict(data)
        forzar_pita = "pitas" in data or "precio_pita" in data
        if forzar_pita:
            cur_row = self.obtener(row_id) or {}
            if "puesto" not in data or not data.get("puesto"):
                data["puesto"] = cur_row.get("puesto")
            if "precio_pita" not in data or data.get("precio_pita") is None:
                data["precio_pita"] = cur_row.get("precio_pita") or self.precio_pita_default()
            if "pitas" not in data and cur_row.get("pitas") is not None:
                data["pitas"] = cur_row.get("pitas")
            # Si el puesto efectivo es torcedor O el usuario edita pitas en una fila
            # que ya es de torcedor en catálogo, forzar cálculo.
            forzar = self.es_torcedor(str(data.get("puesto") or "")) or forzar_pita
            data = self._calc_torcedor(data, forzar=forzar)
        else:
            data = self._calc_torcedor(data, forzar=False)
        fields = []
        params: list = []
        for k in ("nombre", "ubic", "puesto", "sueldo", "extras", "pitas", "precio_pita", "firmado", "notas", "trabajador_id"):
            if k in data:
                fields.append(f"{k}=%s")
                params.append(data[k])
        if not fields:
            return
        params.append(row_id)
        with self.db.cursor() as cur:
            try:
                cur.execute(f"UPDATE nomina_taller SET {', '.join(fields)} WHERE id=%s", params)
            except Exception:
                # sin columnas pitas (migración pendiente)
                fields2, params2 = [], []
                for k in ("nombre", "ubic", "puesto", "sueldo", "extras", "firmado", "notas", "trabajador_id"):
                    if k in data:
                        fields2.append(f"{k}=%s")
                        params2.append(data[k])
                if not fields2:
                    return
                params2.append(row_id)
                cur.execute(f"UPDATE nomina_taller SET {', '.join(fields2)} WHERE id=%s", params2)

    def eliminar(self, row_id: int) -> None:
        with self.db.cursor() as cur:
            cur.execute("DELETE FROM nomina_taller WHERE id=%s", (row_id,))


