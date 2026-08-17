"""
Importar / Exportar Excel potenciado (compatible con la estructura optimizada).
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.page import PageMargins


class ExcelService:
    """Genera e importa archivos Excel de nómina potenciado."""

    HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
    HEADER_FONT = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
    ALT_FILL = PatternFill("solid", fgColor="E8F4FD")
    GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
    THIN = Border(
        left=Side(style="thin", color="808080"),
        right=Side(style="thin", color="808080"),
        top=Side(style="thin", color="808080"),
        bottom=Side(style="thin", color="808080"),
    )

    def exportar_nomina_formal(
        self,
        ruta: str | Path,
        lineas: list[dict],
        codigo_semana: str = "",
        mes: str = "",
        anio: int = 2026,
    ) -> Path:
        """
        Exporta la nómina formal lista para imprimir y firmar.
        Estructura similar a Nomina-Formal del Excel optimizado.
        """
        ruta = Path(ruta)
        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Formal"

        # Encabezado
        ws["A1"] = "Taller de Fajos Central"
        ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
        ws.merge_cells("A1:P1")

        ws["A2"] = "NÓMINA FORMAL SEMANAL — PLATA"
        ws["A2"].font = Font(name="Calibri", bold=True, size=11, color="2E75B6")
        ws.merge_cells("A2:P2")

        ws["A3"] = f"Semana: {codigo_semana}"
        ws["C3"] = f"Mes: {mes}"
        ws["E3"] = f"Año: {anio}"

        headers = [
            "Nombre", "Ubic", "Folio", "Modelo", "Material", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie",
            "Total Gr", "Efectivo", "Firma",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = self.THIN

        for i, row in enumerate(lineas):
            r = 6 + i
            values = [
                row.get("nombre"),
                row.get("ubic"),
                row.get("folio"),
                row.get("modelo"),
                row.get("material"),
                row.get("tarifa_gr"),
                row.get("gm_sab"),
                row.get("gm_dom"),
                row.get("gm_lun"),
                row.get("gm_mar"),
                row.get("gm_mie"),
                row.get("gm_jue"),
                row.get("gm_vie"),
                row.get("total_gramos"),
                row.get("efectivo"),
                "",  # firma
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=r, column=col, value=val)
                cell.border = self.THIN
                cell.alignment = Alignment(horizontal="center")
                if i % 2 == 0:
                    cell.fill = self.ALT_FILL
                if col == 15 and val is not None:
                    cell.number_format = '$#,##0.00'

        # Totales
        last = 5 + len(lineas)
        tot_row = last + 1
        ws.cell(row=tot_row, column=13, value="TOTALES →").font = Font(bold=True)
        if lineas:
            ws.cell(row=tot_row, column=14, value=f"=SUM(N6:N{last})")
            ws.cell(row=tot_row, column=15, value=f"=SUM(O6:O{last})")
            ws.cell(row=tot_row, column=14).fill = self.GREEN_FILL
            ws.cell(row=tot_row, column=15).fill = self.GREEN_FILL
            ws.cell(row=tot_row, column=15).number_format = '$#,##0.00'
            ws.cell(row=tot_row, column=14).font = Font(bold=True)
            ws.cell(row=tot_row, column=15).font = Font(bold=True)

        # Anchos y página
        widths = {
            "A": 22, "B": 7, "C": 11, "D": 13, "E": 9, "F": 7,
            "G": 6, "H": 6, "I": 6, "J": 6, "K": 6, "L": 6, "M": 6,
            "N": 10, "O": 11, "P": 10,
        }
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins = PageMargins(left=0.3, right=0.3, top=0.4, bottom=0.4)
        ws.print_title_rows = "5:5"

        wb.save(ruta)
        return ruta

    def exportar_captura(
        self,
        ruta: str | Path,
        trabajadores: list[dict],
        codigo_semana: str = "",
        mes: str = "",
        filas_por_persona: int = 3,
    ) -> Path:
        """Exporta hoja de captura pre-llenada (estilo Nomina-Imprimir)."""
        ruta = Path(ruta)
        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Imprimir"

        ws["A1"] = "Taller de Fajos Central"
        ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
        ws["A2"] = "HOJA DE CAPTURA SEMANAL — PLATA"
        ws["A2"].font = Font(name="Calibri", bold=True, size=11, color="2E75B6")
        ws["A3"] = f"Semana: {codigo_semana}"
        ws["C3"] = f"Mes: {mes}"

        headers = [
            "Nombre", "Ubic", "Folio", "Modelo", "Material", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Notas",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center")

        r = 6
        for i, t in enumerate(trabajadores):
            fill = self.ALT_FILL if i % 2 == 0 else PatternFill("solid", fgColor="FFF8E7")
            for f in range(filas_por_persona):
                if f == 0:
                    ws.cell(row=r, column=1, value=t.get("nombre_mostrar") or t.get("nombre"))
                    ws.cell(row=r, column=2, value=t.get("ubic"))
                for col in range(1, 15):
                    cell = ws.cell(row=r, column=col)
                    cell.border = self.THIN
                    cell.fill = fill
                r += 1

        # Extra vacío
        gray = PatternFill("solid", fgColor="F2F2F2")
        for _ in range(12):
            for col in range(1, 15):
                cell = ws.cell(row=r, column=col)
                cell.border = self.THIN
                cell.fill = gray
            r += 1

        widths = {
            "A": 22, "B": 7, "C": 11, "D": 13, "E": 9, "F": 7,
            "G": 6, "H": 6, "I": 6, "J": 6, "K": 6, "L": 6, "M": 6, "N": 12,
        }
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        wb.save(ruta)
        return ruta

    def importar_produccion_csv(self, ruta: str | Path) -> list[dict]:
        """Importa un CSV/Excel de producción y devuelve lista de dicts listos para insertar."""
        ruta = Path(ruta)
        if ruta.suffix.lower() in {".xlsx", ".xls"}:
            df = pd.read_excel(ruta)
        else:
            df = pd.read_csv(ruta)

        # Normalizar nombres de columnas
        col_map = {
            "nombre": "nombre",
            "name": "nombre",
            "ubic": "ubic",
            "ubicacion": "ubic",
            "folio": "folio",
            "modelo": "modelo",
            "material": "material",
            "tarifa_gr": "tarifa_gr",
            "$/gr": "tarifa_gr",
            "tarifa": "tarifa_gr",
            "gm_sab": "gm_sab", "sab": "gm_sab", "sáb": "gm_sab",
            "gm_dom": "gm_dom", "dom": "gm_dom",
            "gm_lun": "gm_lun", "lun": "gm_lun",
            "gm_mar": "gm_mar", "mar": "gm_mar",
            "gm_mie": "gm_mie", "mie": "gm_mie", "mié": "gm_mie",
            "gm_jue": "gm_jue", "jue": "gm_jue",
            "gm_vie": "gm_vie", "vie": "gm_vie",
            "notas": "notas",
        }
        df.columns = [str(c).strip().lower() for c in df.columns]
        rename = {c: col_map[c] for c in df.columns if c in col_map}
        df = df.rename(columns=rename)

        records = []
        for _, row in df.iterrows():
            if pd.isna(row.get("nombre")):
                continue
            rec = {
                "nombre": str(row["nombre"]).strip(),
                "ubic": int(row["ubic"]) if not pd.isna(row.get("ubic")) else 0,
                "folio": str(row["folio"]).strip() if not pd.isna(row.get("folio")) else None,
                "modelo": str(row["modelo"]).strip() if not pd.isna(row.get("modelo")) else None,
                "material": str(row["material"]).strip() if not pd.isna(row.get("material")) else None,
                "tarifa_gr": float(row["tarifa_gr"]) if not pd.isna(row.get("tarifa_gr")) else None,
                "notas": str(row["notas"]).strip() if not pd.isna(row.get("notas")) else None,
            }
            for d in ["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"]:
                v = row.get(d)
                rec[d] = float(v) if v is not None and not pd.isna(v) else None
            records.append(rec)
        return records
