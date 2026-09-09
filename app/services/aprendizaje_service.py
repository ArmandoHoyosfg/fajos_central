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
    ) -> None:
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
        except Exception:
            # Tabla puede no existir aún (migración 004)
            logger.debug("No se pudo registrar aprendizaje (%s)", tipo, exc_info=True)

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

        out: list[dict] = []
        for r in lineas:
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
        na, nb = cls._norm_nombre(a), cls._norm_nombre(b)
        if not na or not nb:
            return False
        if na == nb:
            return True
        if na in nb or nb in na:
            return True
        ta, tb = na.split(), nb.split()
        if ta and tb and ta[0] == tb[0] and len(ta[0]) >= 3:
            # mismo primer nombre + al menos un token extra en común, o uno es solo el nombre corto
            if len(ta) == 1 or len(tb) == 1:
                return True
            if set(ta) & set(tb) - {ta[0]}:
                return True
        return False

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
        Posibles duplicados:
        - mismo nombre (sin importar ubic)
        - nombres similares en la misma ubicación
        Respeta descartes recientes (7 días).
        """
        rows = self.trab.listar(solo_activos=False)
        skipped = self._pares_descartados(7)
        seen_pairs: set[tuple[int, int]] = set()
        cands: list[dict] = []

        def _detalle(group):
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

        def _add(motivo: str, label: str, group: list):
            ids = sorted(int(g["id"]) for g in group)
            # si hay >2, generamos el grupo completo; filtramos si todos los pares están descartados
            pairs_ok = False
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    p = (ids[i], ids[j])
                    if p in seen_pairs:
                        continue
                    if p in skipped:
                        continue
                    pairs_ok = True
                    seen_pairs.add(p)
            if not pairs_ok and len(ids) == 2 and (ids[0], ids[1]) in skipped:
                return
            if len(ids) < 2:
                return
            # si solo 2 y descartado, ya salimos; si >2 y al menos un par vivo, mostrar grupo
            if len(ids) == 2 and (ids[0], ids[1]) in skipped:
                return
            cands.append({
                "nombre": label,
                "motivo": motivo,
                "n": len(group),
                "ids": ids,
                "detalle": _detalle(group),
            })

        # 1) mismo nombre exacto (normalizado)
        by_name: dict[str, list] = {}
        for r in rows:
            k = self._norm_nombre(r.get("nombre_mostrar") or "")
            if not k:
                continue
            by_name.setdefault(k, []).append(r)
        for name, group in by_name.items():
            if len(group) >= 2:
                _add("mismo_nombre", name, group)

        # 2) misma ubic + nombres similares (activos prioritarios)
        by_ubic: dict[str, list] = {}
        for r in rows:
            if not r.get("activo"):
                continue
            u = str(r.get("ubic") if r.get("ubic") is not None else "").strip()
            if not u:
                continue
            by_ubic.setdefault(u, []).append(r)
        for ubic, group in by_ubic.items():
            n = len(group)
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = group[i], group[j]
                    ia, ib = int(a["id"]), int(b["id"])
                    pair = (min(ia, ib), max(ia, ib))
                    if pair in skipped or pair in seen_pairs:
                        continue
                    if self._nombres_similares(a.get("nombre_mostrar") or "", b.get("nombre_mostrar") or ""):
                        # evitar si ya entró por mismo nombre exacto
                        if self._norm_nombre(a.get("nombre_mostrar") or "") == self._norm_nombre(b.get("nombre_mostrar") or ""):
                            continue
                        seen_pairs.add(pair)
                        label = f"{a.get('nombre_mostrar')} / {b.get('nombre_mostrar')} · ubic {ubic}"
                        cands.append({
                            "nombre": label,
                            "motivo": "similar_misma_ubic",
                            "n": 2,
                            "ids": [ia, ib],
                            "detalle": _detalle([a, b]),
                        })

        return cands

    def fusionar_trabajadores(self, id_keep: int, id_merge: int) -> dict:
        """
        Reasigna producción/pita/taller/trabajos de id_merge → id_keep
        y desactiva id_merge. Actualiza nombre/ubic denormalizados del survivor.
        """
        if int(id_keep) == int(id_merge):
            return {"ok": False, "error": "ids iguales"}
        keep = self.trab.obtener(id_keep)
        merge = self.trab.obtener(id_merge)
        counts = {"plata": 0, "pita": 0, "taller": 0, "trabajos": 0}
        with self.db.cursor() as cur:
            for table, key in (
                ("produccion_plata", "plata"),
                ("produccion_pita", "pita"),
                ("nomina_taller", "taller"),
                ("trabajos", "trabajos"),
            ):
                try:
                    cur.execute(
                        f"UPDATE {table} SET trabajador_id = %s WHERE trabajador_id = %s",
                        (id_keep, id_merge),
                    )
                    counts[key] = max(0, cur.rowcount or 0)
                except Exception as e:
                    logger.warning("merge %s: %s", table, e)
            # desactivar el fusionado
            cur.execute(
                "UPDATE trabajadores SET activo = 0, notas = CONCAT(COALESCE(notas,''), %s) WHERE id = %s",
                (f" [fusionado→{id_keep}]", id_merge),
            )
            try:
                self.db.connect().commit()
            except Exception:
                pass
        # sync denormalizados del que se queda
        try:
            self.trab.sincronizar_denormalizados(id_keep)
        except Exception:
            pass
        self.registrar(
            "merge",
            entidad="trabajador",
            entidad_id=id_keep,
            payload={"merged": id_merge, "counts": counts, "keep": keep.get("nombre_mostrar"), "from": merge.get("nombre_mostrar")},
        )
        return {"ok": True, "keep": id_keep, "merged": id_merge, "counts": counts}

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
        except Exception:
            logger.exception("resumen_aprendizaje")
        return out
