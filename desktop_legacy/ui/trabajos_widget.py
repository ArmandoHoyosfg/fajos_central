"""
Trabajos activos por trabajador — progreso diario con reglas de fecha.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from db import ProduccionRepo, SemanasRepo, TrabajosRepo
from ui.calendar_util import format_fecha_larga, today

# mirror app.core.dias without forcing full app import path issues
DAY_BY_WEEKDAY = {
    5: "gm_sab", 6: "gm_dom", 0: "gm_lun", 1: "gm_mar",
    2: "gm_mie", 3: "gm_jue", 4: "gm_vie",
}
DAY_LABELS = {
    "gm_sab": "Sábado", "gm_dom": "Domingo", "gm_lun": "Lunes",
    "gm_mar": "Martes", "gm_mie": "Miércoles", "gm_jue": "Jueves", "gm_vie": "Viernes",
}
ORDERED = ["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"]
DAY_HEADERS = ["Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie"]


def _col_hoy():
    return DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")


def _gramos(row, col):
    try:
        return float(row.get(col) or 0)
    except (TypeError, ValueError):
        return 0.0


class TrabajosWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.trab_repo = TrabajosRepo()
        self.sem_repo = SemanasRepo()
        self.prod_repo = ProduccionRepo()
        self._semana_id = None
        self._rows: list[dict] = []
        self._updating = False
        self._build()
        self.reload()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 16, 16, 16)
        title = QLabel("Trabajos activos")
        title.setProperty("cssClass", "title")
        lay.addWidget(title)
        self.lbl_ctx = QLabel()
        self.lbl_ctx.setProperty("cssClass", "subtitle")
        self.lbl_ctx.setWordWrap(True)
        lay.addWidget(self.lbl_ctx)

        top = QHBoxLayout()
        top.addWidget(QLabel("Semana:"))
        self.cmb_semana = QComboBox()
        self.cmb_semana.setMinimumWidth(240)
        self.cmb_semana.currentIndexChanged.connect(self._on_semana)
        top.addWidget(self.cmb_semana)
        self.chk_solo_sin_hoy = QCheckBox("Solo sin gramos de hoy")
        self.chk_solo_sin_hoy.toggled.connect(self._fill_table)
        top.addWidget(self.chk_solo_sin_hoy)
        top.addStretch()
        btn = QPushButton("Actualizar")
        btn.clicked.connect(self.reload)
        top.addWidget(btn)
        lay.addLayout(top)

        self.lbl_reminder = QLabel()
        self.lbl_reminder.setStyleSheet(
            "background:#313244;color:#c9a227;padding:8px 12px;border-radius:8px;"
            "border-left:3px solid #c9a227;"
        )
        self.lbl_reminder.setWordWrap(True)
        self.lbl_reminder.setVisible(False)
        lay.addWidget(self.lbl_reminder)

        # quick edit today
        edit = QHBoxLayout()
        edit.addWidget(QLabel("Registrar hoy:"))
        self.cmb_trabajo = QComboBox()
        self.cmb_trabajo.setMinimumWidth(280)
        edit.addWidget(self.cmb_trabajo)
        self.spin_gr = QDoubleSpinBox()
        self.spin_gr.setRange(0, 9999)
        self.spin_gr.setDecimals(2)
        edit.addWidget(self.spin_gr)
        btn_save = QPushButton("Guardar hoy")
        btn_save.setProperty("cssClass", "success")
        btn_save.clicked.connect(self._guardar_hoy)
        edit.addWidget(btn_save)
        edit.addStretch()
        lay.addLayout(edit)

        cols = ["Trabajador", "Ubic", "Folio", "Modelo", "Mat", "$/Gr"] + DAY_HEADERS + ["Total", "Prod ID"]
        self.table = QTableWidget()
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.table.itemChanged.connect(self._on_cell)
        self.table.setMinimumHeight(320)
        lay.addWidget(self.table)

        tip = QLabel(
            "Doble clic en un día para editar. Si el día es pasado y ya tiene gramos, se pedirá confirmación. "
            "El formal Excel/PDF se genera desde estos mismos datos."
        )
        tip.setProperty("cssClass", "subtitle")
        tip.setWordWrap(True)
        lay.addWidget(tip)

    def reload(self):
        self.cmb_semana.blockSignals(True)
        self.cmb_semana.clear()
        try:
            for s in self.sem_repo.listar():
                self.cmb_semana.addItem(
                    f"{s['codigo']}  ({s['fecha_inicio']} → {s['fecha_fin']})",
                    s["id"],
                )
        except Exception as e:
            QMessageBox.warning(self, "Semanas", str(e))
        self.cmb_semana.blockSignals(False)
        if self.cmb_semana.count():
            self.cmb_semana.setCurrentIndex(0)
            self._on_semana()
        else:
            self.lbl_ctx.setText("No hay semanas.")

    def _on_semana(self):
        self._semana_id = self.cmb_semana.currentData()
        self._load_rows()

    def _load_rows(self):
        if not self._semana_id:
            self._rows = []
            self._fill_table()
            return
        try:
            self._rows = self.trab_repo.listar_con_semana(self._semana_id, solo_activos=True)
        except Exception as e:
            # fallback si aún no existe el método en repo desktop
            try:
                self._rows = self.trab_repo.listar(solo_activos=True)
            except Exception as e2:
                QMessageBox.critical(self, "Trabajos", str(e2))
                self._rows = []
        self._fill_table()
        self._fill_combo()
        self._update_reminder()

    def _fill_combo(self):
        self.cmb_trabajo.clear()
        for r in self._rows:
            label = f"{r.get('nombre')} ({r.get('ubic')}) · {r.get('folio') or 's/folio'} · {r.get('modelo') or ''}"
            self.cmb_trabajo.addItem(label, r)

    def _update_reminder(self):
        col = _col_hoy()
        sin = [r for r in self._rows if _gramos(r, col) <= 0]
        hoy = format_fecha_larga(today())
        lab = DAY_LABELS.get(col, col)
        if not self._rows:
            self.lbl_reminder.setVisible(False)
            self.lbl_ctx.setText(f"Hoy: {hoy}")
            return
        self.lbl_ctx.setText(
            f"Hoy: {hoy} ({lab}). Trabajos activos: {len(self._rows)}. "
            f"Sin captura de hoy: {len(sin)}."
        )
        if sin:
            nombres = ", ".join(
                f"{r.get('nombre')}[{r.get('folio') or '—'}]" for r in sin[:8]
            )
            extra = f" (+{len(sin)-8} más)" if len(sin) > 8 else ""
            self.lbl_reminder.setText(
                f"⚠ Recordatorio: aún no hay gramos de {lab} en {len(sin)} trabajo(s): {nombres}{extra}"
            )
            self.lbl_reminder.setVisible(True)
        else:
            self.lbl_reminder.setText(f"✓ Todos los trabajos activos tienen gramos de {lab}.")
            self.lbl_reminder.setStyleSheet(
                "background:#313244;color:#a6e3a1;padding:8px 12px;border-radius:8px;"
                "border-left:3px solid #a6e3a1;"
            )
            self.lbl_reminder.setVisible(True)

    def _fill_table(self):
        self._updating = True
        col_h = _col_hoy()
        rows = self._rows
        if self.chk_solo_sin_hoy.isChecked():
            rows = [r for r in rows if _gramos(r, col_h) <= 0]
        self.table.setRowCount(len(rows))
        day_cols = {6 + i: ORDERED[i] for i in range(7)}  # after 6 fixed cols
        for i, r in enumerate(rows):
            vals = [
                r.get("nombre"),
                r.get("ubic"),
                r.get("folio"),
                r.get("modelo"),
                r.get("material"),
                r.get("tarifa_gr"),
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(i, c, item)
            for di, col in enumerate(ORDERED):
                g = r.get(col)
                try:
                    display = "" if g is None or float(g) == 0 else f"{float(g):g}"
                except (TypeError, ValueError):
                    display = ""
                item = QTableWidgetItem(display)
                item.setTextAlignment(Qt.AlignCenter)
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setData(Qt.UserRole, {
                    "trabajo_id": r.get("trabajo_id"),
                    "produccion_id": r.get("produccion_id"),
                    "trabajador_id": r.get("trabajador_id"),
                    "nombre": r.get("nombre"),
                    "ubic": r.get("ubic"),
                    "folio": r.get("folio"),
                    "modelo": r.get("modelo"),
                    "material": r.get("material"),
                    "tarifa_gr": r.get("tarifa_gr"),
                    "col": col,
                    "old": _gramos(r, col),
                })
                if col == col_h:
                    item.setForeground(Qt.yellow)
                self.table.setItem(i, 6 + di, item)
            tot = r.get("total_gramos")
            try:
                tot_s = "" if not tot or float(tot) == 0 else f"{float(tot):g}"
            except (TypeError, ValueError):
                tot_s = ""
            it = QTableWidgetItem(tot_s)
            it.setFlags(it.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 13, it)
            pid = QTableWidgetItem(str(r.get("produccion_id") or ""))
            pid.setFlags(pid.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(i, 14, pid)
        self._updating = False

    def _confirm_past(self, col: str, old: float) -> bool:
        hoy = _col_hoy()
        try:
            is_past = ORDERED.index(col) < ORDERED.index(hoy)
        except ValueError:
            is_past = False
        if is_past and old > 0:
            lab = DAY_LABELS.get(col, col)
            return QMessageBox.question(
                self,
                "Día pasado",
                f"Vas a modificar el {lab}, que ya tiene {old:g} g.\n"
                "¿Confirmas editar un día pasado con datos?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            ) == QMessageBox.Yes
        return True

    def _ensure_prod_line(self, meta: dict) -> int:
        """Devuelve produccion_id; crea línea de semana si no existe."""
        pid = meta.get("produccion_id")
        if pid:
            return int(pid)
        if not self._semana_id:
            raise ValueError("Sin semana seleccionada")
        new_id = self.prod_repo.insertar(self._semana_id, {
            "trabajador_id": meta.get("trabajador_id"),
            "trabajo_id": meta.get("trabajo_id"),
            "nombre": meta.get("nombre"),
            "ubic": meta.get("ubic"),
            "folio": meta.get("folio"),
            "modelo": meta.get("modelo"),
            "material": meta.get("material"),
            "tarifa_gr": meta.get("tarifa_gr"),
        })
        return int(new_id)

    def _on_cell(self, item: QTableWidgetItem):
        if self._updating:
            return
        meta = item.data(Qt.UserRole)
        if not meta or not isinstance(meta, dict):
            return
        col = meta.get("col")
        if not col:
            return
        text = item.text().strip()
        try:
            gramos = None if text == "" else float(text.replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Valor", "Gramos inválidos")
            self._load_rows()
            return
        old = float(meta.get("old") or 0)
        if not self._confirm_past(col, old):
            self._load_rows()
            return
        try:
            pid = self._ensure_prod_line(meta)
            self.prod_repo.actualizar_gramos_dia(pid, col, gramos)
            self.data_changed.emit()
            self._load_rows()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self._load_rows()

    def _guardar_hoy(self):
        r = self.cmb_trabajo.currentData()
        if not r or not isinstance(r, dict):
            QMessageBox.warning(self, "Trabajo", "Elige un trabajo activo.")
            return
        gr = self.spin_gr.value()
        if gr <= 0:
            QMessageBox.warning(self, "Gramos", "Indica gramos > 0.")
            return
        col = _col_hoy()
        old = _gramos(r, col)
        if not self._confirm_past(col, old):
            return
        meta = {
            "trabajo_id": r.get("trabajo_id"),
            "produccion_id": r.get("produccion_id"),
            "trabajador_id": r.get("trabajador_id"),
            "nombre": r.get("nombre"),
            "ubic": r.get("ubic"),
            "folio": r.get("folio"),
            "modelo": r.get("modelo"),
            "material": r.get("material"),
            "tarifa_gr": r.get("tarifa_gr"),
        }
        try:
            pid = self._ensure_prod_line(meta)
            self.prod_repo.actualizar_gramos_dia(pid, col, gr)
            self.spin_gr.setValue(0)
            self.data_changed.emit()
            self._load_rows()
            QMessageBox.information(
                self, "OK",
                f"Guardado {DAY_LABELS[col]}: {gr:g} g — {r.get('nombre')} / {r.get('folio')}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
