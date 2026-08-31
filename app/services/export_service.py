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

def linea_tiene_gramos(row: dict) -> bool:
    """True si la línea tiene al menos un día con gramos > 0 (o total_gramos > 0)."""
    try:
        if float(row.get("total_gramos") or 0) > 0:
            return True
    except (TypeError, ValueError):
        pass
    for col in ("gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"):
        try:
            if float(row.get(col) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False




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
        # Nómina formal/limpia: excluir filas sin gramos en ningún día
        lineas = [r for r in lineas if linea_tiene_gramos(r)]
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

        # Solo filas con gramos en al menos un día (nómina limpia para imprimir)
        data_rows = [r for r in lineas if linea_tiene_gramos(r)]
        def _pk(r):
            try:
                u = int(float(r.get("ubic") or 0))
            except (TypeError, ValueError):
                u = 0
            return (u, str(r.get("nombre") or "").upper(), str(r.get("folio") or "").upper())

        data_rows.sort(key=_pk)

        # Columnas: A nombre … F $/Gr, G–M días, N Total Gr, O Efectivo
        # N = SUM(días)  ·  O = N * F
        for i, row in enumerate(data_rows):
            r = 6 + i
            mat = str(row.get("material") or "").upper()
            fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else None)
            for col, (key, _) in enumerate(self.COLUMNS, 1):
                if key == "total_gramos":
                    # Suma automática de gramos del sábado al viernes
                    val = f"=IF(SUM(G{r}:M{r})=0,\"\",SUM(G{r}:M{r}))"
                elif key == "efectivo":
                    # Efectivo = Total Gr × $/Gr
                    val = f"=IF(OR(N{r}=\"\",N{r}=0,F{r}=\"\"),\"\",ROUND(N{r}*F{r},2))"
                else:
                    val = row.get(key)
                    if isinstance(val, Decimal):
                        val = float(val)
                    if val is not None and key in (
                        "tarifa_gr", "gm_sab", "gm_dom", "gm_lun", "gm_mar",
                        "gm_mie", "gm_jue", "gm_vie",
                    ):
                        try:
                            if float(val) == 0:
                                val = None
                        except (TypeError, ValueError):
                            pass
                cell = ws.cell(row=r, column=col, value=val if val is not None else "")
                cell.border = self.THIN
                cell.alignment = Alignment(horizontal="center" if col > 1 else "left")
                if fill is not None:
                    cell.fill = fill
                if key == "efectivo":
                    cell.number_format = '"$"#,##0.00'
                if key in ("total_gramos", "tarifa_gr") or key.startswith("gm_"):
                    cell.number_format = "0.0"
            firm = ws.cell(row=r, column=len(self.COLUMNS) + 1, value="")
            firm.border = self.THIN
            if fill is not None:
                firm.fill = fill

        last = 5 + len(data_rows)
        if data_rows:
            tot = last + 1
            ws.cell(row=tot, column=13, value="TOTALES").font = Font(bold=True)
            # Sumas automáticas de columnas calculadas
            c_n = ws.cell(row=tot, column=14, value=f"=SUM(N6:N{last})")
            c_o = ws.cell(row=tot, column=15, value=f"=SUM(O6:O{last})")
            c_n.fill = self.GREEN_FILL
            c_o.fill = self.GREEN_FILL
            c_o.number_format = '"$"#,##0.00'
            c_n.number_format = "0.0"
            c_n.font = Font(bold=True)
            c_o.font = Font(bold=True)
            from openpyxl.utils import get_column_letter as _gcl
            for col in range(7, 14):  # sumar cada día G–M
                letter = _gcl(col)
                cell = ws.cell(row=tot, column=col, value=f"=SUM({letter}6:{letter}{last})")
                cell.font = Font(bold=True, size=9)
                cell.number_format = "0.0"

            sub = tot + 2
            ws.cell(row=sub, column=1, value="Resumen por material (fórmulas SUMIF)").font = Font(bold=True, color="1F4E79")
            mats = sorted({str(row.get("material") or "—").upper() for row in data_rows})
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
            for mat in mats:
                # Escapar comillas en material para fórmula
                mat_esc = mat.replace('"', '""')
                ws.cell(row=rr, column=1, value=mat).fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT)
                ws.cell(row=rr, column=2, value=f'=COUNTIF($E$6:$E${last},A{rr})')
                ws.cell(row=rr, column=3, value=f'=SUMIF($E$6:$E${last},A{rr},$N$6:$N${last})')
                ws.cell(row=rr, column=4, value=f'=SUMIF($E$6:$E${last},A{rr},$O$6:$O${last})')
                ws.cell(row=rr, column=3).number_format = "0.0"
                ws.cell(row=rr, column=4).number_format = '"$"#,##0.00'
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


    # ---- Taller / Pita / Resumen completo ----

    TLL_COLUMNS = [
        ("nombre", "Nombre"),
        ("ubic", "Ubic"),
        ("puesto", "Puesto"),
        ("sueldo", "Sueldo"),
        ("extras", "Extras"),
        ("total", "Total"),
        ("firma", "Firma"),
    ]
    PIT_COLUMNS = [
        ("nombre", "Nombre"),
        ("ubic", "Ubic"),
        ("modelo", "Modelo"),
        ("folio", "Folio"),
        ("material", "Material"),
        ("producto", "Producto"),
        ("pitas", "Pitas"),
        ("efectivo", "Efectivo"),
        ("firma", "Firma"),
    ]


    def export_trabajadores(
        self,
        rows: list[dict],
        *,
        filename_stem: str = "trabajadores",
        solo_activos: bool | None = None,
    ) -> tuple[bytes, str, str]:
        """Catálogo de trabajadores a Excel."""
        try:
            data = self._xlsx_trabajadores(rows, solo_activos=solo_activos)
            return (
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{filename_stem}.xlsx",
            )
        except Exception as e:
            logger.exception("Error exportando trabajadores")
            raise ExportError("Fallo al exportar trabajadores.", cause=e) from e

    def _xlsx_trabajadores(self, rows: list[dict], *, solo_activos: bool | None = None) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Trabajadores"
        headers = [
            ("id", "ID"),
            ("nombre_mostrar", "Nombre"),
            ("nombre_completo", "Nombre completo"),
            ("ubic", "Ubic"),
            ("tipo", "Tipo"),
            ("puesto", "Puesto"),
            ("sueldo_modo", "Sueldo modo"),
            ("sueldo_base", "Sueldo base"),
            ("activo", "Activo"),
            ("fecha_incorporacion", "Incorporación"),
            ("codigo_qr", "Código QR"),
            ("notas", "Notas"),
        ]
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
        title = "Catálogo de trabajadores — Fajos Piteados Central"
        if solo_activos is True:
            title += " (solo activos)"
        elif solo_activos is False:
            title += " (todos)"
        ws.cell(1, 1, title)
        ws.cell(1, 1).font = Font(name="Calibri", bold=True, size=12, color="1F4E79")
        for col, (_, label) in enumerate(headers, 1):
            cell = ws.cell(2, col, label)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = Alignment(horizontal="center", wrap_text=True)
            cell.border = self.THIN
        for i, r in enumerate(rows):
            row_i = 3 + i
            vals = [
                r.get("id"),
                r.get("nombre_mostrar"),
                r.get("nombre_completo"),
                r.get("ubic"),
                r.get("tipo"),
                r.get("puesto"),
                r.get("sueldo_modo") or "",
                r.get("sueldo_base") if r.get("sueldo_base") is not None else "",
                "Sí" if r.get("activo") else "No",
                r.get("fecha_incorporacion") or "",
                r.get("codigo_qr") or "",
                r.get("notas") or "",
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row_i, col, v)
                cell.border = self.THIN
                if i % 2:
                    cell.fill = self.ALT_FILL
                if col in (1, 4):
                    cell.alignment = Alignment(horizontal="center")
        widths = [6, 22, 28, 8, 10, 14, 12, 12, 8, 14, 12, 24]
        for i, w in enumerate(widths, 1):
            from openpyxl.utils import get_column_letter
            ws.column_dimensions[get_column_letter(i)].width = w
        ws.auto_filter.ref = f"A2:{get_column_letter(len(headers))}{2 + max(len(rows), 1)}"
        ws.freeze_panes = "A3"
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def export_nomina_taller(
        self,
        lineas: list[dict],
        *,
        codigo_semana: str = "",
        filename_stem: str = "nomina_taller",
        resumen: dict | None = None,
    ) -> tuple[bytes, str, str]:
        """Excel formal Taller: Nombre, Ubic, Puesto, Sueldo, Extras, Total, Firma."""
        try:
            data = self._xlsx_taller(lineas, codigo_semana, resumen)
            return (
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{filename_stem}.xlsx",
            )
        except Exception as e:
            logger.exception("Error exportando taller")
            raise ExportError("Fallo al exportar nómina taller.", cause=e) from e

    def export_nomina_pita(
        self,
        lineas: list[dict],
        *,
        codigo_semana: str = "",
        filename_stem: str = "nomina_pita",
        resumen: dict | None = None,
    ) -> tuple[bytes, str, str]:
        """Excel formal Pita: Nombre, Ubic, Modelo, Folio, Material, Producto, Pitas, Efectivo, Firma."""
        try:
            data = self._xlsx_pita(lineas, codigo_semana, resumen)
            return (
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{filename_stem}.xlsx",
            )
        except Exception as e:
            logger.exception("Error exportando pita")
            raise ExportError("Fallo al exportar nómina pita.", cause=e) from e

    def export_resumen_tres_nominas(
        self,
        *,
        codigo_semana: str,
        nomina_taller: float,
        nomina_plata: float,
        nomina_pita: float,
        filename_stem: str = "resumen_nominas",
    ) -> tuple[bytes, str, str]:
        """Hoja de totales tipo captura: Taller | Plata | Pita | Total."""
        try:
            data = self._xlsx_resumen_totales(
                codigo_semana, nomina_taller, nomina_plata, nomina_pita
            )
            return (
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{filename_stem}.xlsx",
            )
        except Exception as e:
            logger.exception("Error exportando resumen")
            raise ExportError("Fallo al exportar resumen.", cause=e) from e

    def _xlsx_taller(
        self, lineas: list[dict], codigo_semana: str, resumen: dict | None
    ) -> bytes:
        from datetime import datetime
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Taller"
        ws["A1"] = "Taller de Fajos Central — NÓMINA TALLER (TLL)"
        ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
        ws.merge_cells("A1:G1")
        ws["A2"] = (
            f"Semana: {codigo_semana}    |    Sueldo + extras · Torcedores = pitas × $3.20    |    "
            f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        ws["A2"].font = Font(name="Calibri", size=10, color="666666")
        ws.merge_cells("A2:G2")

        headers = [c[1] for c in self.TLL_COLUMNS]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(4, col, h)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
            cell.border = self.THIN

        def _is_torc(r):
            p = str(r.get("puesto") or "").lower()
            return "torcedor" in p or bool(r.get("es_torcedor"))

        normales = [r for r in lineas if not _is_torc(r)]
        torcedores = [r for r in lineas if _is_torc(r)]
        key = lambda x: (int(x.get("ubic") or 0), str(x.get("nombre") or ""))
        normales = sorted(normales, key=key)
        torcedores = sorted(torcedores, key=key)

        money = '"$"#,##0.00'
        row_i = 5
        first_data = 5
        data_rows_idx = []

        def _write_row(r):
            nonlocal row_i
            sueldo = float(r.get("sueldo") or 0)
            extras = float(r.get("extras") or 0)
            vals = [
                r.get("nombre") or "",
                r.get("ubic"),
                r.get("puesto") or "",
                sueldo if sueldo else None,
                extras if extras else 0,
                f'=IF(AND(OR(D{row_i}="",D{row_i}=0),OR(E{row_i}="",E{row_i}=0)),"",IF(D{row_i}="",0,D{row_i})+IF(E{row_i}="",0,E{row_i}))',
                "______" if not r.get("firmado") else "✓",
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row_i, col, v if v is not None else "")
                cell.border = self.THIN
                if col in (4, 5, 6):
                    cell.number_format = money
                if row_i % 2 == 0:
                    cell.fill = self.ALT_FILL
            data_rows_idx.append(row_i)
            row_i += 1

        for r in normales:
            _write_row(r)

        if torcedores:
            # línea en blanco + subtítulo
            row_i += 1
            cell = ws.cell(row_i, 1, "Torcedores (pago por pitas × $3.20)")
            cell.font = Font(name="Calibri", bold=True, size=11, color="1F4E79")
            ws.merge_cells(start_row=row_i, start_column=1, end_row=row_i, end_column=7)
            row_i += 1
            for r in torcedores:
                _write_row(r)

        last_data = data_rows_idx[-1] if data_rows_idx else row_i - 1
        first_data = data_rows_idx[0] if data_rows_idx else 5
        row_i = last_data + 2
        ws.cell(row_i, 3, "TOTAL TALLER").font = Font(bold=True, size=11)
        if data_rows_idx:
            # SUM de cada bloque: usar lista de celdas
            for col, letter in [(4, "D"), (5, "E"), (6, "F")]:
                refs = ",".join(f"{letter}{i}" for i in data_rows_idx)
                cell = ws.cell(row_i, col, value=f"=SUM({refs})" if len(data_rows_idx) <= 50 else f"=SUM({letter}{first_data}:{letter}{last_data})")
                cell.font = Font(bold=True)
                cell.number_format = money
                cell.fill = PatternFill("solid", fgColor="C6EFCE")
                cell.border = self.THIN
        else:
            for col in (4, 5, 6):
                cell = ws.cell(row_i, col, 0)
                cell.number_format = money
                cell.fill = PatternFill("solid", fgColor="C6EFCE")

        if resumen:
            row_i += 2
            ws.cell(row_i, 1, "RESUMEN NÓMINAS").font = Font(bold=True, size=11, color="1F4E79")
            row_i += 1
            for label, key in (
                ("Nómina Taller", "nomina_taller"),
                ("Nómina Plata", "nomina_plata"),
                ("Nómina Pita", "nomina_pita"),
            ):
                ws.cell(row_i, 1, label)
                cell = ws.cell(row_i, 2, float(resumen.get(key) or 0))
                cell.number_format = money
                row_i += 1
            tot = sum(float(resumen.get(k) or 0) for k in ("nomina_taller", "nomina_plata", "nomina_pita"))
            ws.cell(row_i, 1, "GRAN TOTAL").font = Font(bold=True)
            cell = ws.cell(row_i, 2, tot)
            cell.font = Font(bold=True)
            cell.number_format = money
            cell.fill = PatternFill("solid", fgColor="C6EFCE")

        for col, w in enumerate([28, 8, 14, 12, 10, 12, 10], 1):
            ws.column_dimensions[get_column_letter(col)].width = w
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "4:4"
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()


    def _xlsx_pita(
        self, lineas: list[dict], codigo_semana: str, resumen: dict | None
    ) -> bytes:
        from datetime import datetime
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Pita"
        ws["A1"] = "Taller de Fajos Central — NÓMINA PITA (PIT)"
        ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
        ws.merge_cells("A1:I1")
        ws["A2"] = (
            f"Semana: {codigo_semana}    |    Material tipo PITA NxN · Producto (Cinturón) · Pitas suele vacío    |    "
            f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        ws["A2"].font = Font(name="Calibri", size=10, color="666666")
        ws.merge_cells("A2:I2")

        headers = [c[1] for c in self.PIT_COLUMNS]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(4, col, h)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
            cell.border = self.THIN

        money = '"$"#,##0.00'
        pita_fill = PatternFill("solid", fgColor="FCE4D6")
        row_i = 5
        first_data = 5
        for r in sorted(lineas, key=lambda x: (int(x.get("ubic") or 0), str(x.get("nombre") or ""))):
            ef = float(r.get("efectivo") or 0)
            pitas_v = r.get("pitas")
            vals = [
                r.get("nombre") or "",
                r.get("ubic"),
                r.get("modelo") or "",
                r.get("folio") or "",
                r.get("material") or "",
                r.get("producto") or "Cinturón",
                pitas_v if pitas_v is not None else "",
                ef if ef else None,
                "______" if not r.get("firmado") else "✓",
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row_i, col, v if v is not None else "")
                cell.border = self.THIN
                if col in (7, 8) and (isinstance(v, (int, float)) or col == 8):
                    cell.number_format = money if col == 8 else "0.0"
                mat = str(r.get("material") or "").upper()
                if "PITA" in mat:
                    cell.fill = pita_fill
                elif row_i % 2 == 0:
                    cell.fill = self.ALT_FILL
            row_i += 1

        last_data = row_i - 1
        row_i += 1
        ws.cell(row_i, 7, "TOTAL PITA").font = Font(bold=True, size=11)
        if last_data >= first_data:
            cell = ws.cell(row_i, 8, value=f"=SUM(H{first_data}:H{last_data})")
        else:
            cell = ws.cell(row_i, 8, 0)
        cell.font = Font(bold=True)
        cell.fill = self.GREEN_FILL
        cell.number_format = money
        cell.border = self.THIN

        widths = [18, 8, 14, 12, 14, 12, 10, 12, 10]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        ws.print_title_rows = "4:4"
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.oddFooter.center.text = f"Nómina Pita {codigo_semana}"

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def _xlsx_resumen_totales(
        self,
        codigo_semana: str,
        nomina_taller: float,
        nomina_plata: float,
        nomina_pita: float,
    ) -> bytes:
        from datetime import datetime
        from openpyxl.utils import get_column_letter

        wb = Workbook()
        ws = wb.active
        ws.title = "Resumen"
        ws["A1"] = "Taller de Fajos Central — RESUMEN DE NÓMINAS"
        ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
        ws["A2"] = f"Semana: {codigo_semana}    |    {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        money = '"$"#,##0.00'
        rows = [
            ("Nómina Taller", float(nomina_taller or 0)),
            ("Nómina Plata", float(nomina_plata or 0)),
            ("Nómina Pita", float(nomina_pita or 0)),
        ]
        r = 4
        for label, amount in rows:
            ws.cell(r, 1, label).font = Font(size=12)
            cell = ws.cell(r, 2, amount)
            cell.number_format = money
            cell.font = Font(size=12)
            r += 1
        ws.cell(r, 1, "Total Nómina").font = Font(bold=True, size=13)
        cell = ws.cell(r, 2, f"=SUM(B4:B{r-1})")
        cell.font = Font(bold=True, size=13)
        cell.fill = self.GREEN_FILL
        cell.number_format = money
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 14
        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()




    def export_suministro_diario(
        self,
        lineas: list[dict],
        *,
        fecha_iso: str = "",
        label_dia: str = "",
        codigo_semana: str = "",
        filas_extra_por_trabajador: int = 2,
        n_avances: int = 4,
        papel: str = "letter",
        tema: str = "material",
        fuente: str = "normal",
        mostrar_modelo: bool = True,
        mostrar_mat: bool = True,
        mostrar_obs: bool = True,
        mostrar_folio: bool = True,
        generico: bool = False,
        reps_por_trabajador: int = 3,
    ) -> tuple[bytes, str, str]:
        """
        Hoja de SUMINISTRO del día (estilo papel, vertical).
        - generico=True: solo UBIC+NOMBRE rellenos; resto en blanco;
          cada trabajador se repite reps_por_trabajador veces.
        """
        data = self._to_xlsx_suministro_diario(
            lineas,
            fecha_iso=fecha_iso,
            label_dia=label_dia,
            codigo_semana=codigo_semana,
            filas_extra_por_trabajador=filas_extra_por_trabajador,
            n_avances=n_avances,
            papel=papel,
            tema=tema,
            fuente=fuente,
            mostrar_modelo=mostrar_modelo,
            mostrar_mat=mostrar_mat,
            mostrar_obs=mostrar_obs,
            mostrar_folio=mostrar_folio,
            generico=generico,
            reps_por_trabajador=reps_por_trabajador,
        )
        stem = f"suministro_{fecha_iso or 'hoy'}"
        return (
            data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{stem}.xlsx",
        )

    def _to_xlsx_suministro_diario(
        self,
        lineas: list[dict],
        *,
        fecha_iso: str,
        label_dia: str,
        codigo_semana: str,
        filas_extra_por_trabajador: int = 2,
        n_avances: int = 4,
        papel: str = "letter",
        tema: str = "material",
        fuente: str = "normal",
        mostrar_modelo: bool = True,
        mostrar_mat: bool = True,
        mostrar_obs: bool = True,
        mostrar_folio: bool = True,
        generico: bool = False,
        reps_por_trabajador: int = 3,
    ) -> bytes:
        from collections import OrderedDict
        from datetime import date, datetime
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
        from io import BytesIO

        hoy = date.today()
        try:
            if fecha_iso and len(fecha_iso.split("-")) == 3:
                y, m, d = fecha_iso.split("-")
                fecha_txt = f"{int(d):02d}-{int(m):02d}-{y[2:]}"
            else:
                fecha_txt = hoy.strftime("%d-%m-%y")
        except Exception:
            fecha_txt = hoy.strftime("%d-%m-%y")

        # Hasta 10 columnas de avance (Av1…Av10); no se recortan por columnas opcionales
        n_avances = max(2, min(10, int(n_avances or 4)))
        font_sizes = {
            "muy_chica": 8, "chica": 9, "normal": 11,
            "grande": 13, "muy_grande": 15,
        }
        fsize = font_sizes.get((fuente or "normal").lower(), 11)

        thin = Border(
            left=Side(style="thin", color="000000"),
            right=Side(style="thin", color="000000"),
            top=Side(style="thin", color="000000"),
            bottom=Side(style="thin", color="000000"),
        )
        header_fill = PatternFill("solid", fgColor="1F4E79")
        header_font = Font(name="Calibri", bold=True, color="FFFFFF", size=fsize)
        title_font = Font(name="Calibri", bold=True, size=fsize + 5, color="1F4E79")
        sub_font = Font(name="Calibri", bold=True, size=fsize + 1, color="1F4E79")
        body_font = Font(name="Calibri", size=fsize)
        blank_fill = PatternFill("solid", fgColor="FFFDE7")
        mat_fills = {
            "AG3": PatternFill("solid", fgColor="E3F2FD"),
            "AG4": PatternFill("solid", fgColor="E8F5E9"),
            "DOL": PatternFill("solid", fgColor="FFF8E1"),
            "DLO": PatternFill("solid", fgColor="FCE4EC"),
        }
        tema_l = (tema or "material").lower()
        use_mat_colors = tema_l == "material"
        claro = tema_l in ("claro", "ahorro", "blanco")
        # Temas que gastan más de un color concreto (tóner/tinta)
        theme_row_fill = {
            "cian": PatternFill("solid", fgColor="B3E5FC"),      # más cian/azul
            "magenta": PatternFill("solid", fgColor="F8BBD0"),   # más magenta
            "amarillo": PatternFill("solid", fgColor="FFF59D"),  # más amarillo
            "negro": PatternFill("solid", fgColor="E0E0E0"),     # gris (más negro al imprimir bordes/texto)
            "verde": PatternFill("solid", fgColor="C8E6C9"),
        }.get(tema_l)

        def _pk(r):
            try:
                u = int(float(r.get("ubic") or 0))
            except (TypeError, ValueError):
                u = 0
            return (u, str(r.get("nombre") or "").upper(), str(r.get("folio") or "").upper())

        data_rows = sorted(list(lineas or []), key=_pk)
        groups: OrderedDict[tuple, list] = OrderedDict()
        for r in data_rows:
            try:
                u = int(float(r.get("ubic") or 0))
            except (TypeError, ValueError):
                u = 0
            key = (str(r.get("nombre") or "").strip().upper(), u)
            groups.setdefault(key, []).append(r)

        # Modo genérico: un trabajador = N filas solo con ubic+nombre
        generico = bool(generico)
        reps = max(1, min(12, int(reps_por_trabajador or 3)))
        if generico:
            # en genérico las columnas de folio/modelo/mat se dejan en blanco
            # (pueden mostrarse vacías para anotar a mano)
            pass

        # Column layout: UBIC NOMBRE [FOLIO] [MODELO] [MAT] Av… TOTAL [OBS]
        headers = ["UBIC", "NOMBRE"]
        if mostrar_folio:
            headers.append("FOLIO")
        if mostrar_modelo:
            headers.append("MODELO")
        if mostrar_mat:
            headers.append("MAT")
        av_start = len(headers) + 1
        for i in range(1, n_avances + 1):
            headers.append(f"Av{i}")
        headers.append("TOTAL")
        tot_col = len(headers)
        if mostrar_obs:
            headers.append("OBSERVACIONES")
        n_cols = len(headers)

        wb = Workbook()
        ws = wb.active
        ws.title = "Suministro"

        last_letter = get_column_letter(n_cols)
        ws.merge_cells(f"A1:{last_letter}1")
        ws["A1"] = "TALLER DE FAJOS CENTRAL — SUMINISTRO DIARIO"
        ws["A1"].font = title_font

        ws.merge_cells(f"A2:{last_letter}2")
        ws["A2"] = (
            f"FECHA: {fecha_txt}    DÍA: {(label_dia or '').upper()}    "
            f"SEMANA: {codigo_semana or '—'}    "
            f"(No anotar fecha ni día; ya van impresos)"
        )
        ws["A2"].font = sub_font

        ws.merge_cells(f"A3:{last_letter}3")
        ws["A3"] = (
            f"Anota solo los GRAMOS del día en Av1–Av{n_avances} (se suman). "
            "Las filas amarillas son para un FOLIO NUEVO del mismo trabajador."
        )
        ws["A3"].font = Font(name="Calibri", italic=True, size=max(8, fsize - 1), color="555555")

        for c, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=c, value=h)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin

        row_i = 6
        first_data = 6

        def _write_row(nombre, ubic, folio, modelo, material, is_blank=False, force_blank_meta=False):
            nonlocal row_i
            # force_blank_meta: modo genérico → folio/modelo/mat vacíos
            if force_blank_meta:
                folio = modelo = material = ""
            vals = [ubic, nombre]
            if mostrar_folio:
                vals.append("" if force_blank_meta else (folio or ""))
            if mostrar_modelo:
                vals.append("" if force_blank_meta else (modelo or ""))
            if mostrar_mat:
                vals.append("" if force_blank_meta else (material or ""))
            for c, v in enumerate(vals, 1):
                cell = ws.cell(row=row_i, column=c, value=v if v is not None else "")
                cell.border = thin
                cell.font = body_font
                cell.alignment = Alignment(vertical="center")
            for c in range(av_start, av_start + n_avances):
                cell = ws.cell(row=row_i, column=c, value="")
                cell.border = thin
            av_first = get_column_letter(av_start)
            av_last = get_column_letter(av_start + n_avances - 1)
            cell = ws.cell(
                row=row_i,
                column=tot_col,
                value=f'=IF(SUM({av_first}{row_i}:{av_last}{row_i})=0,"",SUM({av_first}{row_i}:{av_last}{row_i}))',
            )
            cell.border = thin
            cell.number_format = "0.0"
            cell.font = body_font
            if mostrar_obs:
                cell = ws.cell(row=row_i, column=n_cols, value="")
                cell.border = thin
            fill = None
            if is_blank:
                fill = blank_fill
            elif claro:
                fill = None
            elif use_mat_colors and not force_blank_meta:
                fill = mat_fills.get(str(material or "").upper())
            elif theme_row_fill is not None:
                fill = theme_row_fill
            if fill:
                for c in range(1, n_cols + 1):
                    ws.cell(row=row_i, column=c).fill = fill
            row_i += 1

        if not groups:
            ws.cell(row=6, column=1, value="(Sin trabajos activos en la semana actual)")
            row_i = 7
        else:
            for (nombre_key, ubic), items in groups.items():
                display_nombre = items[0].get("nombre") or nombre_key
                if generico:
                    for _ in range(reps):
                        _write_row(
                            display_nombre, ubic, "", "", "",
                            is_blank=False, force_blank_meta=True,
                        )
                else:
                    for item in items:
                        _write_row(
                            display_nombre,
                            ubic,
                            item.get("folio"),
                            item.get("modelo"),
                            item.get("material"),
                            is_blank=False,
                        )
                    n_extra = max(0, int(filas_extra_por_trabajador or 0))
                    for _ in range(n_extra):
                        _write_row(display_nombre, ubic, "", "", "", is_blank=True)

        last = row_i - 1
        if last >= first_data:
            tot = last + 1
            ws.cell(row=tot, column=3, value="TOTAL DÍA").font = Font(bold=True, size=fsize)
            for col in range(av_start, tot_col + 1):
                letter = get_column_letter(col)
                cell = ws.cell(
                    row=tot,
                    column=col,
                    value=f"=SUM({letter}{first_data}:{letter}{last})",
                )
                cell.font = Font(bold=True, size=fsize)
                cell.fill = PatternFill("solid", fgColor="C8E6C9")
                cell.number_format = "0.0"
                cell.border = thin
            pie = tot + 2
        else:
            pie = row_i + 1

        ws.cell(row=pie, column=1, value="Capturó: ________________")
        ws.cell(row=pie, column=min(4, n_cols), value="Revisó: ________________")
        ws.cell(
            row=pie + 1,
            column=1,
            value=f"Generado {datetime.now().strftime('%d/%m/%Y %H:%M')} · Fajos Central",
        ).font = Font(size=8, color="888888")

        # widths
        # Estrechas: ubic / folio / modelo / mat · anchas: nombre y AvN
        base_w = [5, 18]  # UBIC, NOMBRE
        if mostrar_folio:
            base_w.append(9)   # FOLIO
        if mostrar_modelo:
            base_w.append(8)   # MODELO (compacto)
        if mostrar_mat:
            base_w.append(5)   # MAT (compacto)
        base_w.extend([8] * n_avances)  # AvN priorizados
        base_w.append(8)  # TOTAL
        if mostrar_obs:
            base_w.append(12)
        for i, w in enumerate(base_w[:n_cols], 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        ws.row_dimensions[5].height = 22
        # Vertical (retrato): cabe mejor en el escritorio y en el flujo del papel de suministro
        ws.page_setup.orientation = "portrait"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        p = (papel or "letter").lower()
        if p in ("a4",):
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
        elif p in ("legal", "oficio"):
            ws.page_setup.paperSize = ws.PAPERSIZE_LEGAL
        else:
            ws.page_setup.paperSize = ws.PAPERSIZE_LETTER
        ws.print_title_rows = "5:5"
        # ~0.5" margins (desktop printer safe)
        ws.page_margins.left = 0.5
        ws.page_margins.right = 0.5
        ws.page_margins.top = 0.5
        ws.page_margins.bottom = 0.5

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def export_captura_manual(
        self,
        lineas: list[dict],
        *,
        codigo_semana: str = "",
    ) -> tuple[bytes, str, str]:
        """
        Nómina en blanco para captura manual (papel).
        - Estilo similar a formal, sin $/Gr ni Efectivo.
        - Columnas de gramos + $/Gr + Total Gr (fórmula SUM). Sin efectivo.
        - Una fila de identidad por trabajo de la semana + una fila en blanco
          extra por cada trabajador (nombre+ubic) para anotar otro folio.
        - Incluye líneas aunque aún no tengan gramos.
        """
        data = self._to_xlsx_captura_manual(lineas, codigo_semana)
        stem = f"nomina_captura_{codigo_semana or 'semana'}"
        return (
            data,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            f"{stem}.xlsx",
        )

    def _to_xlsx_captura_manual(self, lineas: list[dict], codigo_semana: str) -> bytes:
        from datetime import date, datetime
        from collections import OrderedDict

        hoy = date.today()
        generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        meses = {
            1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
            5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
            9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
        }

        def _pk(r):
            try:
                u = int(float(r.get("ubic") or 0))
            except (TypeError, ValueError):
                u = 0
            return (u, str(r.get("nombre") or "").upper(), str(r.get("folio") or "").upper())

        data_rows = sorted(list(lineas or []), key=_pk)

        # Agrupar por trabajador para insertar 1 fila en blanco al final de cada grupo
        groups: OrderedDict[tuple, list] = OrderedDict()
        for r in data_rows:
            try:
                u = int(float(r.get("ubic") or 0))
            except (TypeError, ValueError):
                u = 0
            key = (str(r.get("nombre") or "").strip().upper(), u)
            groups.setdefault(key, []).append(r)

        wb = Workbook()
        ws = wb.active
        ws.title = "Nomina-Captura"

        # --- Encabezado (similar formal, sin precios) ---
        ws.merge_cells("A1:N1")
        ws["A1"] = "TALLER DE FAJOS CENTRAL"
        ws["A1"].font = Font(name="Calibri", bold=True, size=16, color="1F4E79")

        ws.merge_cells("A2:N2")
        ws["A2"] = "NÓMINA EN BLANCO — CAPTURA MANUAL (PLATA)"
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
            ws.cell(row=3, column=col).font = Font(
                name="Calibri", size=9, bold=(col % 2 == 1)
            )

        ws.merge_cells("A4:N4")
        ws["A4"] = (
            "Anotar gramos por día a mano. Hay una fila extra en blanco por cada trabajador "
            "para otro folio. Solo se totalizan gramos (sin precios)."
        )
        ws["A4"].font = Font(name="Calibri", size=8, italic=True, color="666666")

        headers = [
            "Nombre", "Ubic", "Folio", "Modelo", "Material", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Total Gr",
        ]
        for col, h in enumerate(headers, 1):
            cell = ws.cell(row=5, column=col, value=h)
            cell.font = self.HEADER_FONT
            cell.fill = self.HEADER_FILL
            cell.border = self.THIN
            cell.alignment = Alignment(horizontal="center", wrap_text=True)

        # Columnas: A–E identidad, F $/Gr, G–M días, N Total Gr
        row_i = 6
        first_data = 6

        def _write_identity_row(r: dict, blank_days: bool = True) -> int:
            nonlocal row_i
            mat = str(r.get("material") or "").upper()
            fill = self.MAT_FILLS.get(mat, self.MAT_DEFAULT if mat else None)
            tarifa = r.get("tarifa_gr")
            try:
                tarifa_f = float(tarifa) if tarifa is not None else None
                if tarifa_f == 0:
                    tarifa_f = None
            except (TypeError, ValueError):
                tarifa_f = None
            vals = [
                r.get("nombre") or "",
                r.get("ubic"),
                r.get("folio") or "",
                r.get("modelo") or "",
                r.get("material") or "",
                tarifa_f if tarifa_f is not None else 12,
            ]
            for col, v in enumerate(vals, 1):
                cell = ws.cell(row=row_i, column=col, value=v if v is not None else "")
                cell.border = self.THIN
                if fill is not None:
                    cell.fill = fill
                if col == 6:
                    cell.number_format = "0.0"
            # Días en blanco para captura (G–M = cols 7–13)
            for col in range(7, 14):
                cell = ws.cell(row=row_i, column=col, value="")
                cell.border = self.THIN
                if fill is not None:
                    cell.fill = fill
            # Total Gr = suma de días G–M (fórmula)
            cell = ws.cell(
                row=row_i,
                column=14,
                value=f'=IF(SUM(G{row_i}:M{row_i})=0,"",SUM(G{row_i}:M{row_i}))',
            )
            cell.border = self.THIN
            cell.number_format = "0.0"
            if fill is not None:
                cell.fill = fill
            row_i += 1
            return row_i - 1

        def _write_blank_worker_row(nombre: str, ubic, tarifa_default=12) -> None:
            nonlocal row_i
            # Fila en blanco del mismo trabajador (otro folio) — conserva espacio para $/Gr
            for col, v in enumerate([nombre, ubic, "", "", "", tarifa_default], 1):
                cell = ws.cell(row=row_i, column=col, value=v if v is not None else "")
                cell.border = self.THIN
                if col == 6:
                    cell.number_format = "0.0"
            for col in range(7, 14):
                ws.cell(row=row_i, column=col, value="").border = self.THIN
            cell = ws.cell(
                row=row_i,
                column=14,
                value=f'=IF(SUM(G{row_i}:M{row_i})=0,"",SUM(G{row_i}:M{row_i}))',
            )
            cell.border = self.THIN
            cell.number_format = "0.0"
            hint = PatternFill("solid", fgColor="FFF8E7")
            for col in range(1, 15):
                ws.cell(row=row_i, column=col).fill = hint
            row_i += 1

        if not groups:
            ws.cell(row=6, column=1, value="(Sin trabajadores en esta semana)")
            row_i = 7
        else:
            for (nombre_key, ubic), items in groups.items():
                display_nombre = items[0].get("nombre") or nombre_key
                for item in items:
                    _write_identity_row(item)
                # Una fila en blanco por trabajador
                tar0 = items[0].get("tarifa_gr")
                try:
                    tar0 = float(tar0) if tar0 is not None else 12
                except (TypeError, ValueError):
                    tar0 = 12
                _write_blank_worker_row(display_nombre, ubic, tar0)

        last = row_i - 1
        if last >= first_data:
            tot = last + 1
            ws.cell(row=tot, column=5, value="TOTALES").font = Font(bold=True)
            from openpyxl.utils import get_column_letter as _gcl
            for col in range(7, 15):  # días G–M + Total Gr
                letter = _gcl(col)
                cell = ws.cell(
                    row=tot,
                    column=col,
                    value=f"=SUM({letter}{first_data}:{letter}{last})",
                )
                cell.font = Font(bold=True)
                cell.fill = self.GREEN_FILL
                cell.number_format = "0.0"
                cell.border = self.THIN
            pie = tot + 2
        else:
            pie = row_i + 1

        ws.cell(row=pie, column=1, value="Responsable captura: ________________")
        ws.cell(row=pie, column=5, value="Fecha: ____ / ____ / ______")
        ws.cell(
            row=pie + 1,
            column=1,
            value=(
                f"Generado por Fajos Central el {generado}. "
                "Gramos + $/Gr de referencia. Filas crema = espacio extra por trabajador."
            ),
        ).font = Font(size=8, italic=True, color="666666")

        widths = {
            "A": 20, "B": 7, "C": 11, "D": 14, "E": 10, "F": 7,
            "G": 6, "H": 6, "I": 6, "J": 6, "K": 6, "L": 6, "M": 6, "N": 10,
        }
        for col, w in widths.items():
            ws.column_dimensions[col].width = w
        ws.page_setup.orientation = "landscape"
        ws.page_setup.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0
        ws.print_title_rows = "1:5"
        try:
            ws.oddFooter.center.text = f"Captura manual {codigo_semana} · {generado}"
        except Exception:
            pass

        buf = BytesIO()
        wb.save(buf)
        return buf.getvalue()

    def export_master(self, db=None) -> tuple[bytes, str, str]:
        """
        Exporta toda la base operativa a un Excel multi-hoja (archivo Master).
        Incluye catálogos, semanas, producción PLT/PIT, taller, trabajos y resumen.
        """
        from datetime import datetime
        from openpyxl.utils import get_column_letter

        from app.db.connection import get_db

        database = db or get_db()
        generado = datetime.now().strftime("%Y-%m-%d_%H%M")
        wb = Workbook()

        # Definición de hojas: (nombre_hoja, SQL, columnas opcionales ordenadas)
        sheets_spec = [
            (
                "00_Indice",
                None,
                None,
            ),
            (
                "Trabajadores",
                """
                SELECT id, nombre_mostrar, nombre_completo, ubic, tipo, puesto,
                       activo, fecha_incorporacion, notas, creado_en, actualizado_en
                FROM trabajadores
                ORDER BY tipo, nombre_mostrar, ubic
                """,
                None,
            ),
            (
                "Semanas",
                """
                SELECT id, codigo, fecha_inicio, fecha_fin, anio, cerrada,
                       cerrada_en, cerrada_por, notas, creado_en
                FROM semanas
                ORDER BY fecha_inicio DESC
                """,
                None,
            ),
            (
                "Produccion_Plata",
                """
                SELECT id, semana_id, trabajador_id, trabajo_id, nombre, ubic,
                       folio, modelo, material, tarifa_gr,
                       gm_sab, gm_dom, gm_lun, gm_mar, gm_mie, gm_jue, gm_vie,
                       total_gramos, efectivo, firmado, notas, creado_en
                FROM produccion_plata
                ORDER BY semana_id, ubic, nombre
                """,
                None,
            ),
            (
                "Produccion_Pita",
                """
                SELECT id, semana_id, trabajador_id, nombre, ubic, modelo, folio,
                       material, producto, pitas, efectivo, firmado, notas, creado_en
                FROM produccion_pita
                ORDER BY semana_id, ubic, nombre
                """,
                None,
            ),
            (
                "Nomina_Taller",
                """
                SELECT id, semana_id, trabajador_id, nombre, ubic, puesto,
                       sueldo, extras, total, firmado, notas, creado_en
                FROM nomina_taller
                ORDER BY semana_id, ubic, nombre
                """,
                None,
            ),
            (
                "Trabajos",
                """
                SELECT id, trabajador_id, folio, modelo, material, tarifa_gr,
                       activo, notas, creado_en
                FROM trabajos
                ORDER BY trabajador_id, folio
                """,
                None,
            ),
            (
                "Modelos",
                """
                SELECT id, modelo, tipo, material_default, tarifa_default, notas
                FROM modelos
                ORDER BY tipo, modelo
                """,
                None,
            ),
            (
                "Tarifas_Material",
                """
                SELECT id, material, tarifa_por_gramo, descripcion, activo
                FROM tarifas_material
                ORDER BY material
                """,
                None,
            ),
            (
                "Resumen_Nominas",
                """
                SELECT r.id, r.semana_id, s.codigo AS semana_codigo,
                       r.nomina_plt, r.nomina_pit, r.nomina_tll, r.total_semana, r.notas, r.creado_en
                FROM resumen_nominas r
                LEFT JOIN semanas s ON s.id = r.semana_id
                ORDER BY r.semana_id DESC
                """,
                None,
            ),
            (
                "Totales_Semana",
                """
                SELECT * FROM v_totales_semana
                ORDER BY fecha_inicio DESC
                """,
                None,
            ),
        ]

        header_fill = self.HEADER_FILL
        header_font = self.HEADER_FONT
        thin = self.THIN
        alt = self.ALT_FILL

        # Remove default sheet; rebuild
        default = wb.active
        wb.remove(default)

        indice_rows = []
        for sheet_name, sql, _cols in sheets_spec:
            ws = wb.create_sheet(sheet_name)
            if sheet_name == "00_Indice":
                ws["A1"] = "FAJOS PITEADOS CENTRAL — ARCHIVO MASTER"
                ws["A1"].font = Font(name="Calibri", bold=True, size=14, color="1F4E79")
                ws["A2"] = f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
                ws["A3"] = "Contiene catálogos y movimientos de la base de datos operativa."
                ws["A5"] = "Hoja"
                ws["B5"] = "Descripción"
                ws["A5"].font = header_font
                ws["A5"].fill = header_fill
                ws["B5"].font = header_font
                ws["B5"].fill = header_fill
                descriptions = {
                    "Trabajadores": "Catálogo unificado (PLT / PIT / TLL)",
                    "Semanas": "Semanas de nómina",
                    "Produccion_Plata": "Captura semanal plata (gramos)",
                    "Produccion_Pita": "Nómina pita (efectivo)",
                    "Nomina_Taller": "Nómina taller (sueldo + extras)",
                    "Trabajos": "Folios/modelos ligados a trabajador",
                    "Modelos": "Catálogo de modelos",
                    "Tarifas_Material": "Tarifas por material PLT",
                    "Resumen_Nominas": "Totales guardados por semana",
                    "Totales_Semana": "Vista calculada Taller+Plata+Pita",
                }
                r = 6
                for name, desc in descriptions.items():
                    ws.cell(r, 1, name)
                    ws.cell(r, 2, desc)
                    r += 1
                ws.column_dimensions["A"].width = 22
                ws.column_dimensions["B"].width = 48
                continue

            rows = []
            try:
                with database.cursor() as cur:
                    cur.execute(sql)
                    rows = list(cur.fetchall() or [])
            except Exception as e:
                logger.warning("Master sheet %s omitida: %s", sheet_name, e)
                ws["A1"] = f"No disponible: {e}"
                indice_rows.append((sheet_name, 0, str(e)))
                continue

            if not rows:
                ws["A1"] = "(sin registros)"
                indice_rows.append((sheet_name, 0, "vacío"))
                continue

            # Column order from first row keys
            keys = list(rows[0].keys())
            for col, key in enumerate(keys, 1):
                cell = ws.cell(1, col, key)
                cell.fill = header_fill
                cell.font = header_font
                cell.border = thin
                cell.alignment = Alignment(horizontal="center", wrap_text=True)

            for i, row in enumerate(rows):
                for col, key in enumerate(keys, 1):
                    val = row.get(key)
                    if hasattr(val, "isoformat"):
                        try:
                            val = val.isoformat()
                        except Exception:
                            val = str(val)
                    elif isinstance(val, (bytes, bytearray)):
                        val = val.decode("utf-8", errors="replace")
                    cell = ws.cell(i + 2, col, val)
                    cell.border = thin
                    if i % 2 == 1:
                        cell.fill = alt

            for col, key in enumerate(keys, 1):
                width = min(max(len(str(key)) + 2, 10), 28)
                ws.column_dimensions[get_column_letter(col)].width = width

            ws.auto_filter.ref = ws.dimensions
            ws.freeze_panes = "A2"
            indice_rows.append((sheet_name, len(rows), "ok"))

        # Update index counts if sheet exists
        if "00_Indice" in wb.sheetnames:
            ws = wb["00_Indice"]
            ws["A16"] = "Conteos al exportar"
            ws["A16"].font = Font(bold=True)
            r = 17
            for name, n, st in indice_rows:
                ws.cell(r, 1, name)
                ws.cell(r, 2, n if st == "ok" else f"{st}")
                r += 1

        buf = BytesIO()
        wb.save(buf)
        fname = f"fajos_master_{generado}.xlsx"
        return (
            buf.getvalue(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            fname,
        )
