"""Mixin de exportación: suministro diario."""
from __future__ import annotations

from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.core.exceptions import ExportError, ValidationAppError
from app.core.logging_config import get_logger
from app.services.export.helpers import (
    filtrar_lineas_export,
    linea_activa,
    linea_tiene_gramos,
    print_oficio_landscape,
)

logger = get_logger(__name__)


class SuministroExportMixin:
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
        lineas = filtrar_lineas_export(lineas or [], solo_con_gramos=False)

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

