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
    # Colores por material (impresión formal) — mismos tonos que la UI
    MAT_FILLS = {
        "AG3": PatternFill("solid", fgColor="D6EAF8"),
        "AG4": PatternFill("solid", fgColor="D5F5E3"),
        "DOL": PatternFill("solid", fgColor="FCF3CF"),
        "DLO": PatternFill("solid", fgColor="FAD7A0"),
    }
    MAT_DEFAULT = PatternFill("solid", fgColor="E8DAEF")
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
        agrupar_material: bool = True,
    ) -> Path:
        """
        Exporta la nómina formal lista para imprimir y firmar.
        Colores por material, orden Ubic→Nombre (o material→ubic→nombre).
        """
        ruta = Path(ruta)
        lineas = list(lineas)

        def _sort_key(r: dict):
            try:
                u = int(r.get("ubic") or 0)
            except (TypeError, ValueError):
                u = 0
            mat = str(r.get("material") or "").upper()
            nombre = str(r.get("nombre") or "").upper()
            folio = str(r.get("folio") or "").upper()
            if agrupar_material:
                return (mat, u, nombre, folio)
            return (u, nombre, folio)

        lineas.sort(key=_sort_key)

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
        ws["A4"] = "Color por material:"
        ws["A4"].font = Font(name="Calibri", size=8, italic=True, color="666666")
        for col, (code, fill) in enumerate(self.MAT_FILLS.items(), start=2):
            cell = ws.cell(row=4, column=col, value=code)
            cell.fill = fill
            cell.font = Font(name="Calibri", bold=True, size=8)
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center")

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
            mat = str(row.get("material") or "").strip().upper()
            fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else None)
            for col, val in enumerate(values, 1):
                # ocultar ceros en gramos / tarifa
                if col >= 6 and col <= 14 and val is not None:
                    try:
                        if float(val) == 0:
                            val = None
                    except (TypeError, ValueError):
                        pass
                cell = ws.cell(row=r, column=col, value=val)
                cell.border = self.THIN
                cell.alignment = Alignment(horizontal="center" if col > 1 else "left")
                if fill is not None:
                    cell.fill = fill
                if col in (6, 7, 8, 9, 10, 11, 12, 13, 14) and val is not None:
                    cell.number_format = "0.##"
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
        ws.print_title_rows = "1:5"  # encabezado + leyenda + columnas

        wb.save(ruta)
        return ruta


    def exportar_pdf_formal(
        self,
        ruta: str | Path,
        lineas: list[dict],
        codigo_semana: str = "",
    ) -> Path:
        """PDF formal para firma (reportlab). Colores por material."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        except ImportError as e:
            raise RuntimeError(
                "Falta reportlab para PDF. Ejecuta: pip install reportlab"
            ) from e

        ruta = Path(ruta)
        lineas = sorted(
            list(lineas),
            key=lambda r: (
                str(r.get("material") or "").upper(),
                int(r.get("ubic") or 0) if str(r.get("ubic") or "").isdigit() else 0,
                str(r.get("nombre") or "").upper(),
            ),
        )
        mat_colors = {
            "AG3": colors.HexColor("#D6EAF8"),
            "AG4": colors.HexColor("#D5F5E3"),
            "DOL": colors.HexColor("#FCF3CF"),
            "DLO": colors.HexColor("#FAD7A0"),
        }
        buf_path = ruta
        doc = SimpleDocTemplate(
            str(buf_path),
            pagesize=landscape(letter),
            leftMargin=8 * mm,
            rightMargin=8 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
            title=f"Nomina formal {codigo_semana}",
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "T", parent=styles["Title"], fontSize=13, textColor=colors.HexColor("#1F4E79"),
        )
        story = [
            Paragraph("Taller de Fajos Central — NÓMINA FORMAL", title_style),
            Paragraph(f"Semana: {codigo_semana}", styles["Normal"]),
            Spacer(1, 6),
        ]
        keys = [
            ("nombre", "Nombre"), ("ubic", "Ubic"), ("folio", "Folio"),
            ("modelo", "Modelo"), ("material", "Mat"), ("tarifa_gr", "$/Gr"),
            ("gm_sab", "Sáb"), ("gm_dom", "Dom"), ("gm_lun", "Lun"),
            ("gm_mar", "Mar"), ("gm_mie", "Mié"), ("gm_jue", "Jue"), ("gm_vie", "Vie"),
            ("total_gramos", "Tot"), ("efectivo", "Efectivo"),
        ]
        data = [[h for _, h in keys] + ["Firma"]]
        row_mats = [""]
        total_gr = total_ef = 0.0
        for row in lineas:
            mat = str(row.get("material") or "").upper()
            row_mats.append(mat)
            cells = []
            for k, _ in keys:
                val = row.get(k)
                try:
                    if val is not None and float(val) == 0 and k != "ubic":
                        val = None
                except (TypeError, ValueError):
                    pass
                if val is None or val == "":
                    cells.append("")
                elif k == "efectivo":
                    cells.append(f"${float(val):,.2f}")
                    total_ef += float(val)
                elif k in ("total_gramos", "tarifa_gr") or str(k).startswith("gm_"):
                    cells.append(f"{float(val):g}")
                    if k == "total_gramos":
                        total_gr += float(val)
                else:
                    cells.append(str(val))
            cells.append("")
            data.append(cells)
        data.append(
            ["", "", "", "", "", "", "", "", "", "", "", "", "TOTAL", f"{total_gr:g}", f"${total_ef:,.2f}", ""]
        )
        table = Table(data, repeatRows=1)
        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#C8E6C9")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
        for i, mat in enumerate(row_mats):
            if i == 0:
                continue
            cmds.append(("BACKGROUND", (0, i), (-1, i), mat_colors.get(mat, colors.HexColor("#E8DAEF"))))
        table.setStyle(TableStyle(cmds))
        story.append(table)
        doc.build(story)
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
