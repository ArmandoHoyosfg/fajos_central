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
        agrupar_material: bool = False,  # por defecto: ubic → nombre (materiales mezclados, color por fila)
        fecha_inicio: str | None = None,
        fecha_fin: str | None = None,
        titulo_extra: str = "",
    ) -> Path:
        """
        Exporta la nómina formal lista para imprimir y firmar.
        Formato enriquecido tipo hoja Nomina-Formal del Excel del taller.
        """
        from datetime import date, datetime

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

        # Solo líneas con contenido útil (como formal de pago)
        def _util(r: dict) -> bool:
            if r.get("folio") or r.get("modelo"):
                return True
            try:
                return float(r.get("total_gramos") or 0) > 0
            except (TypeError, ValueError):
                return False

        lineas = [r for r in lineas if _util(r)]
        lineas.sort(key=_sort_key)

        hoy = date.today()
        generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        if not mes:
            meses = {
                1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
                5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
                9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
            }
            mes = meses.get(hoy.month, "")
        if not anio:
            anio = hoy.year

        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Formal"

        # --- Encabezado enriquecido ---
        ws.merge_cells("A1:P1")
        c = ws["A1"]
        c.value = "TALLER DE FAJOS CENTRAL"
        c.font = Font(name="Calibri", bold=True, size=16, color="1F4E79")
        c.alignment = Alignment(horizontal="left", vertical="center")

        ws.merge_cells("A2:P2")
        c = ws["A2"]
        c.value = "NÓMINA FORMAL SEMANAL — PRODUCCIÓN PLATA (PLT)"
        c.font = Font(name="Calibri", bold=True, size=12, color="2E75B6")

        # Fila meta: semana, periodo, mes, año, fecha de emisión
        periodo = ""
        if fecha_inicio and fecha_fin:
            periodo = f"{fecha_inicio} → {fecha_fin}"
        elif fecha_inicio:
            periodo = str(fecha_inicio)

        ws["A3"] = "Semana"
        ws["B3"] = codigo_semana or "—"
        ws["C3"] = "Periodo"
        ws["D3"] = periodo or "—"
        ws.merge_cells("D3:F3")
        ws["G3"] = "Mes"
        ws["H3"] = mes
        ws["I3"] = "Año"
        ws["J3"] = anio
        ws["K3"] = "Emitido"
        ws["L3"] = generado
        ws.merge_cells("L3:N3")
        for col in range(1, 15):
            cell = ws.cell(row=3, column=col)
            cell.font = Font(name="Calibri", size=9, bold=(col % 2 == 1))
            cell.alignment = Alignment(horizontal="left" if col % 2 == 1 else "center")

        if titulo_extra:
            ws["A3"].value = str(ws["A3"].value)  # keep
            ws["O3"] = titulo_extra

        # Leyenda materiales
        ws["A4"] = "Material / color:"
        ws["A4"].font = Font(name="Calibri", size=8, italic=True, color="666666")
        for col, (code, fill) in enumerate(self.MAT_FILLS.items(), start=2):
            cell = ws.cell(row=4, column=col, value=code)
            cell.fill = fill
            cell.font = Font(name="Calibri", bold=True, size=8)
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center")
        ws["F4"] = "Orden: ubic → nombre → folio  ·  Color de fila = material  ·  Ceros ocultos  ·  Firma al pagar"
        ws["F4"].font = Font(name="Calibri", size=8, italic=True, color="666666")
        ws.merge_cells("F4:P4")

        headers = [
            "Nombre", "Ubic", "Folio", "Modelo", "Material", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie",
            "Total Gr", "Efectivo", "Firma",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", wrap_text=True, vertical="center")
            cell.border = self.THIN
        ws.row_dimensions[5].height = 22

        # Datos
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
                "",
            ]
            mat = str(row.get("material") or "").strip().upper()
            fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else None)
            for col, val in enumerate(values, 1):
                if col >= 6 and col <= 15 and val is not None:
                    try:
                        if float(val) == 0:
                            val = None
                    except (TypeError, ValueError):
                        pass
                cell = ws.cell(row=r, column=col, value=val)
                cell.border = self.THIN
                cell.alignment = Alignment(
                    horizontal="left" if col == 1 else "center",
                    vertical="center",
                )
                if fill is not None:
                    cell.fill = fill
                if col == 6 and val is not None:
                    cell.number_format = "0.00"
                if 7 <= col <= 14 and val is not None:
                    cell.number_format = "0.##"
                if col == 15 and val is not None:
                    cell.number_format = '"$"#,##0.00'

        last = 5 + max(len(lineas), 1)
        tot_row = last + 1
        if lineas:
            last = 5 + len(lineas)
            tot_row = last + 1
            ws.cell(row=tot_row, column=12, value="TOTALES").font = Font(name="Calibri", bold=True, size=10)
            ws.cell(row=tot_row, column=14, value=f"=SUM(N6:N{last})")
            ws.cell(row=tot_row, column=15, value=f"=SUM(O6:O{last})")
            for col in (14, 15):
                cell = ws.cell(row=tot_row, column=col)
                cell.fill = self.GREEN_FILL
                cell.font = Font(name="Calibri", bold=True, size=10)
                cell.border = self.THIN
            ws.cell(row=tot_row, column=15).number_format = '"$"#,##0.00'
            ws.cell(row=tot_row, column=14).number_format = "0.##"

            # Subtotales por material (bloque a la derecha del total)
            sub_row = tot_row + 2
            ws.cell(row=sub_row, column=1, value="Resumen por material").font = Font(
                name="Calibri", bold=True, size=9, color="1F4E79"
            )
            ws.cell(row=sub_row + 1, column=1, value="Material")
            ws.cell(row=sub_row + 1, column=2, value="Líneas")
            ws.cell(row=sub_row + 1, column=3, value="Gramos")
            ws.cell(row=sub_row + 1, column=4, value="Efectivo")
            for col in range(1, 5):
                ws.cell(row=sub_row + 1, column=col).font = Font(bold=True, size=8)
                ws.cell(row=sub_row + 1, column=col).fill = self.HEADER_FILL
                ws.cell(row=sub_row + 1, column=col).font = self.HEADER_FONT
                ws.cell(row=sub_row + 1, column=col).border = self.THIN

            from collections import defaultdict
            buckets: dict[str, list] = defaultdict(lambda: [0, 0.0, 0.0])
            for row in lineas:
                mat = str(row.get("material") or "—").upper()
                buckets[mat][0] += 1
                try:
                    buckets[mat][1] += float(row.get("total_gramos") or 0)
                except (TypeError, ValueError):
                    pass
                try:
                    buckets[mat][2] += float(row.get("efectivo") or 0)
                except (TypeError, ValueError):
                    pass
            rr = sub_row + 2
            for mat, (n, gr, ef) in sorted(buckets.items()):
                ws.cell(row=rr, column=1, value=mat).fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT)
                ws.cell(row=rr, column=2, value=n)
                ws.cell(row=rr, column=3, value=round(gr, 2))
                ws.cell(row=rr, column=4, value=round(ef, 2))
                ws.cell(row=rr, column=4).number_format = '"$"#,##0.00'
                for col in range(1, 5):
                    ws.cell(row=rr, column=col).border = self.THIN
                rr += 1

            # Pie de página / firmas
            pie = rr + 2
            ws.cell(row=pie, column=1, value="Vo.Bo. supervisor: ________________").font = Font(size=9)
            ws.cell(row=pie, column=6, value="Fecha de pago: ____ / ____ / ______").font = Font(size=9)
            ws.cell(row=pie + 1, column=1, value=(
                f"Documento generado por Fajos Piteados Central el {generado}. "
                "Cada trabajador firma en su fila al recibir el pago."
            )).font = Font(size=8, italic=True, color="666666")
            ws.merge_cells(start_row=pie + 1, start_column=1, end_row=pie + 1, end_column=12)

        widths = {
            "A": 22, "B": 7, "C": 11, "D": 14, "E": 9, "F": 7,
            "G": 6, "H": 6, "I": 6, "J": 6, "K": 6, "L": 6, "M": 6,
            "N": 10, "O": 11, "P": 12,
        }
        for col, w in widths.items():
            ws.column_dimensions[col].width = w

        ws.row_dimensions[1].height = 22
        ws.row_dimensions[2].height = 18
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.page_margins = PageMargins(left=0.35, right=0.35, top=0.4, bottom=0.5)
        ws.print_title_rows = "1:5"
        ws.oddFooter.center.text = f"Nómina formal {codigo_semana} · Emitido {generado}"
        ws.oddFooter.center.font = "Calibri"
        ws.oddFooter.center.size = 8

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
        def _pk(r):
            try:
                u = int(r.get("ubic") or 0)
            except (TypeError, ValueError):
                u = 0
            return (u, str(r.get("nombre") or "").upper(), str(r.get("folio") or "").upper())

        lineas = sorted(list(lineas), key=_pk)
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
            Paragraph(
                f"Semana: {codigo_semana}  ·  Emitido: "
                + __import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M"),
                styles["Normal"],
            ),
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
