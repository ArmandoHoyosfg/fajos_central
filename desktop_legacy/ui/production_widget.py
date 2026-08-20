"""
Pestaña de Producción / Nómina semanal de plata.
Incluye captura de un solo día, edición en tabla, colores por material y filtro.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
    QAbstractItemView,
    QScrollArea,
    QSizePolicy,
    QFrame,
)

from db import ProduccionRepo, SemanasRepo, TrabajadoresRepo
from services.excel_service import ExcelService

DAY_KEYS = [
    ("gm_sab", "Sáb"),
    ("gm_dom", "Dom"),
    ("gm_lun", "Lun"),
    ("gm_mar", "Mar"),
    ("gm_mie", "Mié"),
    ("gm_jue", "Jue"),
    ("gm_vie", "Vie"),
]
DAY_BY_WEEKDAY = {
    5: "gm_sab",  # Saturday
    6: "gm_dom",
    0: "gm_lun",
    1: "gm_mar",
    2: "gm_mie",
    3: "gm_jue",
    4: "gm_vie",
}
MAT_COLORS = {
    "AG3": QColor("#1e3a5f"),
    "AG4": QColor("#1a3d2e"),
    "DOL": QColor("#3d3420"),
    "DLO": QColor("#3d2e1a"),
}
MAT_FG = {
    "AG3": QColor("#89b4fa"),
    "AG4": QColor("#a6e3a1"),
    "DOL": QColor("#c9a227"),
    "DLO": QColor("#fab387"),
}


def _f(v):
    if v is None or v == "":
        return None
    try:
        x = float(v)
        return None if x == 0 else x
    except (TypeError, ValueError):
        return None


class ProductionWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prod_repo = ProduccionRepo()
        self.sem_repo = SemanasRepo()
        self.trab_repo = TrabajadoresRepo()
        self.excel = ExcelService()
        self._semana_id: int | None = None
        self._all_rows: list[dict] = []
        self._updating_cell = False
        self._build_ui()
        self._load_semanas()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: #1e1e2e; width: 12px; margin: 0; }"
            "QScrollBar::handle:vertical { background: #45475a; border-radius: 6px; min-height: 40px; }"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            "QScrollBar:horizontal { background: #1e1e2e; height: 12px; }"
            "QScrollBar::handle:horizontal { background: #45475a; border-radius: 6px; min-width: 40px; }"
        )

        content = QWidget()
        content.setObjectName("prodContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        title = QLabel("Producción semanal — Plata")
        title.setProperty("cssClass", "title")
        layout.addWidget(title)
        sub = QLabel("Captura por día, edición en tabla y export formal")
        sub.setProperty("cssClass", "subtitle")
        layout.addWidget(sub)

        # Semana + totales
        top = QHBoxLayout()
        top.addWidget(QLabel("Semana:"))
        self.cmb_semana = QComboBox()
        self.cmb_semana.setMinimumWidth(240)
        self.cmb_semana.currentIndexChanged.connect(self._on_semana_changed)
        top.addWidget(self.cmb_semana)
        self.btn_nueva_sem = QPushButton("+ Nueva semana")
        self.btn_nueva_sem.clicked.connect(self._on_nueva_semana)
        top.addWidget(self.btn_nueva_sem)
        top.addStretch()
        self.lbl_totales = QLabel("Totales: —")
        self.lbl_totales.setProperty("cssClass", "kpi")
        top.addWidget(self.lbl_totales)
        layout.addLayout(top)

        # --- Un solo día ---
        box_day = QGroupBox("📅  Registrar un solo día")
        day_outer = QVBoxLayout(box_day)
        day_outer.setSpacing(10)
        row1 = QHBoxLayout()
        row2 = QHBoxLayout()
        self.cmb_dia_trab = QComboBox()
        self.cmb_dia_trab.setMinimumWidth(200)
        self.cmb_dia_trab.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.cmb_dia_trab.setEditable(True)
        self.cmb_dia = QComboBox()
        for key, label in DAY_KEYS:
            self.cmb_dia.addItem(label, key)
        today_key = DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")
        idx = self.cmb_dia.findData(today_key)
        if idx >= 0:
            self.cmb_dia.setCurrentIndex(idx)
        self.spin_dia_gr = QDoubleSpinBox()
        self.spin_dia_gr.setRange(0, 9999)
        self.spin_dia_gr.setDecimals(2)
        self.spin_dia_gr.setMinimumWidth(90)
        self.inp_dia_folio = QLineEdit()
        self.inp_dia_folio.setPlaceholderText("Folio (opcional)")
        self.inp_dia_folio.setMinimumWidth(110)
        self.inp_dia_modelo = QLineEdit()
        self.inp_dia_modelo.setPlaceholderText("Modelo (opcional)")
        self.inp_dia_modelo.setMinimumWidth(120)
        self.cmb_dia_mat = QComboBox()
        self.cmb_dia_mat.addItems(["AG3", "AG4", "DOL", "DLO"])
        self.spin_dia_tarifa = QDoubleSpinBox()
        self.spin_dia_tarifa.setRange(0, 100)
        self.spin_dia_tarifa.setValue(12.0)
        self.spin_dia_tarifa.setDecimals(2)
        self.spin_dia_tarifa.setMinimumWidth(90)
        btn_dia = QPushButton("Guardar día")
        btn_dia.setProperty("cssClass", "success")
        btn_dia.setMinimumHeight(32)
        btn_dia.clicked.connect(self._on_guardar_dia)
        for lab, w in [
            ("Trabajador", self.cmb_dia_trab),
            ("Día", self.cmb_dia),
            ("Gramos", self.spin_dia_gr),
            ("", btn_dia),
        ]:
            if lab:
                row1.addWidget(QLabel(lab))
            row1.addWidget(w)
        for lab, w in [
            ("Folio", self.inp_dia_folio),
            ("Modelo", self.inp_dia_modelo),
            ("Material", self.cmb_dia_mat),
            ("$/Gr", self.spin_dia_tarifa),
        ]:
            row2.addWidget(QLabel(lab))
            row2.addWidget(w)
        row2.addStretch(1)
        day_outer.addLayout(row1)
        day_outer.addLayout(row2)
        layout.addWidget(box_day)

        # --- Línea completa ---
        box = QGroupBox("➕  Agregar línea completa (varios días / folio)")
        form = QFormLayout(box)
        self.cmb_trabajador = QComboBox()
        self.cmb_trabajador.setEditable(True)
        self.inp_folio = QLineEdit()
        self.inp_modelo = QLineEdit()
        self.cmb_material = QComboBox()
        self.cmb_material.addItems(["AG3", "AG4", "DOL", "DLO"])
        self.inp_tarifa = QDoubleSpinBox()
        self.inp_tarifa.setRange(0, 100)
        self.inp_tarifa.setValue(12.0)
        self.inp_tarifa.setDecimals(2)
        dias_layout = QHBoxLayout()
        self.dias = {}
        for key, label in DAY_KEYS:
            wrap = QVBoxLayout()
            lb = QLabel(label)
            if key == today_key:
                lb.setStyleSheet("color: #c9a227; font-weight: bold;")
            spin = QDoubleSpinBox()
            spin.setRange(0, 9999)
            spin.setDecimals(2)
            spin.setMaximumWidth(72)
            wrap.addWidget(lb)
            wrap.addWidget(spin)
            dias_layout.addLayout(wrap)
            self.dias[key] = spin
        form.addRow("Trabajador:", self.cmb_trabajador)
        form.addRow("Folio:", self.inp_folio)
        form.addRow("Modelo:", self.inp_modelo)
        form.addRow("Material:", self.cmb_material)
        form.addRow("$/Gr:", self.inp_tarifa)
        form.addRow("Gramos:", dias_layout)
        btn_add = QPushButton("Agregar línea")
        btn_add.clicked.connect(self._on_add)
        form.addRow(btn_add)
        layout.addWidget(box)

        # Filtro
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Filtrar:"))
        self.inp_filter = QLineEdit()
        self.inp_filter.setPlaceholderText("Nombre, folio o material…")
        self.inp_filter.setClearButtonEnabled(True)
        self.inp_filter.textChanged.connect(self._apply_filter)
        filt.addWidget(self.inp_filter)
        hint = QLabel("Doble clic en gramos para editar un día")
        hint.setProperty("cssClass", "subtitle")
        filt.addWidget(hint)
        layout.addLayout(filt)

        # Tabla
        self.table = QTableWidget()
        cols = [
            "ID", "Nombre", "Ubic", "Folio", "Modelo", "Mat", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Total Gr", "Efectivo",
        ]
        self._col_keys = [
            "id", "nombre", "ubic", "folio", "modelo", "material", "tarifa_gr",
            "gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie",
            "total_gramos", "efectivo",
        ]
        self._day_cols = {7: "gm_sab", 8: "gm_dom", 9: "gm_lun", 10: "gm_mar",
                          11: "gm_mie", 12: "gm_jue", 13: "gm_vie"}
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.setMinimumHeight(280)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Highlight today column header
        today_col = {v: k for k, v in self._day_cols.items()}.get(today_key)
        layout.addWidget(self.table)
        self.lbl_empty = QLabel("")
        self.lbl_empty.setProperty("cssClass", "subtitle")
        self.lbl_empty.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_empty)

        # Bottom actions
        bottom = QHBoxLayout()
        btn_del = QPushButton("Eliminar línea")
        btn_del.setProperty("cssClass", "danger")
        btn_del.clicked.connect(self._on_delete)
        btn_export_formal = QPushButton("📄 Formal Excel")
        btn_export_formal.clicked.connect(self._on_export_formal)
        btn_export_captura = QPushButton("📋 Captura")
        btn_export_captura.clicked.connect(self._on_export_captura)
        btn_import = QPushButton("Importar Excel/CSV")
        btn_import.clicked.connect(self._on_import)
        bottom.addWidget(btn_del)
        bottom.addStretch()
        bottom.addWidget(btn_import)
        bottom.addWidget(btn_export_captura)
        bottom.addWidget(btn_export_formal)
        layout.addLayout(bottom)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._load_trabajadores()

    def _load_semanas(self):
        self.cmb_semana.blockSignals(True)
        self.cmb_semana.clear()
        try:
            semanas = self.sem_repo.listar()
            for s in semanas:
                self.cmb_semana.addItem(
                    f"{s['codigo']}  ({s['fecha_inicio']} → {s['fecha_fin']})",
                    s["id"],
                )
        except Exception as e:
            QMessageBox.warning(self, "Semanas", f"No se pudieron cargar semanas:\n{e}")
        self.cmb_semana.blockSignals(False)
        if self.cmb_semana.count():
            self._on_semana_changed()
        else:
            self.lbl_empty.setText("No hay semanas. Crea una con «Nueva semana».")
            self.lbl_totales.setText("Totales: —")

    def _load_trabajadores(self):
        for cmb in (self.cmb_trabajador, self.cmb_dia_trab):
            cmb.clear()
        try:
            rows = self.trab_repo.listar(solo_plt=True, solo_activos=True)
            for r in rows:
                label = f"{r['nombre_mostrar']}  (Ubic {r['ubic']})"
                data = (r["id"], r["nombre_mostrar"], r["ubic"])
                self.cmb_trabajador.addItem(label, data)
                self.cmb_dia_trab.addItem(label, data)
        except Exception:
            pass

    def _on_semana_changed(self):
        self._semana_id = self.cmb_semana.currentData()
        self.refresh_table()

    def _on_nueva_semana(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDateEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Nueva semana")
        fl = QFormLayout(dlg)
        codigo = QLineEdit()
        codigo.setPlaceholderText("16-22")
        ini = QDateEdit(calendarPopup=True)
        fin = QDateEdit(calendarPopup=True)
        ini.setDate(date.today())
        fin.setDate(date.today())
        fl.addRow("Código:", codigo)
        fl.addRow("Inicio:", ini)
        fl.addRow("Fin:", fin)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        fl.addRow(buttons)
        if dlg.exec() != QDialog.Accepted:
            return
        if not codigo.text().strip():
            QMessageBox.warning(self, "Datos", "Escribe el código de semana.")
            return
        try:
            self.sem_repo.crear(
                codigo.text().strip(),
                ini.date().toPython(),
                fin.date().toPython(),
                anio=ini.date().year(),
            )
            self._load_semanas()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _trabajador_data(self, cmb: QComboBox):
        data = cmb.currentData()
        if data:
            return data  # id, nombre, ubic
        text = cmb.currentText().strip()
        return (None, text, 0)

    def _on_guardar_dia(self):
        if not self._semana_id:
            QMessageBox.warning(self, "Semana", "Selecciona o crea una semana.")
            return
        tid, nombre, ubic = self._trabajador_data(self.cmb_dia_trab)
        if not nombre:
            QMessageBox.warning(self, "Datos", "Elige un trabajador.")
            return
        gr = self.spin_dia_gr.value()
        if gr <= 0:
            QMessageBox.warning(self, "Datos", "Indica los gramos del día (> 0).")
            return
        col = self.cmb_dia.currentData()
        folio = self.inp_dia_folio.text().strip() or None
        try:
            existing = self.prod_repo.buscar_linea(self._semana_id, nombre, ubic, folio)
            if existing:
                self.prod_repo.actualizar_gramos_dia(existing["id"], col, gr)
                msg = f"Actualizado {self.cmb_dia.currentText()} de {nombre}."
            else:
                payload = {
                    "trabajador_id": tid,
                    "nombre": nombre,
                    "ubic": int(ubic) if ubic else 0,
                    "folio": folio,
                    "modelo": self.inp_dia_modelo.text().strip() or None,
                    "material": self.cmb_dia_mat.currentText(),
                    "tarifa_gr": self.spin_dia_tarifa.value(),
                    "gm_sab": None, "gm_dom": None, "gm_lun": None,
                    "gm_mar": None, "gm_mie": None, "gm_jue": None, "gm_vie": None,
                }
                payload[col] = gr
                if not payload["ubic"]:
                    QMessageBox.warning(self, "Datos", "Selecciona un trabajador de la lista (con ubic).")
                    return
                self.prod_repo.insertar(self._semana_id, payload)
                msg = f"Nueva línea: {nombre} — {self.cmb_dia.currentText()} {gr} g."
            self.spin_dia_gr.setValue(0)
            self.refresh_table()
            self.data_changed.emit()
            QMessageBox.information(self, "OK", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_add(self):
        if not self._semana_id:
            QMessageBox.warning(self, "Semana", "Selecciona o crea una semana.")
            return
        tid, nombre, ubic = self._trabajador_data(self.cmb_trabajador)
        if not nombre or not ubic:
            QMessageBox.warning(self, "Datos", "Elige un trabajador de la lista.")
            return
        payload = {
            "trabajador_id": tid,
            "nombre": nombre,
            "ubic": int(ubic),
            "folio": self.inp_folio.text().strip() or None,
            "modelo": self.inp_modelo.text().strip() or None,
            "material": self.cmb_material.currentText(),
            "tarifa_gr": self.inp_tarifa.value(),
        }
        for key, spin in self.dias.items():
            payload[key] = _f(spin.value())
        try:
            self.prod_repo.insertar(self._semana_id, payload)
            for spin in self.dias.values():
                spin.setValue(0)
            self.inp_folio.clear()
            self.inp_modelo.clear()
            self.refresh_table()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh_table(self):
        self._updating_cell = True
        try:
            if not self._semana_id:
                self._all_rows = []
                self.table.setRowCount(0)
                self.lbl_empty.setText("Selecciona una semana para ver y capturar producción.")
                self.lbl_totales.setText("Totales: —")
                return
            self._all_rows = self.prod_repo.listar_por_semana(self._semana_id)
            self._apply_filter(self.inp_filter.text())
            tot = self.prod_repo.totales_semana(self._semana_id)
            gr = float(tot.get("total_gramos") or 0)
            ef = float(tot.get("total_efectivo") or 0)
            n = int(tot.get("lineas") or 0)
            self.lbl_totales.setText(f"Líneas: {n}   ·   Gramos: {gr:g}   ·   Efectivo: ${ef:,.2f}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar producción:\n{e}")
        finally:
            self._updating_cell = False

    def _apply_filter(self, text: str = ""):
        self._updating_cell = True
        try:
            q = (text or "").strip().lower()
            rows = self._all_rows
            if q:
                rows = [
                    r for r in rows
                    if q in str(r.get("nombre") or "").lower()
                    or q in str(r.get("folio") or "").lower()
                    or q in str(r.get("material") or "").lower()
                    or q in str(r.get("modelo") or "").lower()
                    or q in str(r.get("ubic") or "")
                ]
            self.table.setRowCount(len(rows))
            if not rows:
                self.lbl_empty.setText(
                    "Sin líneas en esta semana." if not q else "Ninguna línea coincide con el filtro."
                )
            else:
                self.lbl_empty.setText("")
            today_key = DAY_BY_WEEKDAY.get(date.today().weekday())
            for i, r in enumerate(rows):
                mat = str(r.get("material") or "").upper()
                bg = MAT_COLORS.get(mat)
                fg = MAT_FG.get(mat)
                for j, key in enumerate(self._col_keys):
                    val = r.get(key)
                    if isinstance(val, Decimal):
                        val = float(val)
                    if val is None or val == 0:
                        display = ""
                    elif key == "efectivo":
                        display = f"${float(val):,.2f}"
                    elif key in ("total_gramos", "tarifa_gr") or key.startswith("gm_"):
                        display = f"{float(val):g}"
                    else:
                        display = str(val)
                    item = QTableWidgetItem(display)
                    if j == 0 or j in self._day_cols or key in ("ubic", "tarifa_gr", "total_gramos", "efectivo"):
                        item.setTextAlignment(Qt.AlignCenter)
                    # editable only day columns
                    if j in self._day_cols:
                        item.setFlags(item.flags() | Qt.ItemIsEditable)
                        if self._day_cols[j] == today_key:
                            item.setForeground(QBrush(QColor("#c9a227")))
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if bg and j > 0:
                        item.setBackground(QBrush(bg))
                        if fg:
                            item.setForeground(QBrush(fg))
                    if j == 0:
                        item.setData(Qt.UserRole, r.get("id"))
                    self.table.setItem(i, j, item)
        finally:
            self._updating_cell = False

    def _on_cell_changed(self, item: QTableWidgetItem):
        if self._updating_cell:
            return
        col = item.column()
        if col not in self._day_cols:
            return
        row = item.row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        prod_id = id_item.data(Qt.UserRole) or int(id_item.text())
        col_name = self._day_cols[col]
        text = item.text().strip()
        try:
            gramos = None if text == "" else float(text.replace(",", "."))
        except ValueError:
            QMessageBox.warning(self, "Valor", "Gramos inválidos.")
            self.refresh_table()
            return
        try:
            self.prod_repo.actualizar_gramos_dia(int(prod_id), col_name, gramos)
            self.refresh_table()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.refresh_table()

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selección", "Selecciona una línea.")
            return
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        prod_id = id_item.data(Qt.UserRole) or int(id_item.text())
        if not QMessageBox.question(
            self, "Confirmar", f"¿Eliminar línea id={prod_id}?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            return
        try:
            self.prod_repo.eliminar(int(prod_id))
            self.refresh_table()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_export_formal(self):
        if not self._semana_id:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Nómina Formal", "Nomina_Formal.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            rows = list(self._all_rows)
            rows.sort(key=lambda r: (int(r.get("ubic") or 0), str(r.get("nombre") or "").upper()))
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            self.excel.exportar_nomina_formal(path, rows, codigo_semana=codigo)
            QMessageBox.information(self, "Exportado", path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_export_captura(self):
        if not self._semana_id:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar captura", "Nomina_Captura.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            trabs = self.trab_repo.listar(solo_plt=True, solo_activos=True)
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            self.excel.exportar_captura(path, trabs, codigo_semana=codigo)
            QMessageBox.information(self, "Exportado", path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar", "", "Excel/CSV (*.xlsx *.csv);;Todos (*.*)"
        )
        if not path or not self._semana_id:
            if not self._semana_id:
                QMessageBox.warning(self, "Semana", "Selecciona una semana primero.")
            return
        try:
            rows = self.excel.importar_lineas(path)
            count = 0
            for rec in rows:
                self.prod_repo.insertar(self._semana_id, rec)
                count += 1
            self.refresh_table()
            self.data_changed.emit()
            QMessageBox.information(self, "Importado", f"{count} líneas importadas.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def reload_workers(self):
        self._load_trabajadores()
