"""
Pestaña de Producción / Nómina semanal de plata.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
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
)

from db import ProduccionRepo, SemanasRepo, TrabajadoresRepo
from services.excel_service import ExcelService


class ProductionWidget(QWidget):
    data_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.prod_repo = ProduccionRepo()
        self.sem_repo = SemanasRepo()
        self.trab_repo = TrabajadoresRepo()
        self.excel = ExcelService()
        self._semana_id: int | None = None
        self._build_ui()
        self._load_semanas()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel("Producción semanal — Plata")
        title.setProperty("cssClass", "title")
        layout.addWidget(title)

        # Selector de semana
        top = QHBoxLayout()
        top.addWidget(QLabel("Semana:"))
        self.cmb_semana = QComboBox()
        self.cmb_semana.setMinimumWidth(220)
        self.cmb_semana.currentIndexChanged.connect(self._on_semana_changed)
        top.addWidget(self.cmb_semana)

        self.btn_nueva_sem = QPushButton("Nueva semana")
        self.btn_nueva_sem.clicked.connect(self._on_nueva_semana)
        top.addWidget(self.btn_nueva_sem)
        top.addStretch()

        self.lbl_totales = QLabel("Totales: —")
        self.lbl_totales.setProperty("cssClass", "subtitle")
        top.addWidget(self.lbl_totales)
        layout.addLayout(top)

        # Formulario captura rápida
        box = QGroupBox("Agregar línea de producción")
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
        for d in ["sab", "dom", "lun", "mar", "mie", "jue", "vie"]:
            sp = QDoubleSpinBox()
            sp.setRange(0, 999)
            sp.setDecimals(2)
            sp.setSpecialValueText("—")
            sp.setValue(0)
            sp.setMaximumWidth(70)
            self.dias[d] = sp
            dias_layout.addWidget(QLabel(d[:3].capitalize()))
            dias_layout.addWidget(sp)

        form.addRow("Trabajador:", self.cmb_trabajador)
        form.addRow("Folio:", self.inp_folio)
        form.addRow("Modelo:", self.inp_modelo)
        form.addRow("Material:", self.cmb_material)
        form.addRow("$/Gr:", self.inp_tarifa)
        form.addRow("Gramos/día:", dias_layout)

        btn_add = QPushButton("Agregar a la semana")
        btn_add.setProperty("cssClass", "success")
        btn_add.clicked.connect(self._on_add_linea)
        form.addRow(btn_add)
        layout.addWidget(box)

        # Tabla
        self.table = QTableWidget()
        cols = [
            "ID", "Nombre", "Ubic", "Folio", "Modelo", "Mat", "$/Gr",
            "Sáb", "Dom", "Lun", "Mar", "Mié", "Jue", "Vie",
            "Total Gr", "Efectivo",
        ]
        self.table.setColumnCount(len(cols))
        self.table.setHorizontalHeaderLabels(cols)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # Botones inferiores
        bottom = QHBoxLayout()
        btn_del = QPushButton("Eliminar línea")
        btn_del.setProperty("cssClass", "danger")
        btn_del.clicked.connect(self._on_delete)
        btn_export_formal = QPushButton("Exportar Formal (orden Ubic→Nombre)")
        btn_export_formal.clicked.connect(self._on_export_formal)
        btn_export_captura = QPushButton("Exportar hoja de captura")
        btn_export_captura.clicked.connect(self._on_export_captura)
        btn_import = QPushButton("Importar desde Excel/CSV")
        btn_import.clicked.connect(self._on_import)

        bottom.addWidget(btn_del)
        bottom.addStretch()
        bottom.addWidget(btn_import)
        bottom.addWidget(btn_export_captura)
        bottom.addWidget(btn_export_formal)
        layout.addLayout(bottom)

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

    def _load_trabajadores(self):
        self.cmb_trabajador.clear()
        try:
            rows = self.trab_repo.listar(solo_plt=True, solo_activos=True)
            for r in rows:
                self.cmb_trabajador.addItem(
                    f"{r['nombre_mostrar']}  (Ubic {r['ubic']})",
                    (r["id"], r["nombre_mostrar"], r["ubic"]),
                )
        except Exception:
            pass

    def _on_semana_changed(self):
        self._semana_id = self.cmb_semana.currentData()
        self.refresh_table()

    def refresh_table(self):
        if not self._semana_id:
            self.table.setRowCount(0)
            self.lbl_totales.setText("Totales: —")
            return
        try:
            rows = self.prod_repo.listar_por_semana(self._semana_id)
            tot = self.prod_repo.totales_semana(self._semana_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r["id"], r["nombre"], r["ubic"], r.get("folio") or "",
                r.get("modelo") or "", r.get("material") or "",
                r.get("tarifa_gr") or "",
                r.get("gm_sab") or "", r.get("gm_dom") or "",
                r.get("gm_lun") or "", r.get("gm_mar") or "",
                r.get("gm_mie") or "", r.get("gm_jue") or "",
                r.get("gm_vie") or "",
                r.get("total_gramos") or 0,
                r.get("efectivo") or 0,
            ]
            for j, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(i, j, item)

        self.lbl_totales.setText(
            f"Líneas: {tot['lineas']}  |  Gramos: {tot['total_gramos']}  |  "
            f"Efectivo: ${tot['total_efectivo']}"
        )

    def _on_nueva_semana(self):
        from PySide6.QtWidgets import QInputDialog
        codigo, ok = QInputDialog.getText(self, "Nueva semana", "Código (ej: 25-08):")
        if not ok or not codigo.strip():
            return
        ini, ok1 = QInputDialog.getText(self, "Fecha inicio", "YYYY-MM-DD:")
        if not ok1:
            return
        fin, ok2 = QInputDialog.getText(self, "Fecha fin", "YYYY-MM-DD:")
        if not ok2:
            return
        try:
            sid = self.sem_repo.crear(codigo.strip(), ini.strip(), fin.strip())
            self._load_semanas()
            # Seleccionar la nueva
            idx = self.cmb_semana.findData(sid)
            if idx >= 0:
                self.cmb_semana.setCurrentIndex(idx)
            QMessageBox.information(self, "OK", f"Semana {codigo} creada.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_add_linea(self):
        if not self._semana_id:
            QMessageBox.warning(self, "Semana", "Selecciona o crea una semana.")
            return
        data = self.cmb_trabajador.currentData()
        if not data:
            QMessageBox.warning(self, "Trabajador", "Selecciona un trabajador.")
            return
        tid, nombre, ubic = data
        payload = {
            "trabajador_id": tid,
            "nombre": nombre,
            "ubic": ubic,
            "folio": self.inp_folio.text().strip() or None,
            "modelo": self.inp_modelo.text().strip() or None,
            "material": self.cmb_material.currentText(),
            "tarifa_gr": self.inp_tarifa.value(),
        }
        for d, sp in self.dias.items():
            val = sp.value()
            payload[f"gm_{d}"] = val if val > 0 else None

        try:
            self.prod_repo.insertar(self._semana_id, payload)
            self.refresh_table()
            self.data_changed.emit()
            # limpiar días
            for sp in self.dias.values():
                sp.setValue(0)
            self.inp_folio.clear()
            self.inp_modelo.clear()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_delete(self):
        row = self.table.currentRow()
        if row < 0:
            return
        pid = int(self.table.item(row, 0).text())
        if QMessageBox.question(self, "Confirmar", "¿Eliminar esta línea?") != QMessageBox.Yes:
            return
        try:
            self.prod_repo.eliminar(pid)
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
            rows = self.prod_repo.listar_por_semana(self._semana_id)
            codigo = self.cmb_semana.currentText().split()[0]
            self.excel.exportar_nomina_formal(path, rows, codigo_semana=codigo)
            QMessageBox.information(self, "Exportado", f"Guardado en:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_export_captura(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar hoja de captura", "Nomina_Captura.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            trabs = self.trab_repo.listar(solo_plt=True, solo_activos=True)
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            self.excel.exportar_captura(path, trabs, codigo_semana=codigo)
            QMessageBox.information(self, "Exportado", f"Guardado en:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_import(self):
        if not self._semana_id:
            QMessageBox.warning(self, "Semana", "Selecciona una semana primero.")
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar producción", "", "Excel/CSV (*.xlsx *.xls *.csv)"
        )
        if not path:
            return
        try:
            records = self.excel.importar_produccion_csv(path)
            count = 0
            for rec in records:
                self.prod_repo.insertar(self._semana_id, rec)
                count += 1
            self.refresh_table()
            self.data_changed.emit()
            QMessageBox.information(self, "Importado", f"{count} líneas importadas.")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def reload_workers(self):
        self._load_trabajadores()
