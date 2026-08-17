#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Automatización Taller de Fajos Central
Python + MariaDB/MySQL (base de datos: fajos_central)

Requisitos:
    pip install mysql-connector-python pandas openpyxl

Uso básico:
    python automatizacion_fajos.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("Falta la librería. Instala con:")
    print("  pip install mysql-connector-python")
    sys.exit(1)

# ============================================================
# CONFIGURACIÓN DE CONEXIÓN
# Ajusta estos valores según tu servidor
# ============================================================
DB_CONFIG = {
    "host": "localhost",          # o la IP del servidor
    "port": 3306,
    "user": "root",               # tu usuario de MariaDB
    "password": "",               # tu contraseña
    "database": "fajos_central",
    "charset": "utf8mb4",
    "collation": "utf8mb4_unicode_ci",
    "autocommit": True,
}


# ============================================================
# CLASE PRINCIPAL
# ============================================================
class FajosDB:
    """Capa de acceso a la base de datos del taller."""

    def __init__(self, config: dict | None = None):
        self.config = config or DB_CONFIG
        self.conn: Optional[mysql.connector.MySQLConnection] = None

    def conectar(self) -> None:
        try:
            self.conn = mysql.connector.connect(**self.config)
            print(f"✓ Conectado a {self.config['database']} @ {self.config['host']}")
        except Error as e:
            print(f"✗ Error de conexión: {e}")
            raise

    def desconectar(self) -> None:
        if self.conn and self.conn.is_connected():
            self.conn.close()
            print("✓ Conexión cerrada")

    def _cursor(self, dictionary: bool = True):
        if not self.conn or not self.conn.is_connected():
            self.conectar()
        return self.conn.cursor(dictionary=dictionary)

    # ----------------------------------------------------------
    # TRABAJADORES
    # ----------------------------------------------------------
    def listar_trabajadores_plt(self, solo_activos: bool = True) -> list[dict]:
        """Devuelve trabajadores de plata (PLT / PLT/PIT / Mixto)."""
        sql = """
            SELECT id, nombre_mostrar, nombre_completo, ubic, tipo,
                   fecha_incorporacion, activo
            FROM trabajadores
            WHERE (tipo = 'PLT' OR tipo = 'PLT/PIT' OR tipo = 'Mixto')
        """
        if solo_activos:
            sql += " AND activo = 1"
        sql += " ORDER BY nombre_mostrar, ubic"

        cur = self._cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        return rows

    def agregar_trabajador(
        self,
        nombre_mostrar: str,
        ubic: int,
        tipo: str = "PLT",
        nombre_completo: str | None = None,
        puesto: str | None = None,
        fecha_incorporacion: date | str | None = None,
    ) -> int:
        """Inserta un trabajador nuevo. Devuelve el id generado."""
        sql = """
            INSERT INTO trabajadores
                (nombre_mostrar, nombre_completo, ubic, tipo, puesto, activo, fecha_incorporacion)
            VALUES (%s, %s, %s, %s, %s, 1, %s)
        """
        cur = self._cursor()
        cur.execute(
            sql,
            (
                nombre_mostrar,
                nombre_completo or nombre_mostrar,
                ubic,
                tipo,
                puesto,
                fecha_incorporacion,
            ),
        )
        new_id = cur.lastrowid
        cur.close()
        print(f"✓ Trabajador agregado: {nombre_mostrar} (Ubic {ubic}) → id={new_id}")
        return new_id

    def desactivar_trabajador(self, trabajador_id: int) -> None:
        cur = self._cursor()
        cur.execute("UPDATE trabajadores SET activo = 0 WHERE id = %s", (trabajador_id,))
        cur.close()
        print(f"✓ Trabajador id={trabajador_id} marcado como inactivo")

    # ----------------------------------------------------------
    # SEMANAS
    # ----------------------------------------------------------
    def crear_semana(
        self,
        codigo: str,
        fecha_inicio: date | str,
        fecha_fin: date | str,
        anio: int = 2026,
        notas: str | None = None,
    ) -> int:
        """Crea una semana de nómina. Devuelve el id."""
        sql = """
            INSERT INTO semanas (codigo, fecha_inicio, fecha_fin, anio, notas)
            VALUES (%s, %s, %s, %s, %s)
        """
        cur = self._cursor()
        cur.execute(sql, (codigo, fecha_inicio, fecha_fin, anio, notas))
        new_id = cur.lastrowid
        cur.close()
        print(f"✓ Semana {codigo} creada → id={new_id}")
        return new_id

    def obtener_semana(self, codigo: str, anio: int = 2026) -> dict | None:
        cur = self._cursor()
        cur.execute(
            "SELECT * FROM semanas WHERE codigo = %s AND anio = %s",
            (codigo, anio),
        )
        row = cur.fetchone()
        cur.close()
        return row

    # ----------------------------------------------------------
    # PRODUCCIÓN PLATA (captura de gramos)
    # ----------------------------------------------------------
    def insertar_produccion(
        self,
        semana_id: int,
        nombre: str,
        ubic: int,
        folio: str | None = None,
        modelo: str | None = None,
        material: str | None = None,
        tarifa_gr: float | Decimal | None = None,
        gm_sab: float | None = None,
        gm_dom: float | None = None,
        gm_lun: float | None = None,
        gm_mar: float | None = None,
        gm_mie: float | None = None,
        gm_jue: float | None = None,
        gm_vie: float | None = None,
        trabajador_id: int | None = None,
        notas: str | None = None,
    ) -> int:
        """
        Inserta una línea de producción.
        total_gramos y efectivo se calculan solos en la BD.
        """
        sql = """
            INSERT INTO produccion_plata (
                semana_id, trabajador_id, nombre, ubic, folio, modelo, material, tarifa_gr,
                gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie, notas
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        cur = self._cursor()
        cur.execute(
            sql,
            (
                semana_id,
                trabajador_id,
                nombre,
                ubic,
                folio,
                modelo,
                material,
                tarifa_gr,
                gm_sab,
                gm_dom,
                gm_lun,
                gm_mar,
                gm_mie,
                gm_jue,
                gm_vie,
                notas,
            ),
        )
        new_id = cur.lastrowid
        cur.close()
        return new_id

    def listar_produccion_semana(self, semana_id: int) -> list[dict]:
        """Lista todas las líneas de producción de una semana (con totales calculados)."""
        sql = """
            SELECT id, nombre, ubic, folio, modelo, material, tarifa_gr,
                   gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie,
                   total_gramos, efectivo, firmado, notas
            FROM produccion_plata
            WHERE semana_id = %s
            ORDER BY nombre, ubic, id
        """
        cur = self._cursor()
        cur.execute(sql, (semana_id,))
        rows = cur.fetchall()
        cur.close()
        return rows

    def total_semana_plata(self, semana_id: int) -> dict:
        """Suma de gramos y efectivo de una semana."""
        sql = """
            SELECT
                COUNT(*)            AS lineas,
                COALESCE(SUM(total_gramos), 0) AS total_gramos,
                COALESCE(SUM(efectivo), 0)     AS total_efectivo
            FROM produccion_plata
            WHERE semana_id = %s
        """
        cur = self._cursor()
        cur.execute(sql, (semana_id,))
        row = cur.fetchone()
        cur.close()
        return row

    def marcar_firmado(self, produccion_id: int, firmado: bool = True) -> None:
        cur = self._cursor()
        cur.execute(
            "UPDATE produccion_plata SET firmado = %s WHERE id = %s",
            (1 if firmado else 0, produccion_id),
        )
        cur.close()

    # ----------------------------------------------------------
    # RESUMEN NÓMINAS
    # ----------------------------------------------------------
    def guardar_resumen_semana(
        self,
        semana_id: int,
        nomina_plt: float | None = None,
        nomina_pit: float | None = None,
        nomina_tll: float | None = None,
        notas: str | None = None,
    ) -> None:
        """Inserta o actualiza el resumen de una semana."""
        sql = """
            INSERT INTO resumen_nominas (semana_id, nomina_plt, nomina_pit, nomina_tll, notas)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                nomina_plt = VALUES(nomina_plt),
                nomina_pit = VALUES(nomina_pit),
                nomina_tll = VALUES(nomina_tll),
                notas      = VALUES(notas)
        """
        cur = self._cursor()
        cur.execute(sql, (semana_id, nomina_plt, nomina_pit, nomina_tll, notas))
        cur.close()
        print(f"✓ Resumen de semana_id={semana_id} guardado")

    def listar_resumenes(self) -> list[dict]:
        sql = """
            SELECT r.*, s.codigo, s.fecha_inicio, s.fecha_fin
            FROM resumen_nominas r
            JOIN semanas s ON s.id = r.semana_id
            ORDER BY s.fecha_inicio
        """
        cur = self._cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        cur.close()
        return rows

    # ----------------------------------------------------------
    # UTILIDADES
    # ----------------------------------------------------------
    def exportar_produccion_csv(self, semana_id: int, ruta: str) -> None:
        """Exporta la producción de una semana a CSV (útil para Excel)."""
        try:
            import pandas as pd
        except ImportError:
            print("Instala pandas: pip install pandas")
            return

        rows = self.listar_produccion_semana(semana_id)
        if not rows:
            print("No hay datos para exportar")
            return

        df = pd.DataFrame(rows)
        df.to_csv(ruta, index=False, encoding="utf-8-sig")
        print(f"✓ Exportado a {ruta}")

    def preparar_nomina_formal(self, semana_id: int) -> list[dict]:
        """
        Devuelve los datos listos para imprimir la nómina formal:
        nombre, ubic, folio, modelo, material, tarifa, días, total_gramos, efectivo.
        """
        return self.listar_produccion_semana(semana_id)


# ============================================================
# EJEMPLO DE USO / MENÚ INTERACTIVO
# ============================================================
def menu():
    db = FajosDB()

    try:
        db.conectar()

        while True:
            print("\n" + "=" * 50)
            print("  TALLER DE FAJOS — Automatización")
            print("=" * 50)
            print("1. Listar trabajadores PLT activos")
            print("2. Agregar trabajador")
            print("3. Crear semana de nómina")
            print("4. Insertar línea de producción (ejemplo)")
            print("5. Ver producción de una semana")
            print("6. Totales de una semana (gramos + efectivo)")
            print("7. Guardar resumen de nómina")
            print("8. Listar resúmenes")
            print("9. Exportar producción a CSV")
            print("0. Salir")
            print("-" * 50)

            op = input("Opción: ").strip()

            if op == "0":
                break

            elif op == "1":
                rows = db.listar_trabajadores_plt()
                print(f"\n{len(rows)} trabajadores PLT activos:\n")
                for r in rows:
                    print(f"  {r['id']:3} | {r['nombre_mostrar']:<30} | Ubic {r['ubic']:<5} | {r['tipo']}")

            elif op == "2":
                nombre = input("Nombre (mostrar): ").strip()
                ubic = int(input("Ubicación: ").strip())
                tipo = input("Tipo [PLT]: ").strip() or "PLT"
                fecha = input("Fecha incorporación (YYYY-MM-DD) [hoy]: ").strip() or date.today().isoformat()
                db.agregar_trabajador(nombre, ubic, tipo=tipo, fecha_incorporacion=fecha)

            elif op == "3":
                codigo = input("Código semana (ej: 25-08): ").strip()
                ini = input("Fecha inicio (YYYY-MM-DD): ").strip()
                fin = input("Fecha fin (YYYY-MM-DD): ").strip()
                db.crear_semana(codigo, ini, fin)

            elif op == "4":
                print("\n--- Insertar producción de ejemplo ---")
                semana_id = int(input("ID de semana: ").strip())
                nombre = input("Nombre trabajador: ").strip()
                ubic = int(input("Ubic: ").strip())
                folio = input("Folio: ").strip() or None
                modelo = input("Modelo: ").strip() or None
                material = input("Material [AG3]: ").strip() or "AG3"
                tarifa = float(input("Tarifa $/gr [12]: ").strip() or "12")
                print("Gramos por día (Enter = vacío):")
                dias = {}
                for d in ["sab", "dom", "lun", "mar", "mie", "jue", "vie"]:
                    v = input(f"  {d}: ").strip()
                    dias[d] = float(v) if v else None

                new_id = db.insertar_produccion(
                    semana_id=semana_id,
                    nombre=nombre,
                    ubic=ubic,
                    folio=folio,
                    modelo=modelo,
                    material=material,
                    tarifa_gr=tarifa,
                    gm_sab=dias["sab"],
                    gm_dom=dias["dom"],
                    gm_lun=dias["lun"],
                    gm_mar=dias["mar"],
                    gm_mie=dias["mie"],
                    gm_jue=dias["jue"],
                    gm_vie=dias["vie"],
                )
                print(f"✓ Línea insertada id={new_id}")
                tot = db.total_semana_plata(semana_id)
                print(f"  Totales semana → Gramos: {tot['total_gramos']} | Efectivo: ${tot['total_efectivo']}")

            elif op == "5":
                semana_id = int(input("ID de semana: ").strip())
                rows = db.listar_produccion_semana(semana_id)
                print(f"\n{len(rows)} líneas:\n")
                for r in rows:
                    print(
                        f"  {r['nombre']:<25} | {r['folio'] or '-':<10} | "
                        f"{r['modelo'] or '-':<12} | Gr: {r['total_gramos'] or 0:>7} | "
                        f"$ {r['efectivo'] or 0:>8}"
                    )

            elif op == "6":
                semana_id = int(input("ID de semana: ").strip())
                tot = db.total_semana_plata(semana_id)
                print(f"\nLíneas: {tot['lineas']}")
                print(f"Total gramos : {tot['total_gramos']}")
                print(f"Total efectivo: ${tot['total_efectivo']}")

            elif op == "7":
                semana_id = int(input("ID de semana: ").strip())
                # Calcular PLT automáticamente
                tot = db.total_semana_plata(semana_id)
                plt = float(tot["total_efectivo"] or 0)
                print(f"PLT calculado automáticamente: ${plt}")
                pit = input("Nómina PIT (Enter=0): ").strip()
                tll = input("Nómina TLL (Enter=0): ").strip()
                db.guardar_resumen_semana(
                    semana_id,
                    nomina_plt=plt,
                    nomina_pit=float(pit) if pit else 0,
                    nomina_tll=float(tll) if tll else 0,
                )

            elif op == "8":
                rows = db.listar_resumenes()
                print(f"\n{len(rows)} resúmenes:\n")
                for r in rows:
                    print(
                        f"  {r['codigo']:<8} | PLT ${r['nomina_plt'] or 0:>10} | "
                        f"PIT ${r['nomina_pit'] or 0:>10} | TLL ${r['nomina_tll'] or 0:>10} | "
                        f"TOTAL ${r['total_semana'] or 0:>10}"
                    )

            elif op == "9":
                semana_id = int(input("ID de semana: ").strip())
                ruta = input("Ruta CSV [produccion_semana.csv]: ").strip() or "produccion_semana.csv"
                db.exportar_produccion_csv(semana_id, ruta)

            else:
                print("Opción no válida")

    except Error as e:
        print(f"Error de base de datos: {e}")
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario")
    finally:
        db.desconectar()


if __name__ == "__main__":
    menu()
