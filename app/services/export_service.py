"""
Exportación multi-formato: Excel, CSV, PDF, JSON.
"""
from __future__ import annotations

import csv
import json
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any, Literal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.config import settings
from app.core.exceptions import ExportError, ValidationAppError
from app.core.logging_config import get_logger

logger = get_logger(__name__)

ExportFormat = Literal["xlsx", "csv", "pdf", "json"]


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"No serializable: {type(obj)}")


class ExportService:
    HEADER_FILL = PatternFill("solid", fgColor="1F4E79")
    HEADER_FONT = Font(name="Calibri", bold=True, size=10, color="FFFFFF")
    ALT_FILL = PatternFill("solid", fgColor="E8F4FD")
    MAT_FILLS = {
        "AG3": PatternFill("solid", fgColor="D6EAF8"),
        "AG4": PatternFill("solid", fgColor="D5F5E3"),
        "DOL": PatternFill("solid", fgColor="FCF3CF"),
        "DLO": PatternFill("solid", fgColor="FAD7A0"),
    }
    MAT_DEFAULT = PatternFill("solid", fgColor="E8DAEF")
    GREEN_FILL = PatternFill("solid", fgColor="C6EFCE")
    THIN = Border(
        left=Side(style="thin", color="808080"),
        right=Side(style="thin", color="808080"),
        top=Side(style="thin", color="808080"),
        bottom=Side(style="thin", color="808080"),
    )

    COLUMNS = [
        ("nombre", "Nombre"),
        ("ubic", "Ubic"),
        ("folio", "Folio"),
        ("modelo", "Modelo"),
        ("material", "Material"),
        ("tarifa_gr", "$/Gr"),
        ("gm_sab", "Sáb"),
        ("gm_dom", "Dom"),
        ("gm_lun", "Lun"),
        ("gm_mar", "Mar"),
        ("gm_mie", "Mié"),
        ("gm_jue", "Jue"),
        ("gm_vie", "Vie"),
        ("total_gramos", "Total Gr"),
        ("efectivo", "Efectivo"),
    ]

    def __init__(self):
        settings.export_dir.mkdir(parents=True, exist_ok=True)

    def export_produccion(
        self,
        lineas: list[dict],
        fmt: ExportFormat,
        *,
        codigo_semana: str = "",
        filename_stem: str = "nomina",
    ) -> tuple[bytes, str, str]:
        """
        Devuelve (contenido_bytes, media_type, filename).
        """
        fmt = fmt.lower()  # type: ignore
        if fmt not in ("xlsx", "csv", "pdf", "json"):
            raise ValidationAppError(
                f"Formato no soportado: {fmt}",
                details={"format": fmt, "allowed": ["xlsx", "csv", "pdf", "json"]},
            )
        try:
            if fmt == "xlsx":
                data = self._to_xlsx(lineas, codigo_semana)
                return data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", f"{filename_stem}.xlsx"
            if fmt == "csv":
                data = self._to_csv(lineas)
                return data, "text/csv; charset=utf-8", f"{filename_stem}.csv"
            if fmt == "json":
                data = self._to_json(lineas, codigo_semana)
                return data, "application/json", f"{filename_stem}.json"
            if fmt == "pdf":
                data = self._to_pdf(lineas, codigo_semana)
                return data, "application/pdf", f"{filename_stem}.pdf"
        except ExportError:
            raise
        except Exception as e:
            logger.exception("Error exportando a %s", fmt)
            raise ExportError(
                f"Fallo al exportar a {fmt}.",
                details={"format": fmt, "lineas": len(lineas)},
                cause=e,
            ) from e
        raise ValidationAppError(f"Formato no implementado: {fmt}")

    def _to_xlsx(self, lineas: list[dict], codigo_semana: str) -> bytes:
        from datetime import date, datetime
        from collections import defaultdict

        hoy = date.today()
        generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }

        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Formal"

        ws.merge_cells("A1:P1")
        ws["A1"] = "TALLER DE FAJOS CENTRAL"
        ws["A1"].font = Font(name="Calibri", bold=True, size=16, color="1F4E79")

        ws.merge_cells("A2:P2")
        ws["A2"] = "NÓMINA FORMAL SEMANAL — PRODUCCIÓN PLATA (PLT)"
        ws["A2"].font = Font(name="Calibri", bold=True, size=12, color="2E75B6")

        ws["A3"] = "Semana"
        ws["B3"] = codigo_semana or "—"
        ws["C3"] = "Mes"
        ws["D3"] = meses.get(hoy.month, "")
        ws["E3"] = "Año"
        ws["F3"] = hoy.year
        ws["G3"] = "Emitido"
        ws["H3"] = generado
        for col in range(1, 9):
            ws.cell(row=3, column=col).font = Font(name="Calibri", size=9, bold=(col % 2 == 1))

        ws["A4"] = "Material:"
        ws["A4"].font = Font(name="Calibri", size=8, italic=True, color="666666")
        for col, (code, fill) in enumerate(self.MAT_FILLS.items(), start=2):
            cell = ws.cell(row=4, column=col, value=code)
            cell.fill = fill
            cell.font = Font(name="Calibri", bold=True, size=8)
            cell.border = self.THIN

        headers = [h for _, h in self.COLUMNS] + ["Firma"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        data_rows = [
            r for r in lineas
            if r.get("folio") or r.get("modelo") or float(r.get("total_gramos") or 0) > 0
        ]
        data_rows.sort(
            key=lambda r: (
                str(r.get("material") or "").upper(),
                int(r.get("ubic") or 0) if str(r.get("ubic") or "").replace(".", "").isdigit() else 0,
                str(r.get("nombre") or "").upper(),
            )
        )

        for i, row in enumerate(data_rows):
            r = 6 + i
            mat = str(row.get("material") or "").upper()
            fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else None)
            for col, (key, _) in enumerate(self.COLUMNS, 1):
                val = row.get(key)
                if isinstance(val, Decimal):
                    val = float(val)
                if val is not None and key in (
                    "tarifa_gr", "gm_sab", "gm_dom", "gm_lun", "gm_mar",
                    "gm_mie", "gm_jue", "gm_vie", "total_gramos", "efectivo",
                ):
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
                if key == "efectivo" and val is not None:
                    cell.number_format = '"$"#,##0.00'
            firm = ws.cell(row=r, column=len(self.COLUMNS) + 1, value="")
            firm.border = self.THIN
            if fill is not None:
                firm.fill = fill

        last = 5 + len(data_rows)
        if data_rows:
            tot = last + 1
            ws.cell(row=tot, column=13, value="TOTALES").font = Font(bold=True)
            ws.cell(row=tot, column=14, value=f"=SUM(N6:N{last})")
            ws.cell(row=tot, column=15, value=f"=SUM(O6:O{last})")
            ws.cell(row=tot, column=14).fill = self.GREEN_FILL
            ws.cell(row=tot, column=15).fill = self.GREEN_FILL
            ws.cell(row=tot, column=15).number_format = '"$"#,##0.00'
            ws.cell(row=tot, column=14).font = Font(bold=True)
            ws.cell(row=tot, column=15).font = Font(bold=True)

            sub = tot + 2
            ws.cell(row=sub, column=1, value="Resumen por material").font = Font(bold=True, color="1F4E79")
            buckets: dict = defaultdict(lambda: [0, 0.0, 0.0])
            for row in data_rows:
                mat = str(row.get("material") or "—").upper()
                buckets[mat][0] += 1
                buckets[mat][1] += float(row.get("total_gramos") or 0)
                buckets[mat][2] += float(row.get("efectivo") or 0)
            ws.cell(row=sub + 1, column=1, value="Material")
            ws.cell(row=sub + 1, column=2, value="Líneas")
            ws.cell(row=sub + 1, column=3, value="Gramos")
            ws.cell(row=sub + 1, column=4, value="Efectivo")
            for c in range(1, 5):
                cell = ws.cell(row=sub + 1, column=c)
                cell.fill = self.HEADER_FILL
                cell.font = self.HEADER_FONT
                cell.border = self.THIN
            rr = sub + 2
            for mat, (n, gr, ef) in sorted(buckets.items()):
                ws.cell(row=rr, column=1, value=mat).fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT)
                ws.cell(row=rr, column=2, value=n)
                ws.cell(row=rr, column=3, value=round(gr, 2))
                ws.cell(row=rr, column=4, value=round(ef, 2)).number_format = '"$"#,##0.00'
                for c in range(1, 5):
                    ws.cell(row=rr, column=c).border = self.THIN
                rr += 1
            pie = rr + 1
            ws.cell(row=pie, column=1, value="Vo.Bo. supervisor: ________________")
            ws.cell(row=pie, column=6, value="Fecha de pago: ____ / ____ / ______")
            ws.cell(row=pie + 1, column=1, value=(
                f"Generado por Fajos Piteados Central el {generado}. Firma en cada fila al pagar."
            )).font = Font(size=8, italic=True, color="666666")

        widths = {
            "A": 22, "B": 7, "C": 11, "D": 14, "E": 9, "F": 7,
            "G": 6, "H": 6, "I": 6, "J": 6, "K": 6, "L": 6, "M": 6,
            "N": 10, "O": 11, "P": 12,
        }
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:5"
        try:
            ws.oddFooter.center.text = f"Nómina formal {codigo_semana} · {generado}"
        except Exception:
            pass

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _to_csv(self, lineas: list[dict]) -> bytes:
        sio = StringIO()
        writer = csv.writer(sio)
        writer.writerow([h for _, h in self.COLUMNS])
        for row in lineas:
            writer.writerow([
                float(row[k]) if isinstance(row.get(k), Decimal) else row.get(k, "")
                for k, _ in self.COLUMNS
            ])
        return sio.getvalue().encode("utf-8-sig")

    def _to_json(self, lineas: list[dict], codigo_semana: str) -> bytes:
        payload = {
            "semana": codigo_semana,
            "total_lineas": len(lineas),
            "lineas": lineas,
        }
        return json.dumps(payload, default=_json_default, ensure_ascii=False, indent=2).encode("utf-8")

    def _to_pdf(self, lineas: list[dict], codigo_semana: str) -> bytes:
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.units import mm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        except ImportError as e:
            raise ExportError(
                "Falta la librería reportlab para exportar PDF.",
                details={"hint": "pip install reportlab"},
                cause=e,
            ) from e

        mat_colors = {
            "AG3": colors.HexColor("#D6EAF8"),
            "AG4": colors.HexColor("#D5F5E3"),
            "DOL": colors.HexColor("#FCF3CF"),
            "DLO": colors.HexColor("#FAD7A0"),
        }
        default_row = colors.HexColor("#F5EEF8")

        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(letter),
            leftMargin=8 * mm,
            rightMargin=8 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm,
            title=f"Nomina formal {codigo_semana}",
        )
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "T", parent=styles["Title"], fontSize=14, textColor=colors.HexColor("#1F4E79"), spaceAfter=4,
        )
        sub_style = ParagraphStyle(
            "S", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#555555"),
        )
        story = []
        story.append(Paragraph("Taller de Fajos Central — NÓMINA FORMAL (PAGO)", title_style))
        story.append(Paragraph(
            f"Semana: <b>{codigo_semana}</b> · Orden: Ubic → Nombre · Color = material · Espacio firma",
            sub_style,
        ))
        story.append(Spacer(1, 6))

        # Columnas compactas para formal
        keys = [
            ("nombre", "Nombre"), ("ubic", "Ubic"), ("folio", "Folio"),
            ("modelo", "Modelo"), ("material", "Mat"), ("tarifa_gr", "$/Gr"),
            ("gm_sab", "Sáb"), ("gm_dom", "Dom"), ("gm_lun", "Lun"),
            ("gm_mar", "Mar"), ("gm_mie", "Mié"), ("gm_jue", "Jue"), ("gm_vie", "Vie"),
            ("total_gramos", "Total Gr"), ("efectivo", "Efectivo"),
        ]
        header = [h for _, h in keys] + ["Firma"]
        data = [header]
        row_mats: list[str] = [""]
        total_gr = 0.0
        total_ef = 0.0
        for row in lineas:
            mat = str(row.get("material") or "").upper()
            row_mats.append(mat)
            cells = []
            for k, _ in keys:
                val = row.get(k)
                if isinstance(val, Decimal):
                    val = float(val)
                if val is None or val == "" or val == 0:
                    cells.append("")
                elif k == "efectivo":
                    cells.append(f"${float(val):,.2f}")
                    total_ef += float(val)
                elif k == "total_gramos":
                    cells.append(f"{float(val):g}")
                    total_gr += float(val)
                elif k in ("tarifa_gr",) or k.startswith("gm_"):
                    cells.append(f"{float(val):g}" if isinstance(val, (int, float)) else str(val))
                else:
                    cells.append(str(val))
            cells.append("")  # firma
            data.append(cells)

        data.append(
            ["", "", "", "", "", "", "", "", "", "", "", "", "TOTALES", f"{total_gr:g}", f"${total_ef:,.2f}", ""]
        )

        col_widths = [72, 28, 42, 48, 28, 28, 24, 24, 24, 24, 24, 24, 24, 36, 48, 40]
        table = Table(data, repeatRows=1, colWidths=col_widths)
        style_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#888888")),
            ("ALIGN", (1, 0), (-1, -1), "CENTER"),
            ("ALIGN", (0, 1), (0, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#C8E6C9")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
        for i, mat in enumerate(row_mats):
            if i == 0:
                continue
            bg = mat_colors.get(mat, default_row if mat else colors.white)
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), bg))
        table.setStyle(TableStyle(style_cmds))
        story.append(table)
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            "Firma del trabajador en la columna derecha. Documento generado por Fajos Piteados Central.",
            sub_style,
        ))
        doc.build(story)
        return buf.getvalue()
