"""
Aprendizaje ligero: registra uso, detecta folios inactivos/reasignados
y acumula estadísticas simples (sin ML pesado).
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from app.core.calendar_util import encontrar_semana_actual, parse_db_date, today
from app.core.logging_config import get_logger
from app.db.connection import get_db
from app.db.repository import ProduccionRepo, SemanasRepo, TrabajadoresRepo, TrabajosRepo

logger = get_logger(__name__)


class AprendizajeService:
    def __init__(self, db=None) -> None:
        self.db = db or get_db()
        self.semanas = SemanasRepo(self.db)
        self.prod = ProduccionRepo(self.db)
        self.trab = TrabajadoresRepo(self.db)
        self.trabajos = TrabajosRepo(self.db)

    def registrar(
        self,
        tipo: str,
        *,
        entidad: str | None = None,
        entidad_id: int | None = None,
        semana_id: int | None = None,
        payload: dict | None = None,
        peso: float = 1.0,
    ) -> int | None:
        """Registra evento de aprendizaje; devuelve id del evento si es posible."""
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO aprendizaje_eventos
                      (tipo, entidad, entidad_id, semana_id, payload_json, peso)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        tipo[:40],
                        entidad,
                        entidad_id,
                        semana_id,
                        json.dumps(payload, default=str) if payload else None,
                        peso,
                    ),
                )
                eid = getattr(cur, "lastrowid", None)
                try:
                    self.db.connect().commit()
                except Exception:
                    pass
                return int(eid) if eid else None
        except Exception:
            logger.debug("No se pudo registrar aprendizaje (%s)", tipo, exc_info=True)
            return None

    def bump_stat(self, clave: str, valor_num: float | None = None, valor_txt: str | None = None) -> None:
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO aprendizaje_stats (clave, valor_num, valor_txt, muestras)
                    VALUES (%s, %s, %s, 1)
                    ON DUPLICATE KEY UPDATE
                      valor_num = CASE
                        WHEN VALUES(valor_num) IS NULL THEN valor_num
                        WHEN valor_num IS NULL THEN VALUES(valor_num)
                        ELSE (valor_num * muestras + VALUES(valor_num)) / (muestras + 1)
                      END,
                      valor_txt = COALESCE(VALUES(valor_txt), valor_txt),
                      muestras = muestras + 1
                    """,
                    (clave[:80], valor_num, valor_txt),
                )
        except Exception:
            logger.debug("No se pudo bump_stat %s", clave, exc_info=True)

    def _gramos_linea(self, row: dict) -> float:
        try:
            return float(row.get("total_gramos") or 0)
        except (TypeError, ValueError):
            return 0.0


    def detectar_folios_inactivos(self, semana_id: int | None = None) -> list[dict]:
        """
        Folios con 0 g esta semana + cuántas semanas llevan inactivos
        y cuándo fue la última actividad.
        """
        semanas = self.semanas.listar()
        # Orden cronológico descendente por fecha_inicio
        def _fi(s):
            return parse_db_date(s.get("fecha_inicio")) or today()

        semanas_ord = sorted(semanas, key=_fi, reverse=True)
        actual = None
        if semana_id:
            for s in semanas_ord:
                if int(s["id"]) == int(semana_id):
                    actual = s
                    break
        if not actual:
            actual = encontrar_semana_actual(semanas, today())
        if not actual:
            return []

        sid = int(actual["id"])
        lineas = self.prod.listar_por_semana(sid)
        fi_act = _fi(actual)

        # Semanas estrictamente anteriores a la actual (hasta 12)
        anteriores = [
            s for s in semanas_ord
            if int(s["id"]) != sid and _fi(s) < fi_act
        ][:12]

        # Cache de líneas por semana_id
        cache_lineas: dict[int, list] = {sid: lineas}

        def lineas_sem(sem_id: int) -> list:
            if sem_id not in cache_lineas:
                try:
                    cache_lineas[sem_id] = self.prod.listar_por_semana(sem_id)
                except Exception:
                    cache_lineas[sem_id] = []
            return cache_lineas[sem_id]

        def actividad_folio(sem_id: int, folio_key: str) -> dict | None:
            """Primera línea con gramos > 0 de ese folio en la semana."""
            for r in lineas_sem(sem_id):
                f = (r.get("folio") or "").strip().upper()
                if f != folio_key:
                    continue
                g = self._gramos_linea(r)
                if g > 0:
                    return {
                        "nombre": r.get("nombre"),
                        "ubic": r.get("ubic"),
                        "trabajador_id": r.get("trabajador_id"),
                        "gramos": g,
                        "prod_id": r.get("id"),
                    }
            return None

        # Semana inmediatamente anterior (para hint finalizado/reasignación)
        prev = anteriores[0] if anteriores else None
        prev_by_folio: dict[str, list[dict]] = {}
        if prev:
            for r in lineas_sem(int(prev["id"])):
                folio = (r.get("folio") or "").strip()
                if not folio:
                    continue
                g = self._gramos_linea(r)
                if g <= 0:
                    continue
                prev_by_folio.setdefault(folio.upper(), []).append({
                    "nombre": r.get("nombre"),
                    "ubic": r.get("ubic"),
                    "trabajador_id": r.get("trabajador_id"),
                    "gramos": g,
                    "semana": prev.get("codigo"),
                    "prod_id": r.get("id"),
                })

        from app.services.export.helpers import linea_activa

        out: list[dict] = []
        for r in lineas:
            if not linea_activa(r):
                continue
            folio = (r.get("folio") or "").strip()
            if not folio:
                continue
            if self._gramos_linea(r) > 0:
                continue
            key = folio.upper()
            prev_list = prev_by_folio.get(key) or []
            hint = "sin_avance_esta_semana"
            prev_info = prev_list[0] if prev_list else None
            if prev_info:
                tid_now = r.get("trabajador_id")
                tid_prev = prev_info.get("trabajador_id")
                if tid_now and tid_prev:
                    same_person = int(tid_now) == int(tid_prev)
                else:
                    same_person = (
                        str(prev_info.get("nombre") or "").lower()
                        == str(r.get("nombre") or "").lower()
                    )
                hint = "posible_finalizado" if same_person else "posible_reasignacion"

            # Contar semanas consecutivas sin gramos (incluyendo la actual = al menos 1)
            semanas_inactivo = 1
            ultima_act = None  # dict con semana codigo, gramos, nombre
            for s_ant in anteriores:
                act = actividad_folio(int(s_ant["id"]), key)
                if act is None:
                    # ¿Había línea del folio sin gramos o no existía?
                    # Si no hay ninguna fila del folio, dejamos de contar (no estaba asignado)
                    tiene_fila = any(
                        (x.get("folio") or "").strip().upper() == key
                        for x in lineas_sem(int(s_ant["id"]))
                    )
                    if tiene_fila:
                        semanas_inactivo += 1
                        continue
                    break
                ultima_act = {
                    **act,
                    "semana": s_ant.get("codigo"),
                    "semana_id": int(s_ant["id"]),
                }
                break
            else:
                # Se agotó el historial sin encontrar actividad
                if semanas_inactivo > 1:
                    pass  # ultima_act sigue None → "sin registro reciente"

            # Texto legible
            if semanas_inactivo == 1:
                inactivo_txt = "1 semana (solo esta)"
            else:
                inactivo_txt = f"{semanas_inactivo} semanas seguidas"

            if ultima_act:
                g_txt = ultima_act.get("gramos")
                try:
                    g_txt = f"{float(g_txt):.1f}".rstrip("0").rstrip(".")
                except Exception:
                    g_txt = str(g_txt)
                ultima_txt = f"Última act.: sem {ultima_act.get('semana')} · {g_txt} g"
            else:
                ultima_txt = "Sin actividad en historial reciente"

            out.append({
                "prod_id": r.get("id"),
                "folio": folio,
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "trabajador_id": r.get("trabajador_id"),
                "hint": hint,
                "prev": prev_info,
                "semana_id": sid,
                "semanas_inactivo": semanas_inactivo,
                "inactivo_txt": inactivo_txt,
                "ultima_actividad": ultima_act,
                "ultima_txt": ultima_txt,
                "accion_sugerida": (
                    "marcar_terminado" if hint == "posible_finalizado"
                    else "revisar_reasignacion" if hint == "posible_reasignacion"
                    else "revisar"
                ),
            })
        # Más inactivos primero
        out.sort(key=lambda x: (-int(x.get("semanas_inactivo") or 0), str(x.get("folio") or "")))
        return out

    def detectar_reasignaciones(self, semana_id: int | None = None) -> list[dict]:
        """
        Folio con avance esta semana en trabajador B, y la semana previa
        el mismo folio tenía avance en trabajador A (A != B).
        """
        semanas = self.semanas.listar()
        actual = None
        if semana_id:
            for s in semanas:
                if int(s["id"]) == int(semana_id):
                    actual = s
                    break
        if not actual:
            actual = encontrar_semana_actual(semanas, today())
        if not actual:
            return []
        sid = int(actual["id"])
        fi = parse_db_date(actual.get("fecha_inicio"))
        prev = encontrar_semana_actual(semanas, fi - timedelta(days=1)) if fi else None
        if not prev:
            return []

        prev_owners: dict[str, list[dict]] = {}
        for r in self.prod.listar_por_semana(int(prev["id"])):
            folio = (r.get("folio") or "").strip()
            if not folio or self._gramos_linea(r) <= 0:
                continue
            prev_owners.setdefault(folio.upper(), []).append({
                "trabajador_id": r.get("trabajador_id"),
                "nombre": r.get("nombre"),
                "ubic": r.get("ubic"),
                "gramos": self._gramos_linea(r),
                "semana": prev.get("codigo"),
            })

        out = []
        for r in self.prod.listar_por_semana(sid):
            folio = (r.get("folio") or "").strip()
            if not folio or self._gramos_linea(r) <= 0:
                continue
            key = folio.upper()
            prevs = prev_owners.get(key) or []
            tid = r.get("trabajador_id")
            for p in prevs:
                ptid = p.get("trabajador_id")
                if tid and ptid and int(tid) != int(ptid):
                    out.append({
                        "folio": folio,
                        "de": p,
                        "a": {
                            "trabajador_id": tid,
                            "nombre": r.get("nombre"),
                            "ubic": r.get("ubic"),
                            "gramos": self._gramos_linea(r),
                            "prod_id": r.get("id"),
                            "semana": actual.get("codigo"),
                        },
                        "semana_id": sid,
                        "mensaje": (
                            f"El folio {folio} pasó de {p.get('nombre')} (ubic {p.get('ubic')}) "
                            f"a {r.get('nombre')} (ubic {r.get('ubic')})"
                        ),
                    })
                elif not tid or not ptid:
                    # fallback por nombre
                    if str(p.get("nombre") or "").lower() != str(r.get("nombre") or "").lower():
                        out.append({
                            "folio": folio,
                            "de": p,
                            "a": {
                                "trabajador_id": tid,
                                "nombre": r.get("nombre"),
                                "ubic": r.get("ubic"),
                                "gramos": self._gramos_linea(r),
                                "prod_id": r.get("id"),
                                "semana": actual.get("codigo"),
                            },
                            "semana_id": sid,
                            "mensaje": (
                                f"El folio {folio} cambió de persona: "
                                f"{p.get('nombre')} → {r.get('nombre')}"
                            ),
                        })
        return out

    def marcar_folio_terminado(self, prod_id: int | None = None, trabajo_id: int | None = None) -> dict:
        """
        Marca folio como terminado.
        - Siempre marca la línea de producción con [terminado] si hay prod_id
          (así se oculta aunque no exista fila en `trabajos`).
        - Si hay trabajo ligado (o se encuentra por folio), lo desactiva.
        """
        folio = None
        tid = trabajo_id
        trab_id = None
        marked_prod = False
        with self.db.cursor() as cur:
            if not tid and prod_id:
                cur.execute(
                    "SELECT trabajo_id, folio, trabajador_id, notas FROM produccion_plata WHERE id=%s",
                    (prod_id,),
                )
                row = cur.fetchone() or {}
                if not row:
                    return {"ok": False, "error": f"No existe la línea de producción #{prod_id}."}
                tid = row.get("trabajo_id")
                folio = (row.get("folio") or "").strip() or None
                trab_id = row.get("trabajador_id")
                # Buscar trabajo por trabajador+folio
                if not tid and folio and trab_id:
                    try:
                        cur.execute(
                            """
                            SELECT id FROM trabajos
                             WHERE trabajador_id=%s AND folio=%s
                             ORDER BY id DESC LIMIT 1
                            """,
                            (trab_id, folio),
                        )
                        tw = cur.fetchone()
                        if tw:
                            tid = tw["id"]
                            try:
                                cur.execute(
                                    "UPDATE produccion_plata SET trabajo_id=%s WHERE id=%s",
                                    (tid, prod_id),
                                )
                            except Exception:
                                pass
                    except Exception:
                        tid = None
                # Fallback: solo por folio (última coincidencia)
                if not tid and folio:
                    try:
                        cur.execute(
                            """
                            SELECT id FROM trabajos
                             WHERE folio=%s
                             ORDER BY id DESC LIMIT 1
                            """,
                            (folio,),
                        )
                        tw = cur.fetchone()
                        if tw:
                            tid = tw["id"]
                            try:
                                cur.execute(
                                    "UPDATE produccion_plata SET trabajo_id=%s WHERE id=%s",
                                    (tid, prod_id),
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

            if trabajo_id and not folio:
                try:
                    cur.execute("SELECT folio FROM trabajos WHERE id=%s", (trabajo_id,))
                    tw = cur.fetchone() or {}
                    folio = (tw.get("folio") or "").strip() or None
                    tid = trabajo_id
                except Exception:
                    pass

            # 1) Marcar línea(s) de producción
            #    - la indicada
            #    - y cualquier otra de la misma semana con mismo trabajador+folio
            if prod_id:
                try:
                    cur.execute(
                        """
                        SELECT semana_id, trabajador_id, folio, nombre, ubic
                          FROM produccion_plata WHERE id=%s
                        """,
                        (prod_id,),
                    )
                    base = cur.fetchone() or {}
                    cur.execute(
                        """
                        UPDATE produccion_plata
                           SET notas = TRIM(CONCAT(COALESCE(notas,''), ' [terminado]'))
                         WHERE id = %s AND (notas IS NULL OR notas NOT LIKE %s)
                        """,
                        (prod_id, "%[terminado]%"),
                    )
                    marked_prod = True
                    # Hermanas misma semana + mismo folio + mismo trabajador
                    folio_b = (base.get("folio") or "").strip()
                    sid = base.get("semana_id")
                    trab = base.get("trabajador_id")
                    if sid and folio_b:
                        if trab:
                            cur.execute(
                                """
                                UPDATE produccion_plata
                                   SET notas = TRIM(CONCAT(COALESCE(notas,''), ' [terminado]'))
                                 WHERE semana_id=%s AND trabajador_id=%s
                                   AND UPPER(TRIM(folio))=UPPER(%s)
                                   AND id<>%s
                                   AND (notas IS NULL OR notas NOT LIKE %s)
                                """,
                                (sid, trab, folio_b, prod_id, "%[terminado]%"),
                            )
                        else:
                            cur.execute(
                                """
                                UPDATE produccion_plata
                                   SET notas = TRIM(CONCAT(COALESCE(notas,''), ' [terminado]'))
                                 WHERE semana_id=%s
                                   AND UPPER(TRIM(nombre))=UPPER(%s)
                                   AND ubic=%s
                                   AND UPPER(TRIM(folio))=UPPER(%s)
                                   AND id<>%s
                                   AND (notas IS NULL OR notas NOT LIKE %s)
                                """,
                                (
                                    sid,
                                    base.get("nombre") or "",
                                    base.get("ubic"),
                                    folio_b,
                                    prod_id,
                                    "%[terminado]%",
                                ),
                            )
                except Exception as e:
                    return {"ok": False, "error": f"No se pudo marcar la línea: {e}"}

            # 2) Desactivar trabajo si existe
            if tid:
                try:
                    cur.execute(
                        "UPDATE trabajos SET terminado_en = COALESCE(terminado_en, NOW()), activo = 0 WHERE id = %s",
                        (tid,),
                    )
                except Exception:
                    try:
                        cur.execute(
                            "UPDATE trabajos SET terminado_en = COALESCE(terminado_en, NOW()) WHERE id = %s",
                            (tid,),
                        )
                    except Exception:
                        # No bloquear: la línea de producción ya está marcada
                        pass

            if not marked_prod and not tid:
                return {
                    "ok": False,
                    "error": "Indica una línea de producción o un trabajo para terminar.",
                }

        try:
            self.registrar(
                "folio_terminado",
                entidad="trabajo" if tid else "produccion_plata",
                entidad_id=int(tid or prod_id or 0),
                payload={"prod_id": prod_id, "folio": folio, "trabajo_id": tid},
            )
        except Exception:
            pass
        return {
            "ok": True,
            "trabajo_id": tid,
            "folio": folio,
            "prod_id": prod_id,
            "solo_linea": bool(marked_prod and not tid),
        }




    def marcar_folios_terminados_lote(
        self,
        semana_id: int | None = None,
        min_semanas: int = 2,
        prod_ids: list[int] | None = None,
    ) -> dict:
        """
        Termina en lote folios sin avance.
        - Si prod_ids: solo esos.
        - Si no: todos los inactivos con semanas_inactivo >= min_semanas.
        min_semanas por defecto 2 (dos semanas o más sin avance).
        """
        min_semanas = max(1, int(min_semanas or 2))
        inactivos = self.detectar_folios_inactivos(semana_id)
        if prod_ids:
            want = {int(x) for x in prod_ids if x}
            candidatos = [x for x in inactivos if int(x.get("prod_id") or 0) in want]
        else:
            candidatos = [
                x for x in inactivos
                if int(x.get("semanas_inactivo") or 0) >= min_semanas
                and x.get("prod_id")
            ]
        ok, fail = [], []
        for x in candidatos:
            pid = int(x["prod_id"])
            try:
                r = self.marcar_folio_terminado(prod_id=pid)
                if r.get("ok"):
                    ok.append({"prod_id": pid, "folio": x.get("folio") or r.get("folio")})
                else:
                    fail.append({"prod_id": pid, "folio": x.get("folio"), "error": r.get("error")})
            except Exception as e:
                fail.append({"prod_id": pid, "folio": x.get("folio"), "error": str(e)})
        try:
            self.registrar(
                "folio_terminado_lote",
                entidad="produccion_plata",
                semana_id=semana_id,
                payload={"ok": len(ok), "fail": len(fail), "min_semanas": min_semanas},
            )
        except Exception:
            pass
        return {
            "ok": True,
            "terminados": len(ok),
            "fallidos": len(fail),
            "detalle_ok": ok[:50],
            "detalle_fail": fail[:20],
            "min_semanas": min_semanas,
        }

    def reactivar_folio(self, prod_id: int | None = None, trabajo_id: int | None = None) -> dict:
        """Reabre un folio terminado (activo=1, limpia marca en notas)."""
        folio = None
        tid = trabajo_id
        with self.db.cursor() as cur:
            if prod_id:
                cur.execute(
                    "SELECT trabajo_id, folio, notas FROM produccion_plata WHERE id=%s",
                    (prod_id,),
                )
                row = cur.fetchone() or {}
                if not row:
                    return {"ok": False, "error": f"No existe la línea #{prod_id}."}
                if not tid:
                    tid = row.get("trabajo_id")
                folio = (row.get("folio") or "").strip() or None
                # Quitar marca [terminado] de notas
                notas = str(row.get("notas") or "").replace("[terminado]", "").strip()
                try:
                    cur.execute(
                        "UPDATE produccion_plata SET notas = %s WHERE id = %s",
                        (notas or None, prod_id),
                    )
                except Exception as e:
                    return {"ok": False, "error": str(e)}
            if tid:
                try:
                    cur.execute(
                        "UPDATE trabajos SET activo = 1, terminado_en = NULL WHERE id = %s",
                        (tid,),
                    )
                except Exception:
                    pass
            elif not prod_id:
                return {"ok": False, "error": "Indica línea o trabajo a reactivar."}
        try:
            self.registrar(
                "folio_reactivado",
                entidad="trabajo" if tid else "produccion_plata",
                entidad_id=int(tid or prod_id or 0),
                payload={"prod_id": prod_id, "folio": folio},
            )
        except Exception:
            pass
        return {"ok": True, "trabajo_id": tid, "folio": folio, "prod_id": prod_id}


    def purgar_terminados(self, dias: int = 7) -> dict:
        """Elimina trabajos terminados tras N días. Historial de nómina se conserva."""
        dias = max(1, min(int(dias or 7), 90))
        deleted = 0
        with self.db.cursor() as cur:
            try:
                cur.execute(
                    """
                    DELETE FROM trabajos
                     WHERE activo = 0
                       AND terminado_en IS NOT NULL
                       AND terminado_en < (NOW() - INTERVAL %s DAY)
                    """,
                    (dias,),
                )
                deleted = max(0, cur.rowcount or 0)
            except Exception as e:
                logger.warning("purgar_terminados: %s", e)
                return {"ok": False, "error": str(e), "eliminados": 0, "dias": dias}
            try:
                self.db.connect().commit()
            except Exception:
                pass
        if deleted:
            self.registrar(
                "purga_terminados",
                entidad="app",
                payload={"eliminados": deleted, "dias": dias},
            )
        return {"ok": True, "eliminados": deleted, "dias": dias}

    @staticmethod
    def _norm_nombre(s: str) -> str:
        import unicodedata
        s = unicodedata.normalize("NFD", (s or "").strip().lower())
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return " ".join(s.split())

    @classmethod
    def _nombres_similares(cls, a: str, b: str) -> bool:
        """
        Similitud estricta para posibles fichas dobles.
        - Igual normalizado → sí
        - Uno contiene al otro solo si ambos tienen ≥ 2 tokens (evita José vs José Luis Pérez en distinto contexto)
        - Mismo primer token (≥4 letras) + al menos otro token en común
        No empareja solo por nombre de pila genérico (Juan, José, María…).
        """
        na, nb = cls._norm_nombre(a), cls._norm_nombre(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        ta, tb = na.split(), nb.split()
        # Contención solo con nombres compuestos (2+ tokens cada lado o el corto ⊆ largo con 2+ tokens en el largo)
        if na in nb or nb in na:
            corto, largo = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
            if len(largo) >= 2 and len(corto) >= 1:
                # todos los tokens del corto están en el largo
                if set(corto) <= set(largo):
                    return True
            return False
        if not ta or not tb:
            return False
        # Primer nombre genérico corto: no basta por sí solo
        if ta[0] != tb[0] or len(ta[0]) < 4:
            return False
        extra = (set(ta) & set(tb)) - {ta[0]}
        if extra and len(ta) >= 2 and len(tb) >= 2:
            return True
        return False

    @classmethod
    def _ubic_key(cls, ubic) -> str | None:
        """Normaliza ubicación; None si vacía/inválida (sin ubic no se sugiere duplicado)."""
        if ubic is None:
            return None
        s = str(ubic).strip()
        if s == "" or s.lower() in ("none", "null", "-"):
            return None
        try:
            return str(int(float(s)))
        except (TypeError, ValueError):
            return s.lower()

    def _pares_descartados(self, dias: int = 7) -> set[tuple[int, int]]:
        """Pares (id_min, id_max) descartados hace menos de N días."""
        out: set[tuple[int, int]] = set()
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT clave, actualizado_en FROM aprendizaje_stats
                     WHERE clave LIKE 'dup_skip_%%'
                       AND actualizado_en >= (NOW() - INTERVAL %s DAY)
                    """,
                    (max(1, int(dias)),),
                )
                for row in cur.fetchall() or []:
                    k = str(row.get("clave") or "")
                    parts = k.replace("dup_skip_", "").split("_")
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                        out.add((int(parts[0]), int(parts[1])))
        except Exception:
            pass
        return out

    def descartar_duplicado(self, id_a: int, id_b: int, dias: int = 7) -> dict:
        """Oculta la sugerencia de fusión por N días (default 7)."""
        a, b = sorted([int(id_a), int(id_b)])
        if a == b:
            return {"ok": False, "error": "IDs iguales"}
        key = f"dup_skip_{a}_{b}"
        self.bump_stat(key, valor_num=float(dias), valor_txt="descartado")
        self.registrar(
            "dup_descartado",
            entidad="trabajador",
            entidad_id=a,
            payload={"id_a": a, "id_b": b, "dias": dias},
        )
        return {"ok": True, "id_a": a, "id_b": b, "dias": dias}

    def candidatos_duplicados_trabajadores(self) -> list[dict]:
        """
        Posibles fichas dobles (regla de negocio):
        - Misma ubicación (obligatorio)
        - Nombre igual (normalizado) o similar estricto
        Sin ubicación no se sugiere. Distinta ubic = personas distintas.
        Respeta descartes recientes (7 días).
        """
        rows = self.trab.listar(solo_activos=False)
        skipped = self._pares_descartados(7)
        seen_pairs: set[tuple[int, int]] = set()
        cands: list[dict] = []

        def _detalle(group: list) -> list[dict]:
            return [
                {
                    "id": int(g["id"]),
                    "nombre_mostrar": g.get("nombre_mostrar"),
                    "ubic": g.get("ubic"),
                    "tipo": g.get("tipo"),
                    "activo": bool(g.get("activo")),
                }
                for g in group
            ]

        def _pair_ok(ia: int, ib: int) -> bool:
            a, b = (ia, ib) if ia < ib else (ib, ia)
            if a == b:
                return False
            if (a, b) in seen_pairs or (a, b) in skipped:
                return False
            return True

        def _add_pair(motivo: str, label: str, a: dict, b: dict) -> None:
            ia, ib = int(a["id"]), int(b["id"])
            if not _pair_ok(ia, ib):
                return
            lo, hi = (ia, ib) if ia < ib else (ib, ia)
            seen_pairs.add((lo, hi))
            cands.append({
                "nombre": label,
                "motivo": motivo,
                "n": 2,
                "ids": [lo, hi],
                "detalle": _detalle([a, b]),
                "ubic": self._ubic_key(a.get("ubic")),
            })

        # Agrupar por ubicación; solo comparar dentro del mismo grupo
        by_ubic: dict[str, list] = {}
        for r in rows:
            uk = self._ubic_key(r.get("ubic"))
            if uk is None:
                continue
            by_ubic.setdefault(uk, []).append(r)

        for ubic, group in by_ubic.items():
            if len(group) < 2:
                continue
            # 1) mismo nombre exacto (normalizado) en esta ubic
            by_name: dict[str, list] = {}
            for r in group:
                k = self._norm_nombre(r.get("nombre_mostrar") or "")
                if not k:
                    continue
                by_name.setdefault(k, []).append(r)
            for name, g2 in by_name.items():
                if len(g2) < 2:
                    continue
                # pares dentro del grupo (no un mega-grupo de 5 sin revisar descartes)
                for i in range(len(g2)):
                    for j in range(i + 1, len(g2)):
                        a, b = g2[i], g2[j]
                        label = f"{a.get('nombre_mostrar')} · ubic {ubic}"
                        _add_pair("mismo_nombre_misma_ubic", label, a, b)

            # 2) nombres similares (no idénticos) en la misma ubic
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    na = self._norm_nombre(a.get("nombre_mostrar") or "")
                    nb = self._norm_nombre(b.get("nombre_mostrar") or "")
                    if not na or not nb or na == nb:
                        continue  # exactos ya cubiertos arriba
                    if not self._nombres_similares(a.get("nombre_mostrar") or "", b.get("nombre_mostrar") or ""):
                        continue
                    label = (
                        f"{a.get('nombre_mostrar')} / {b.get('nombre_mostrar')} · ubic {ubic}"
                    )
                    _add_pair("similar_misma_ubic", label, a, b)

        return cands



    @staticmethod
    def _score_nombre_completo(row: dict | None) -> tuple[int, int, int]:
        """Más alto = nombre más completo (preferir como ficha que se queda)."""
        if not row:
            return (0, 0, 0)
        nm = (row.get("nombre_mostrar") or "").strip()
        nc = (row.get("nombre_completo") or "").strip()
        best = nc if len(nc) >= len(nm) else nm
        tokens = [x for x in best.split() if x]
        return (len(tokens), len(best), len(nc))

    def _elegir_survivor(self, a: dict, b: dict) -> tuple[dict, dict]:
        """Devuelve (keep_row, merge_row) priorizando nombre más completo; si empate, el activo; si empate, menor id."""
        sa, sb = self._score_nombre_completo(a), self._score_nombre_completo(b)
        if sa > sb:
            return a, b
        if sb > sa:
            return b, a
        act_a = bool(a.get("activo"))
        act_b = bool(b.get("activo"))
        if act_a and not act_b:
            return a, b
        if act_b and not act_a:
            return b, a
        if int(a["id"]) <= int(b["id"]):
            return a, b
        return b, a

    def _mezclar_campos_trabajador(self, keep: dict, other: dict) -> dict:
        """Rellena huecos del survivor con datos del fusionado; nombre = el más completo."""
        out = dict(keep)
        # Nombre: el más completo de ambos
        sk, so = self._score_nombre_completo(keep), self._score_nombre_completo(other)
        if so > sk:
            if (other.get("nombre_mostrar") or "").strip():
                out["nombre_mostrar"] = other["nombre_mostrar"]
            if (other.get("nombre_completo") or "").strip():
                out["nombre_completo"] = other["nombre_completo"]
        else:
            # Completar nombre_completo si keep solo tiene mostrar
            if not (out.get("nombre_completo") or "").strip() and (other.get("nombre_completo") or "").strip():
                out["nombre_completo"] = other["nombre_completo"]
            if not (out.get("nombre_mostrar") or "").strip() and (other.get("nombre_mostrar") or "").strip():
                out["nombre_mostrar"] = other["nombre_mostrar"]
            # Si other tiene más texto en completo, usarlo
            nc_k = (out.get("nombre_completo") or out.get("nombre_mostrar") or "")
            nc_o = (other.get("nombre_completo") or other.get("nombre_mostrar") or "")
            if len(nc_o.strip()) > len(nc_k.strip()):
                if (other.get("nombre_completo") or "").strip():
                    out["nombre_completo"] = other["nombre_completo"]
                if (other.get("nombre_mostrar") or "").strip() and len((other.get("nombre_mostrar") or "")) > len((out.get("nombre_mostrar") or "")):
                    out["nombre_mostrar"] = other["nombre_mostrar"]

        def _fill(key):
            kv, ov = out.get(key), other.get(key)
            empty = kv is None or (isinstance(kv, str) and not str(kv).strip())
            if empty and ov is not None and not (isinstance(ov, str) and not str(ov).strip()):
                out[key] = ov

        for key in (
            "ubic", "tipo", "puesto", "sueldo_modo", "sueldo_base",
            "fecha_incorporacion", "codigo_qr", "notas",
        ):
            _fill(key)
        # tipo: unir flags tipo PLT/PIT/TLL si vienen en texto
        # notas: concatenar referencia al fusionado
        nota_extra = f" [unido desde id {other.get('id')}]"
        notas = (out.get("notas") or "") + nota_extra
        if other.get("notas") and str(other.get("notas")) not in notas:
            notas = (out.get("notas") or "") + " | " + str(other.get("notas")) + nota_extra
        out["notas"] = notas.strip()
        out["activo"] = 1
        return out

    def fusionar_trabajadores(
        self,
        id_keep: int,
        id_merge: int,
        *,
        auto_nombre: bool = True,
    ) -> dict:
        """
        Fusiona dos fichas.
        - Por defecto se queda la de **nombre más completo** (auto_nombre=True),
          aunque el formulario indique otro keep (se intercambian).
        - Mezcla campos vacíos del survivor con datos del fusionado.
        - Guarda snapshot + ids movidos para rollback en DEV.
        """
        if int(id_keep) == int(id_merge):
            return {"ok": False, "error": "ids iguales"}
        keep = self.trab.obtener(id_keep)
        merge = self.trab.obtener(id_merge)
        if not keep or not merge:
            return {"ok": False, "error": "trabajador no encontrado"}

        auto_swapped = False
        if auto_nombre:
            keep, merge = self._elegir_survivor(keep, merge)
            if int(keep["id"]) != int(id_keep):
                auto_swapped = True
            id_keep, id_merge = int(keep["id"]), int(merge["id"])

        snapshot_keep = dict(keep)
        snapshot_merge = dict(merge)
        mezclado = self._mezclar_campos_trabajador(keep, merge)

        moved: dict[str, list[int]] = {"plata": [], "pita": [], "taller": [], "trabajos": []}
        counts = {"plata": 0, "pita": 0, "taller": 0, "trabajos": 0}
        tables = (
            ("produccion_plata", "plata"),
            ("produccion_pita", "pita"),
            ("nomina_taller", "taller"),
            ("trabajos", "trabajos"),
        )

        with self.db.cursor() as cur:
            for table, key in tables:
                try:
                    cur.execute(
                        f"SELECT id FROM {table} WHERE trabajador_id = %s",
                        (id_merge,),
                    )
                    ids = [int(r["id"]) for r in (cur.fetchall() or []) if r.get("id") is not None]
                    moved[key] = ids
                    if ids:
                        cur.execute(
                            f"UPDATE {table} SET trabajador_id = %s WHERE trabajador_id = %s",
                            (id_keep, id_merge),
                        )
                        counts[key] = max(0, cur.rowcount or 0)
                except Exception as e:
                    logger.warning("merge %s: %s", table, e)

            # Actualizar survivor con campos mezclados
            try:
                sets = []
                params: list = []
                for col in (
                    "nombre_mostrar", "nombre_completo", "ubic", "tipo", "puesto",
                    "sueldo_modo", "sueldo_base", "fecha_incorporacion", "codigo_qr", "notas", "activo",
                ):
                    if col in mezclado:
                        sets.append(f"{col} = %s")
                        params.append(mezclado.get(col))
                if sets:
                    params.append(id_keep)
                    cur.execute(
                        f"UPDATE trabajadores SET {', '.join(sets)} WHERE id = %s",
                        tuple(params),
                    )
            except Exception as e:
                logger.warning("merge update keep: %s", e)

            cur.execute(
                "UPDATE trabajadores SET activo = 0, notas = CONCAT(COALESCE(notas,''), %s) WHERE id = %s",
                (f" [fusionado→{id_keep}]", id_merge),
            )
            try:
                self.db.connect().commit()
            except Exception:
                pass

        try:
            self.trab.sincronizar_denormalizados(id_keep)
        except Exception:
            pass

        payload = {
            "keep": id_keep,
            "merged": id_merge,
            "auto_swapped": auto_swapped,
            "counts": counts,
            "moved": moved,
            "snapshot_keep": {k: snapshot_keep.get(k) for k in (
                "id", "nombre_mostrar", "nombre_completo", "ubic", "tipo", "puesto",
                "sueldo_modo", "sueldo_base", "fecha_incorporacion", "codigo_qr", "notas", "activo",
            )},
            "snapshot_merge": {k: snapshot_merge.get(k) for k in (
                "id", "nombre_mostrar", "nombre_completo", "ubic", "tipo", "puesto",
                "sueldo_modo", "sueldo_base", "fecha_incorporacion", "codigo_qr", "notas", "activo",
            )},
            "resultado_nombre": mezclado.get("nombre_mostrar"),
        }
        event_id = None
        try:
            event_id = self.registrar(
                "merge",
                entidad="trabajador",
                entidad_id=id_keep,
                payload=payload,
            )
        except Exception:
            self.registrar(
                "merge",
                entidad="trabajador",
                entidad_id=id_keep,
                payload=payload,
            )

        return {
            "ok": True,
            "keep": id_keep,
            "merged": id_merge,
            "counts": counts,
            "auto_swapped": auto_swapped,
            "nombre_final": mezclado.get("nombre_mostrar"),
            "event_id": event_id,
            "msg": (
                f"Unido: se conservó «{mezclado.get('nombre_mostrar')}» (id {id_keep}). "
                f"La ficha id {id_merge} quedó inactiva. Puedes deshacerlo en DEV → Historial de uniones."
            ),
        }

    def listar_fusiones(self, limit: int = 50) -> list[dict]:
        """Historial de uniones (más recientes primero) para DEV."""
        out: list[dict] = []
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, tipo, entidad, entidad_id, payload_json, creado_en
                    FROM aprendizaje_eventos
                    WHERE tipo = 'merge'
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (int(limit),),
                )
                for r in cur.fetchall() or []:
                    payload = {}
                    raw = r.get("payload_json")
                    if raw:
                        try:
                            payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
                        except Exception:
                            payload = {}
                    out.append({
                        "id": r.get("id"),
                        "creado_en": str(r.get("creado_en") or ""),
                        "keep": payload.get("keep"),
                        "merged": payload.get("merged"),
                        "nombre_final": payload.get("resultado_nombre"),
                        "counts": payload.get("counts") or {},
                        "auto_swapped": payload.get("auto_swapped"),
                        "deshecho": bool(payload.get("deshecho")),
                        "payload": payload,
                    })
        except Exception as e:
            logger.warning("listar_fusiones: %s", e)
        return out

    def deshacer_fusion(self, event_id: int) -> dict:
        """
        Rollback de una unión registrada en aprendizaje_eventos.
        Restaura trabajador fusionado, reasigna filas movidas y snapshots.
        """
        import json as _json
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT id, payload_json FROM aprendizaje_eventos WHERE id = %s AND tipo = 'merge'",
                (int(event_id),),
            )
            row = cur.fetchone()
        if not row:
            return {"ok": False, "error": "Evento de unión no encontrado"}
        try:
            payload = _json.loads(row["payload_json"]) if isinstance(row.get("payload_json"), str) else (row.get("payload_json") or {})
        except Exception:
            return {"ok": False, "error": "Payload de unión inválido"}
        if payload.get("deshecho"):
            return {"ok": False, "error": "Esta unión ya fue deshecha"}
        id_keep = int(payload.get("keep") or 0)
        id_merge = int(payload.get("merged") or 0)
        moved = payload.get("moved") or {}
        snap_k = payload.get("snapshot_keep") or {}
        snap_m = payload.get("snapshot_merge") or {}
        if not id_keep or not id_merge:
            return {"ok": False, "error": "Payload incompleto (keep/merged)"}

        tables = (
            ("produccion_plata", "plata"),
            ("produccion_pita", "pita"),
            ("nomina_taller", "taller"),
            ("trabajos", "trabajos"),
        )
        restored = {"plata": 0, "pita": 0, "taller": 0, "trabajos": 0}
        with self.db.cursor() as cur:
            for table, key in tables:
                ids = [int(x) for x in (moved.get(key) or []) if x is not None]
                if not ids:
                    continue
                try:
                    placeholders = ",".join(["%s"] * len(ids))
                    cur.execute(
                        f"UPDATE {table} SET trabajador_id = %s WHERE id IN ({placeholders}) AND trabajador_id = %s",
                        tuple([id_merge] + ids + [id_keep]),
                    )
                    restored[key] = max(0, cur.rowcount or 0)
                except Exception as e:
                    logger.warning("rollback %s: %s", table, e)

            def _restore_trab(tid: int, snap: dict):
                if not snap:
                    return
                cols = []
                params = []
                for col in (
                    "nombre_mostrar", "nombre_completo", "ubic", "tipo", "puesto",
                    "sueldo_modo", "sueldo_base", "fecha_incorporacion", "codigo_qr", "notas", "activo",
                ):
                    if col in snap:
                        cols.append(f"{col} = %s")
                        params.append(snap.get(col))
                if not cols:
                    return
                params.append(tid)
                cur.execute(
                    f"UPDATE trabajadores SET {', '.join(cols)} WHERE id = %s",
                    tuple(params),
                )

            _restore_trab(id_keep, snap_k)
            _restore_trab(id_merge, snap_m)
            # asegurar activo del merge según snapshot
            try:
                act = snap_m.get("activo")
                if act is None:
                    act = 1
                cur.execute("UPDATE trabajadores SET activo = %s WHERE id = %s", (1 if act else 0, id_merge))
            except Exception:
                pass
            try:
                self.db.connect().commit()
            except Exception:
                pass

        for tid in (id_keep, id_merge):
            try:
                self.trab.sincronizar_denormalizados(tid)
            except Exception:
                pass

        payload["deshecho"] = True
        payload["deshecho_restored"] = restored
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "UPDATE aprendizaje_eventos SET payload_json = %s WHERE id = %s",
                    (_json.dumps(payload, ensure_ascii=False, default=str), int(event_id)),
                )
                try:
                    self.db.connect().commit()
                except Exception:
                    pass
        except Exception as e:
            logger.warning("mark deshecho: %s", e)

        self.registrar(
            "merge_rollback",
            entidad="trabajador",
            entidad_id=id_keep,
            payload={"event_id": int(event_id), "keep": id_keep, "merged": id_merge, "restored": restored},
        )
        return {
            "ok": True,
            "event_id": int(event_id),
            "keep": id_keep,
            "merged": id_merge,
            "restored": restored,
            "msg": f"Unión deshecha: ficha {id_merge} restaurada; filas devueltas cuando fue posible.",
        }



    def alertas_operativas(self, semana_id: int | None = None) -> list[dict]:
        """
        Avisos accionables para Dashboard / Plata (Fase 4).
        Resume conteos en lugar de listar cada folio (menos ruido).
        """
        from urllib.parse import quote
        avisos: list[dict] = []
        try:
            inact = self.detectar_folios_inactivos(semana_id) or []
        except Exception:
            inact = []
        try:
            reasig = self.detectar_reasignaciones(semana_id) or []
        except Exception:
            reasig = []
        try:
            dups = self.candidatos_duplicados_trabajadores() or []
        except Exception:
            dups = []

        n_inact = len(inact)
        n_fin = sum(1 for x in inact if (x.get("hint") or "") == "posible_finalizado")
        n_reasig_hint = sum(1 for x in inact if (x.get("hint") or "") == "posible_reasignacion")
        sid_q = f"semana_id={int(semana_id)}&" if semana_id else ""

        if n_inact:
            detalle_parts = [f"{n_inact} folio(s) sin gramos esta semana"]
            if n_fin:
                detalle_parts.append(f"{n_fin} parecen terminados")
            if n_reasig_hint:
                detalle_parts.append(f"{n_reasig_hint} posibles reasignaciones")
            avisos.append({
                "nivel": "warn" if n_inact >= 5 else "info",
                "codigo": "aprendizaje_sin_avance",
                "titulo": f"{n_inact} folio(s) sin avance",
                "detalle": " · ".join(detalle_parts) + ". Revisa en Plata o marca terminados en lote.",
                "href": f"/produccion?{sid_q}filtro=sin_avance",
                "accion": "Ver en Plata",
                "count": n_inact,
                "fuente": "aprendizaje",
            })

        if reasig:
            sample = ", ".join(
                str(x.get("folio") or "?") for x in reasig[:3]
            )
            extra = f" Ej: {sample}" if sample else ""
            avisos.append({
                "nivel": "info",
                "codigo": "aprendizaje_reasignacion",
                "titulo": f"{len(reasig)} folio(s) cambiaron de persona",
                "detalle": "La semana pasada tenían avance con otro trabajador." + extra,
                "href": f"/produccion?{sid_q}filtro=reasignados",
                "accion": "Revisar",
                "count": len(reasig),
                "fuente": "aprendizaje",
            })

        if dups:
            avisos.append({
                "nivel": "info",
                "codigo": "aprendizaje_fichas_dobles",
                "titulo": f"{len(dups)} posible(s) ficha(s) doble(s)",
                "detalle": "Misma ubicación y nombre igual o parecido. Unir o descartar en Trabajadores.",
                "href": "/trabajadores#unir-fichas",
                "accion": "Unir fichas",
                "count": len(dups),
                "fuente": "aprendizaje",
            })

        return avisos

    def resumen_aprendizaje(self) -> dict:
        """KPIs simples para panel Dev."""
        out: dict[str, Any] = {
            "eventos_7d": 0,
            "stats": [],
            "folios_inactivos": [],
            "candidatos_dup": [],
            "tabla_ok": True,
        }
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS n FROM aprendizaje_eventos
                    WHERE creado_en >= (NOW() - INTERVAL 7 DAY)
                    """
                )
                out["eventos_7d"] = int((cur.fetchone() or {}).get("n") or 0)
                cur.execute(
                    "SELECT clave, valor_num, valor_txt, muestras FROM aprendizaje_stats ORDER BY actualizado_en DESC LIMIT 30"
                )
                out["stats"] = [dict(r) for r in (cur.fetchall() or [])]
        except Exception:
            out["tabla_ok"] = False
        try:
            out["folios_inactivos"] = self.detectar_folios_inactivos()[:40]
            out["reasignaciones"] = self.detectar_reasignaciones()[:40]
            out["candidatos_dup"] = self.candidatos_duplicados_trabajadores()[:30]
            out["alertas"] = self.alertas_operativas()
        except Exception:
            logger.exception("resumen_aprendizaje")
        return out
