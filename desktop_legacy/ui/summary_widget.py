"""
Pestaña de Resumen de nóminas.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QComboBox,
)

from db import ResumenRepo, SemanasRepo, ProduccionRepo


class SummaryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.repo = ResumenRepo()
        self.sem_repo = SemanasRepo()
        self.prod_repo = ProduccionRepo()
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Resumen de Nóminas")
        title.setProperty("cssClass", "title")
        layout.addWidget(title)

        form = QFormLayout()
        self.cmb_semana = QComboBox()
        self.sp_plt = QDoubleSpinBox()
        self.sp_plt.setRange(0, 1_000_000)
        self.sp_plt.setDecimals(2)
        self.sp_plt.setPrefix("$ ")
        self.sp_pit = QDoubleSpinBox()
        self.sp_pit.setRange(0, 1_000_000)
        self.sp_pit.setDecimals(2)
        self.sp_pit.setPrefix("$ ")
        self.sp_tll = QDoubleSpinBox()
        self.sp_tll.setRange(0, 1_000_000)
        self.sp_tll.setDecimals(2)
        self.sp_tll.setPrefix("$ ")

        form.addRow("Semana:", self.cmb_semana)
        form.addRow("Nómina PLT:", self.sp_plt)
        form.addRow("Nómina PIT:", self.sp_pit)
        form.addRow("Nómina TLL:", self.sp_tll)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        btn_auto = QPushButton("Calcular PLT desde producción")
        btn_auto.clicked.connect(self._auto_plt)
        btn_save = QPushButton("Guardar resumen")
        btn_save.setProperty("cssClass", "success")
        btn_save.clicked.connect(self._save)
        btn_refresh = QPushButton("Actualizar")
        btn_refresh.clicked.connect(self.refresh)
        btn_row.addWidget(btn_auto)
        btn_row.addWidget(btn_save)
        btn_row.addWidget(btn_refresh)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Código", "Inicio", "Fin", "PLT", "PIT", "TLL", "TOTAL"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table)

        self._load_semanas()

    def _load_semanas(self):
        self.cmb_semana.clear()
        try:
            for s in self.sem_repo.listar():
                self.cmb_semana.addItem(f"{s['codigo']}", s["id"])
        except Exception:
            pass

    def refresh(self):
        self._load_semanas()
        try:
            rows = self.repo.listar()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.get("codigo"),
                str(r.get("fecha_inicio") or ""),
                str(r.get("fecha_fin") or ""),
                f"${r.get('nomina_plt') or 0:,.2f}",
                f"${r.get('nomina_pit') or 0:,.2f}",
                f"${r.get('nomina_tll') or 0:,.2f}",
                f"${r.get('total_semana') or 0:,.2f}",
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)

    def _auto_plt(self):
        sid = self.cmb_semana.currentData()
        if not sid:
            return
        try:
            tot = self.prod_repo.totales_semana(sid)
            self.sp_plt.setValue(float(tot["total_efectivo"] or 0))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save(self):
        sid = self.cmb_semana.currentData()
        if not sid:
            QMessageBox.warning(self, "Semana", "Selecciona una semana.")
            return
        try:
            self.repo.guardar(
                sid,
                nomina_plt=self.sp_plt.value(),
                nomina_pit=self.sp_pit.value(),
                nomina_tll=self.sp_tll.value(),
            )
            self.refresh()
            QMessageBox.information(self, "OK", "Resumen guardado.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
