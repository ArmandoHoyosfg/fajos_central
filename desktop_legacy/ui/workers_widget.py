"""
Pestaña de Trabajadores.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout as _QVBox,

    QComboBox,
    QDateEdit,
    QFormLayout,
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
)

from db import TrabajadoresRepo


class WorkersWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = TrabajadoresRepo()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Catálogo de Trabajadores")
        title.setProperty("cssClass", "title")
        layout.addWidget(title)
        sub = QLabel("Mismo nombre + distinta ubic = personas diferentes")
        sub.setProperty("cssClass", "subtitle")
        layout.addWidget(sub)

        search_row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por nombre o ubic…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)

        # Formulario alta rápida
        form_box = QWidget()
        form = QFormLayout(form_box)
        form.setSpacing(8)

        self.inp_nombre = QLineEdit()
        self.inp_nombre.setPlaceholderText("Nombre para mostrar")
        self.inp_ubic = QSpinBox()
        self.inp_ubic.setRange(1, 9999)
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.addItems(["PLT", "PIT", "TLL", "PLT/PIT", "Mixto"])
        self.inp_puesto = QLineEdit()
        self.inp_puesto.setPlaceholderText("Puesto (solo TLL)")
        self.date_inc = QDateEdit()
        self.date_inc.setCalendarPopup(True)
        self.date_inc.setDate(date.today())

        form.addRow("Nombre:", self.inp_nombre)
        form.addRow("Ubicación:", self.inp_ubic)
        form.addRow("Tipo:", self.cmb_tipo)
        form.addRow("Puesto:", self.inp_puesto)
        form.addRow("Incorporación:", self.date_inc)

        btn_row = QHBoxLayout()
        self.btn_add = QPushButton("Agregar trabajador")
        self.btn_add.setProperty("cssClass", "success")
        self.btn_add.clicked.connect(self._on_add)
        self.btn_refresh = QPushButton("Actualizar lista")
        self.btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(self.btn_add)
        btn_row.addWidget(self.btn_refresh)
        btn_row.addStretch()

        layout.addWidget(form_box)
        layout.addLayout(btn_row)

        # Tabla
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nombre", "Nombre completo", "Ubic", "Tipo", "Puesto", "Activo", "Incorporación"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        act_row = QHBoxLayout()
        btn_edit = QPushButton("Editar seleccionado")
        btn_edit.clicked.connect(self._on_edit)
        btn_deact = QPushButton("Dar de baja")
        btn_deact.setProperty("cssClass", "danger")
        btn_deact.clicked.connect(self._on_deactivate)
        btn_act = QPushButton("Reactivar")
        btn_act.setProperty("cssClass", "success")
        btn_act.clicked.connect(self._on_reactivate)
        act_row.addWidget(btn_edit)
        act_row.addWidget(btn_deact)
        act_row.addWidget(btn_act)
        act_row.addStretch()
        layout.addLayout(act_row)
        self.table.doubleClicked.connect(lambda: self._on_edit())

    def refresh(self):
        try:
            self._all_rows = self.repo.listar(solo_activos=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudieron cargar trabajadores:\n{e}")
            return
        self.apply_filter(self.search.text() if hasattr(self, "search") else "")

    def apply_filter(self, text: str = ""):
        text = (text or "").strip().lower()
        rows = getattr(self, "_all_rows", []) or []
        if text:
            filtered = []
            for r in rows:
                blob = f"{r.get('nombre_mostrar','')} {r.get('nombre_completo','')} {r.get('ubic','')} {r.get('tipo','')}".lower()
                if text in blob:
                    filtered.append(r)
            rows = filtered
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r["id"],
                r["nombre_mostrar"],
                r.get("nombre_completo") or "",
                r["ubic"],
                r["tipo"],
                r.get("puesto") or "",
                "Sí" if r["activo"] else "No",
                str(r["fecha_incorporacion"] or ""),
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter if j in (0, 3, 4, 6) else Qt.AlignLeft | Qt.AlignVCenter)
                if j == 4:  # Tipo
                    t = str(v).upper()
                    if "PLT" in t and "PIT" in t:
                        item.setBackground(QBrush(QColor("#313244")))
                    elif "PLT" in t:
                        item.setBackground(QBrush(QColor("#1e3a5f")))
                        item.setForeground(QBrush(QColor("#89b4fa")))
                    elif "PIT" in t:
                        item.setBackground(QBrush(QColor("#3d2a1a")))
                        item.setForeground(QBrush(QColor("#fab387")))
                    elif "TLL" in t:
                        item.setBackground(QBrush(QColor("#1a3d2a")))
                        item.setForeground(QBrush(QColor("#a6e3a1")))
                if j == 6:  # Activo
                    if str(v) == "Sí":
                        item.setForeground(QBrush(QColor("#a6e3a1")))
                    else:
                        item.setForeground(QBrush(QColor("#f38ba8")))
                self.table.setItem(i, j, item)

    def _on_add(self):
        nombre = self.inp_nombre.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Datos incompletos", "Escribe el nombre.")
            return
        try:
            self.repo.agregar(
                nombre_mostrar=nombre,
                ubic=self.inp_ubic.value(),
                tipo=self.cmb_tipo.currentText(),
                puesto=self.inp_puesto.text().strip() or None,
                fecha_incorporacion=self.date_inc.date().toPython(),
            )
            self.inp_nombre.clear()
            self.refresh()
            self.data_changed.emit()
            QMessageBox.information(self, "OK", "Trabajador agregado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))


    def _selected_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        try:
            return int(item.text())
        except (TypeError, ValueError, AttributeError):
            return None

    def _on_edit(self):
        tid = self._selected_id()
        if not tid:
            QMessageBox.information(self, "Editar", "Selecciona un trabajador en la tabla.")
            return
        row = next((r for r in self._all_rows if r.get("id") == tid), None)
        if not row:
            QMessageBox.warning(self, "Editar", "No se encontró el registro.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar — {row.get('nombre_mostrar')}")
        dlg.setMinimumWidth(380)
        form = QFormLayout(dlg)
        inp_n = QLineEdit(str(row.get("nombre_mostrar") or ""))
        inp_c = QLineEdit(str(row.get("nombre_completo") or ""))
        inp_u = QSpinBox()
        inp_u.setRange(1, 9999)
        try:
            inp_u.setValue(int(row.get("ubic") or 1))
        except (TypeError, ValueError):
            inp_u.setValue(1)
        cmb_t = QComboBox()
        cmb_t.addItems(["PLT", "PIT", "TLL", "PLT/PIT", "Mixto"])
        tip = str(row.get("tipo") or "PLT")
        idx = cmb_t.findText(tip)
        if idx >= 0:
            cmb_t.setCurrentIndex(idx)
        inp_p = QLineEdit(str(row.get("puesto") or ""))
        date_i = QDateEdit()
        date_i.setCalendarPopup(True)
        from datetime import date as _date
        fi = row.get("fecha_incorporacion")
        if fi:
            try:
                if hasattr(fi, "year"):
                    date_i.setDate(fi if not hasattr(fi, "date") else fi)
                else:
                    y, m, d = str(fi)[:10].split("-")
                    date_i.setDate(_date(int(y), int(m), int(d)))
            except Exception:
                date_i.setDate(_date.today())
        else:
            date_i.setDate(_date.today())
        cmb_a = QComboBox()
        cmb_a.addItem("Activo", 1)
        cmb_a.addItem("Baja", 0)
        cmb_a.setCurrentIndex(0 if row.get("activo") else 1)
        form.addRow("Nombre:", inp_n)
        form.addRow("Nombre completo:", inp_c)
        form.addRow("Ubicación:", inp_u)
        form.addRow("Tipo:", cmb_t)
        form.addRow("Puesto:", inp_p)
        form.addRow("Incorporación:", date_i)
        form.addRow("Estado:", cmb_a)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        if dlg.exec() != QDialog.Accepted:
            return
        try:
            self.repo.actualizar(
                tid,
                nombre_mostrar=inp_n.text().strip(),
                nombre_completo=inp_c.text().strip() or inp_n.text().strip(),
                ubic=inp_u.value(),
                tipo=cmb_t.currentText(),
                puesto=inp_p.text().strip() or None,
                fecha_incorporacion=date_i.date().toPython().isoformat(),
                activo=cmb_a.currentData(),
            )
            self.data_changed.emit()
            self.refresh()
            QMessageBox.information(self, "OK", "Trabajador actualizado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_reactivate(self):
        tid = self._selected_id()
        if not tid:
            QMessageBox.information(self, "Reactivar", "Selecciona un trabajador.")
            return
        try:
            if hasattr(self.repo, "activar"):
                self.repo.activar(tid)
            else:
                self.repo.actualizar(tid, activo=1)
            self.data_changed.emit()
            self.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_deactivate(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selección", "Selecciona un trabajador.")
            return
        tid = int(self.table.item(row, 0).text())
        try:
            self.repo.desactivar(tid)
            self.refresh()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
