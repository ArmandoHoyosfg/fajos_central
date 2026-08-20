"""
Pestaña de Trabajadores.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import (
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

        btn_deact = QPushButton("Desactivar seleccionado")
        btn_deact.setProperty("cssClass", "danger")
        btn_deact.clicked.connect(self._on_deactivate)
        layout.addWidget(btn_deact)

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
