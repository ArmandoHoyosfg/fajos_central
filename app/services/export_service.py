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
        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Formal"
        ws["A1"] = "Taller de Fajos Central — Nómina Formal"
        ws["A1"].font = Font(name="Calibri", bold=True, size=13, color="1F4E79")
        ws["A2"] = f"Semana: {codigo_semana}"

        headers = [h for _, h in self.COLUMNS] + ["Firma"]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=4, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center")

        for i, row in enumerate(lineas):
            r = 5 + i
            for col, (key, _) in enumerate(self.COLUMNS, 1):
                val = row.get(key)
                cell = ws.cell(row=r, column=col, value=float(val) if isinstance(val, Decimal) else val)
                cell.border = self.THIN
                cell.alignment = Alignment(horizontal="center")
                mat = str(row.get("material") or "").upper()
                fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else (self.ALT_FILL if i % 2 == 0 else None))
                if fill is not None:
                    cell.fill = fill
                if key == "efectivo" and val is not None:
                    cell.number_format = '$#,##0.00'
            # Firma vacía
            cell = ws.cell(row=r, column=len(self.COLUMNS) + 1, value="")
            cell.border = self.THIN

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
