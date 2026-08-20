"""
Pestaña de Producción / Nómina semanal de plata.
Incluye captura de un solo día, edición en tabla, colores por material y filtro.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QInputDialog,
    QCheckBox,
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
    QToolButton,
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

from db import ProduccionRepo, SemanasRepo, TrabajadoresRepo, TarifasRepo
from services.excel_service import ExcelService
from ui.calendar_util import (
    encontrar_semana_actual,
    etiqueta_semana,
    format_fecha_larga,
    sugerir_codigo_semana,
    today,
)

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
TARIFA_DEFAULT = {"AG3": 12.0, "AG4": 13.0, "DOL": 13.0, "DLO": 13.0}

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
        self.tarifas_repo = TarifasRepo()
        self._tarifas = {}
        self._semana_cerrada = False
        self._semana_id: int | None = None
        self._all_rows: list[dict] = []
        self._updating_cell = False
        self._last_material = "AG3"
        self._last_tarifa = 12.0
        self._toast_timer = None
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
        sub = QLabel("Captura por día · Enter guarda · Doble clic edita gramos")
        sub.setProperty("cssClass", "subtitle")
        layout.addWidget(sub)
        self.lbl_toast = QLabel("")
        self.lbl_toast.setProperty("cssClass", "toast")
        self.lbl_toast.setVisible(False)
        layout.addWidget(self.lbl_toast)

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
        self.btn_semana_actual = QPushButton("★ Semana actual")
        self.btn_semana_actual.setToolTip("Crea o selecciona la semana sáb–vie de hoy")
        self.btn_semana_actual.clicked.connect(self._on_semana_actual)
        top.addWidget(self.btn_semana_actual)
        self.btn_cerrar_sem = QPushButton("🔒 Cerrar semana")
        self.btn_cerrar_sem.setToolTip("Bloquea edición de producción (formal definitivo)")
        self.btn_cerrar_sem.clicked.connect(self._on_cerrar_semana)
        top.addWidget(self.btn_cerrar_sem)
        self.btn_reabrir_sem = QPushButton("🔓 Reabrir")
        self.btn_reabrir_sem.clicked.connect(self._on_reabrir_semana)
        top.addWidget(self.btn_reabrir_sem)
        top.addStretch()
        self.lbl_totales = QLabel("Totales: —")
        self.lbl_totales.setProperty("cssClass", "kpi")
        top.addWidget(self.lbl_totales)
        layout.addLayout(top)
        self.lbl_semana_ctx = QLabel("")
        self.lbl_semana_ctx.setProperty("cssClass", "subtitle")
        self.lbl_semana_ctx.setWordWrap(True)
        layout.addWidget(self.lbl_semana_ctx)

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

        # --- Línea completa (colapsada por defecto) ---
        self.btn_toggle_full = QToolButton()
        self.btn_toggle_full.setText("➕  Línea completa (varios días / folio)  — clic para expandir")
        self.btn_toggle_full.setCheckable(True)
        self.btn_toggle_full.setChecked(False)
        self.btn_toggle_full.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.btn_toggle_full.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.btn_toggle_full.setStyleSheet(
            "QToolButton { text-align: left; padding: 8px 12px; background: #313244; "
            "border: 1px solid #45475a; border-radius: 8px; color: #cdd6f4; font-weight: 600; }"
            "QToolButton:checked { background: #45475a; }"
        )
        layout.addWidget(self.btn_toggle_full)

        box = QGroupBox()
        box.setTitle("")
        box.setVisible(False)
        self.box_full = box
        self.btn_toggle_full.toggled.connect(lambda on: (
            box.setVisible(on),
            self.btn_toggle_full.setText(
                "➖  Ocultar línea completa" if on
                else "➕  Línea completa (varios días / folio)  — clic para expandir"
            ),
        ))
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

        # Filtro + herramientas
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Filtrar:"))
        self.inp_filter = QLineEdit()
        self.inp_filter.setPlaceholderText("Nombre, folio o material…")
        self.inp_filter.setClearButtonEnabled(True)
        self.inp_filter.textChanged.connect(self._apply_filter)
        filt.addWidget(self.inp_filter)
        self.chk_solo_hoy = QCheckBox("Solo sin gramos hoy")
        self.chk_solo_hoy.setToolTip("Muestra líneas que aún no tienen gramos en el día de hoy")
        self.chk_solo_hoy.toggled.connect(lambda: self._apply_filter(self.inp_filter.text()))
        filt.addWidget(self.chk_solo_hoy)
        self.chk_sin_firma = QCheckBox("Sin firmar")
        self.chk_sin_firma.setToolTip("Solo líneas pendientes de firma")
        self.chk_sin_firma.toggled.connect(lambda: self._apply_filter(self.inp_filter.text()))
        filt.addWidget(self.chk_sin_firma)
        btn_copy = QPushButton("Copiar día → hoy")
        btn_copy.setToolTip("Copia gramos del día anterior al día de hoy en la línea seleccionada")
        btn_copy.clicked.connect(self._on_copy_prev_day)
        filt.addWidget(btn_copy)
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
        self.table.cellDoubleClicked.connect(self._on_day_double_click)
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
        btn_export_pdf = QPushButton("📕 Formal PDF")
        btn_export_pdf.clicked.connect(self._on_export_pdf)
        btn_export_captura = QPushButton("📋 Captura")
        btn_export_captura.clicked.connect(self._on_export_captura)
        btn_import = QPushButton("Importar Excel/CSV")
        btn_import.clicked.connect(self._on_import)
        bottom.addWidget(btn_del)
        bottom.addStretch()
        bottom.addWidget(btn_import)
        bottom.addWidget(btn_export_captura)
        bottom.addWidget(btn_export_formal)
        bottom.addWidget(btn_export_pdf)
        layout.addLayout(bottom)
        layout.addStretch(1)

        scroll.setWidget(content)
        outer.addWidget(scroll)

        self._load_trabajadores()
        self._setup_shortcuts()
        self.cmb_dia_mat.currentTextChanged.connect(self._on_mat_changed_day)
        self.cmb_material.currentTextChanged.connect(self._on_mat_changed_full)
        self._load_tarifas()

    def _load_semanas(self):
        self.cmb_semana.blockSignals(True)
        self.cmb_semana.clear()
        actual_id = None
        try:
            semanas = self.sem_repo.listar()
            actual = encontrar_semana_actual(semanas, today())
            if actual:
                actual_id = actual.get("id")
            for s in semanas:
                self.cmb_semana.addItem(etiqueta_semana(s, today()), s["id"])
        except Exception as e:
            QMessageBox.warning(self, "Semanas", f"No se pudieron cargar semanas:\n{e}")
        self.cmb_semana.blockSignals(False)

        # Seleccionar semana que contiene la fecha de hoy
        if actual_id is not None:
            idx = self.cmb_semana.findData(actual_id)
            if idx >= 0:
                self.cmb_semana.setCurrentIndex(idx)
        elif self.cmb_semana.count():
            self.cmb_semana.setCurrentIndex(0)

        self._update_semana_context_label()
        if self.cmb_semana.count():
            self._on_semana_changed()
        else:
            self.lbl_empty.setText(
                "No hay semanas. Crea una con «Nueva semana» "
                "(se sugerirá el rango sáb–vie actual)."
            )
            self.lbl_totales.setText("Totales: —")


    def _load_trabajadores(self):
        for cmb in (self.cmb_trabajador, self.cmb_dia_trab):
            cmb.clear()
        try:
            rows = self.trab_repo.listar(solo_plt=False, solo_activos=True)
            for r in rows:
                label = f"{r['nombre_mostrar']}  (Ubic {r['ubic']})"
                data = (r["id"], r["nombre_mostrar"], r["ubic"])
                self.cmb_trabajador.addItem(label, data)
                self.cmb_dia_trab.addItem(label, data)
        except Exception:
            pass


    def _update_semana_context_label(self) -> None:
        hoy = today()
        texto_hoy = format_fecha_larga(hoy)
        sid = self.cmb_semana.currentData()
        if sid is None:
            self.lbl_semana_ctx.setText(
                f"Hoy es {texto_hoy}. No hay semana seleccionada."
            )
            return
        # recuperar fechas del ítem actual desde listar es costoso; parse etiqueta
        label = self.cmb_semana.currentText()
        if "★ ACTUAL" in label:
            estado = "Estás en la <b>semana actual</b> del calendario."
        else:
            estado = (
                "La semana seleccionada <b>no incluye hoy</b>. "
                "Cambia a la marcada ★ ACTUAL o crea la semana correspondiente."
            )
        if self._semana_cerrada:
            estado += " · <b style='color:#f38ba8'>SEMANA CERRADA</b> (solo lectura)"
        self.lbl_semana_ctx.setText(f"📅 Hoy: {texto_hoy}.  {estado}")

    def on_fecha_sistema_changed(self, d=None) -> None:
        """Llamado desde MainWindow cuando cambia el día del sistema."""
        self._update_semana_context_label()
        # Re-evaluar selección de semana actual
        try:
            semanas = self.sem_repo.listar()
            actual = encontrar_semana_actual(semanas, d or today())
            if actual and self.cmb_semana.currentData() != actual.get("id"):
                # solo auto-cambiar si el usuario estaba en una semana que ya no es "hoy"
                # Evitar sorpresas: solo actualizar etiquetas y sugerir
                for i in range(self.cmb_semana.count()):
                    txt = self.cmb_semana.itemText(i)
                    if "★ ACTUAL" in txt or self.cmb_semana.itemData(i) == actual.get("id"):
                        # refresh labels without forcing switch every 30s
                        break
                self._load_semanas()
        except Exception:
            pass

    def _on_semana_changed(self):
        self._semana_id = self.cmb_semana.currentData()
        cerrada = False
        if self._semana_id:
            try:
                cerrada = bool(self.sem_repo.esta_cerrada(self._semana_id))
            except Exception:
                cerrada = False
        self._set_edit_enabled(not cerrada)
        self._update_semana_context_label()
        self.refresh_table()


    def _on_semana_actual(self) -> None:
        """Crea o selecciona la semana del calendario que contiene hoy."""
        try:
            semanas = self.sem_repo.listar()
            actual = encontrar_semana_actual(semanas, today())
            if actual:
                idx = self.cmb_semana.findData(actual["id"])
                if idx >= 0:
                    self.cmb_semana.setCurrentIndex(idx)
                self._show_toast(f"Semana actual: {actual.get('codigo')}")
                return
            codigo, sab, vie = sugerir_codigo_semana(today())
            new_id = self.sem_repo.crear(
                codigo, sab, vie, anio=sab.year, notas="Semana actual (auto)",
            )
            self._load_semanas()
            idx = self.cmb_semana.findData(new_id)
            if idx >= 0:
                self.cmb_semana.setCurrentIndex(idx)
            self._show_toast(f"Creada semana {codigo}")
        except Exception as e:
            self._show_toast(str(e), error=True)

    def _on_nueva_semana(self):
        from PySide6.QtWidgets import QDialog, QDialogButtonBox, QDateEdit

        dlg = QDialog(self)
        dlg.setWindowTitle("Nueva semana")
        fl = QFormLayout(dlg)
        codigo = QLineEdit()
        sug_cod, sug_ini, sug_fin = sugerir_codigo_semana(today())
        codigo.setPlaceholderText(sug_cod)
        codigo.setText(sug_cod)
        ini = QDateEdit(calendarPopup=True)
        fin = QDateEdit(calendarPopup=True)
        ini.setDate(sug_ini)
        fin.setDate(sug_fin)
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


    def _show_toast(self, msg: str, error: bool = False) -> None:
        """Confirmación discreta (sin modal)."""
        from PySide6.QtCore import QTimer
        self.lbl_toast.setText(("⚠ " if error else "✓ ") + msg)
        self.lbl_toast.setStyleSheet(
            "color: #f38ba8; background: #313244; padding: 6px 12px; border-radius: 6px;"
            if error else
            "color: #a6e3a1; background: #313244; padding: 6px 12px; border-radius: 6px;"
        )
        self.lbl_toast.setVisible(True)
        if self._toast_timer:
            self._toast_timer.stop()
        self._toast_timer = QTimer(self)
        self._toast_timer.setSingleShot(True)
        self._toast_timer.timeout.connect(lambda: self.lbl_toast.setVisible(False))
        self._toast_timer.start(3200)

    def _setup_shortcuts(self) -> None:
        sc_save = QShortcut(QKeySequence(Qt.Key_Return), self)
        sc_save.activated.connect(self._on_guardar_dia)
        sc_save2 = QShortcut(QKeySequence(Qt.Key_Enter), self)
        sc_save2.activated.connect(self._on_guardar_dia)
        sc_left = QShortcut(QKeySequence(Qt.Key_Left), self)
        sc_left.activated.connect(lambda: self._nudge_day(-1))
        sc_right = QShortcut(QKeySequence(Qt.Key_Right), self)
        sc_right.activated.connect(lambda: self._nudge_day(1))

    def _nudge_day(self, delta: int) -> None:
        if not self.spin_dia_gr.hasFocus() and not self.cmb_dia.hasFocus():
            # only when day panel is the natural focus context
            if self.cmb_dia_trab.hasFocus() or self.spin_dia_gr.hasFocus() or self.cmb_dia.hasFocus():
                pass
        i = self.cmb_dia.currentIndex()
        n = self.cmb_dia.count()
        self.cmb_dia.setCurrentIndex((i + delta) % n)


    def _load_tarifas(self) -> None:
        try:
            self._tarifas = self.tarifas_repo.mapa() or {}
        except Exception:
            self._tarifas = {"AG3": 12.0, "AG4": 13.0, "DOL": 13.0, "DLO": 13.0}

    def _tarifa_material(self, mat: str) -> float:
        if not self._tarifas:
            self._load_tarifas()
        return float(self._tarifas.get((mat or "AG3").upper(), 12.0))

    def _set_edit_enabled(self, enabled: bool) -> None:
        self._semana_cerrada = not enabled
        for w in (
            getattr(self, "cmb_dia_trab", None),
            getattr(self, "spin_dia_gr", None),
            getattr(self, "cmb_dia", None),
        ):
            if w is not None:
                w.setEnabled(enabled)
        if hasattr(self, "btn_toggle_full"):
            self.btn_toggle_full.setEnabled(enabled)
        if hasattr(self, "box_full"):
            self.box_full.setEnabled(enabled)
        if enabled:
            self.table.setEditTriggers(
                QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
            )
        else:
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        if hasattr(self, "btn_cerrar_sem"):
            self.btn_cerrar_sem.setEnabled(enabled and self._semana_id is not None)
        if hasattr(self, "btn_reabrir_sem"):
            self.btn_reabrir_sem.setEnabled((not enabled) and self._semana_id is not None)

    def _on_cerrar_semana(self) -> None:
        if not self._semana_id:
            return
        if not QMessageBox.question(
            self,
            "Cerrar semana",
            "¿Cerrar esta semana?\nNo se podrá editar producción hasta reabrirla.\n"
            "Úsalo cuando el formal ya esté listo para pago.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) == QMessageBox.Yes:
            return
        try:
            self.sem_repo.cerrar(self._semana_id, usuario="desktop")
            self._set_edit_enabled(False)
            self._update_semana_context_label()
            self._show_toast("Semana cerrada.")
        except Exception as e:
            self._show_toast(str(e), error=True)

    def _on_reabrir_semana(self) -> None:
        if not self._semana_id:
            return
        if not QMessageBox.question(
            self, "Reabrir", "¿Reabrir la semana para permitir ediciones?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes:
            return
        try:
            self.sem_repo.reabrir(self._semana_id)
            self._set_edit_enabled(True)
            self._update_semana_context_label()
            self._show_toast("Semana reabierta.")
        except Exception as e:
            self._show_toast(str(e), error=True)


    def _on_mat_changed_day(self, mat: str) -> None:
        tar = self._tarifa_material(mat)
        self.spin_dia_tarifa.setValue(tar)
        self._last_material = mat
        self._last_tarifa = tar

    def _on_mat_changed_full(self, mat: str) -> None:
        tar = self._tarifa_material(mat)
        self.inp_tarifa.setValue(tar)
        self._last_material = mat
        self._last_tarifa = tar

    def _warn_folio_dup(self, folio: str | None, exclude_id: int | None = None) -> None:
        if not folio or not self._semana_id:
            return
        for r in self._all_rows:
            if exclude_id and r.get("id") == exclude_id:
                continue
            if str(r.get("folio") or "").strip().upper() == folio.strip().upper():
                self._show_toast(
                    f"El folio «{folio}» ya existe en esta semana (id={r.get('id')}).",
                    error=True,
                )
                return

    def _on_copy_prev_day(self) -> None:
        """Copia gramos del día anterior al día de hoy en la fila seleccionada."""
        row = self.table.currentRow()
        if row < 0:
            self._show_toast("Selecciona una línea en la tabla.", error=True)
            return
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        prod_id = id_item.data(Qt.UserRole) or int(id_item.text())
        today_key = DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")
        order = [k for k, _ in DAY_KEYS]
        try:
            ti = order.index(today_key)
        except ValueError:
            ti = 0
        if ti == 0:
            self._show_toast("No hay día anterior a copiar (hoy es el primero).", error=True)
            return
        prev_key = order[ti - 1]
        # read current values from _all_rows
        rec = next((r for r in self._all_rows if r.get("id") == prod_id), None)
        if not rec:
            self._show_toast("Línea no encontrada.", error=True)
            return
        prev_val = rec.get(prev_key)
        if prev_val is None or float(prev_val or 0) == 0:
            self._show_toast("El día anterior no tiene gramos.", error=True)
            return
        try:
            self.prod_repo.actualizar_gramos_dia(int(prod_id), today_key, float(prev_val))
            self.refresh_table()
            self.data_changed.emit()
            self._show_toast(f"Copiado {prev_val} g del día anterior → hoy.")
        except Exception as e:
            self._show_toast(str(e), error=True)


    def _on_guardar_dia(self):
        if not self._semana_id:
            self._show_toast("Selecciona o crea una semana.", error=True)
            return
        if self._semana_cerrada:
            self._show_toast("Semana cerrada: no se puede editar.", error=True)
            return
        tid, nombre, ubic = self._trabajador_data(self.cmb_dia_trab)
        if not nombre:
            self._show_toast("Elige un trabajador.", error=True)
            return
        gr = self.spin_dia_gr.value()
        if gr <= 0:
            self._show_toast("Indica los gramos del día (> 0).", error=True)
            return
        col = self.cmb_dia.currentData()
        folio = self.inp_dia_folio.text().strip() or None
        material = self.cmb_dia_mat.currentText()
        tarifa = self.spin_dia_tarifa.value()
        expected = TARIFA_DEFAULT.get(material)
        if expected is not None and abs(tarifa - expected) > 0.001:
            # aviso suave; no bloquea
            self._show_toast(
                f"Tarifa {tarifa} distinta a la habitual de {material} ({expected}). Se guarda igual."
            )
        try:
            existing = self.prod_repo.buscar_linea(self._semana_id, nombre, int(ubic) if ubic else 0, folio)
            if existing:
                self._warn_folio_dup(folio, exclude_id=existing.get("id"))
                self.prod_repo.actualizar_gramos_dia(existing["id"], col, gr)
                msg = f"{nombre}: {self.cmb_dia.currentText()} = {gr:g} g"
            else:
                if not ubic:
                    self._show_toast("Selecciona un trabajador de la lista (con ubic).", error=True)
                    return
                self._warn_folio_dup(folio)
                payload = {
                    "trabajador_id": tid,
                    "nombre": nombre,
                    "ubic": int(ubic),
                    "folio": folio,
                    "modelo": self.inp_dia_modelo.text().strip() or None,
                    "material": material,
                    "tarifa_gr": tarifa,
                    "gm_sab": None, "gm_dom": None, "gm_lun": None,
                    "gm_mar": None, "gm_mie": None, "gm_jue": None, "gm_vie": None,
                }
                payload[col] = gr
                self.prod_repo.insertar(self._semana_id, payload)
                msg = f"Nueva línea · {nombre} · {self.cmb_dia.currentText()} {gr:g} g"
            self._last_material = material
            self._last_tarifa = tarifa
            self.spin_dia_gr.setValue(0)
            self.spin_dia_gr.setFocus()
            self.refresh_table()
            self.data_changed.emit()
            self._show_toast(msg)
        except Exception as e:
            self._show_toast(str(e), error=True)

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


    def _recalc_totales_ui(self, rows: list | None = None) -> None:
        """Recalcula KPIs en pantalla a partir de las filas visibles (tiempo real)."""
        rows = rows if rows is not None else getattr(self, "_all_rows", [])
        n = len(rows)
        gr = 0.0
        ef = 0.0
        for r in rows:
            try:
                gr += float(r.get("total_gramos") or 0)
            except (TypeError, ValueError):
                pass
            try:
                ef += float(r.get("efectivo") or 0)
            except (TypeError, ValueError):
                pass
        self.lbl_totales.setText(
            f"Líneas: {n}   ·   Gramos: {gr:g}   ·   Efectivo: ${ef:,.2f}"
        )

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
            if getattr(self, "chk_solo_hoy", None) and self.chk_solo_hoy.isChecked():
                today_key = DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")
                rows = [
                    r for r in rows
                    if not r.get(today_key) or float(r.get(today_key) or 0) == 0
                ]
            if getattr(self, "chk_sin_firma", None) and self.chk_sin_firma.isChecked():
                rows = [r for r in rows if not r.get("firmado")]
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
                    # Solo HOY editable directo; otros días: doble clic + confirmación
                    if j in self._day_cols:
                        if self._day_cols[j] == today_key and not getattr(self, "_semana_cerrada", False):
                            item.setFlags(item.flags() | Qt.ItemIsEditable)
                            item.setForeground(QBrush(QColor("#c9a227")))
                            item.setToolTip("Hoy — editable")
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                            item.setToolTip("Doble clic para editar (requiere confirmación)")
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    if bg and j > 0:
                        item.setBackground(QBrush(bg))
                        if fg:
                            item.setForeground(QBrush(fg))
                    if j == 0:
                        item.setData(Qt.UserRole, r.get("id"))
                    self.table.setItem(i, j, item)
            self._lock_non_today_cells()
        finally:
            self._updating_cell = False



    def _lock_non_today_cells(self) -> None:
        """Solo el día de hoy es editable directo; el resto exige doble clic + confirmación."""
        hoy = self._col_hoy_key()
        for row in range(self.table.rowCount()):
            for col, col_name in self._day_cols.items():
                item = self.table.item(row, col)
                if not item:
                    continue
                if col_name == hoy and not getattr(self, "_semana_cerrada", False):
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                    item.setToolTip("Hoy — editable")
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                    item.setToolTip("Doble clic para editar (requiere confirmación)")

    def _col_hoy_key(self) -> str:
        return DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")

    def _on_day_double_click(self, row: int, col: int) -> None:
        """Días distintos de hoy: bloqueados; se editan solo con confirmación."""
        if col not in self._day_cols:
            return
        col_name = self._day_cols[col]
        if col_name == self._col_hoy_key():
            return  # hoy se edita normal
        if getattr(self, "_semana_cerrada", False):
            QMessageBox.information(self, "Cerrada", "La semana está cerrada.")
            return
        id_item = self.table.item(row, 0)
        if not id_item:
            return
        try:
            prod_id = int(id_item.text())
        except ValueError:
            return
        labels = {
            "gm_sab": "Sábado", "gm_dom": "Domingo", "gm_lun": "Lunes",
            "gm_mar": "Martes", "gm_mie": "Miércoles", "gm_jue": "Jueves", "gm_vie": "Viernes",
        }
        lab = labels.get(col_name, col_name)
        old_val = 0.0
        for r in self._all_rows:
            if r.get("id") == prod_id:
                try:
                    old_val = float(r.get(col_name) or 0)
                except (TypeError, ValueError):
                    old_val = 0.0
                break
        msg = (
            f"El {lab} no es el día de hoy.\n"
            f"Valor actual: {old_val:g} g\n\n"
            "¿Confirmas editar este día?"
        )
        if QMessageBox.question(
            self, "Editar día bloqueado", msg,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        val, ok = QInputDialog.getDouble(
            self, f"Gramos — {lab}", f"Gramos para {lab}:",
            old_val if old_val else 0.0, 0.0, 9999.0, 2,
        )
        if not ok:
            return
        gramos = None if val == 0 else val
        try:
            self.prod_repo.actualizar_gramos_dia(prod_id, col_name, gramos)
            for r in self._all_rows:
                if r.get("id") == prod_id:
                    r[col_name] = gramos
                    days = list(self._day_cols.values())
                    tg = sum(float(r.get(d) or 0) for d in days)
                    r["total_gramos"] = tg
                    try:
                        r["efectivo"] = round(tg * float(r.get("tarifa_gr") or 0), 2)
                    except (TypeError, ValueError):
                        pass
                    break
            self._recalc_totales_ui()
            self.refresh_table()
            self.data_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_cell_changed(self, item: QTableWidgetItem):
        # Guard: solo hoy vía edición directa

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
        # Confirmación día pasado con datos
        ordered = ["gm_sab", "gm_dom", "gm_lun", "gm_mar", "gm_mie", "gm_jue", "gm_vie"]
        labels = {"gm_sab": "Sábado", "gm_dom": "Domingo", "gm_lun": "Lunes",
                  "gm_mar": "Martes", "gm_mie": "Miércoles", "gm_jue": "Jueves", "gm_vie": "Viernes"}
        hoy_key = DAY_BY_WEEKDAY.get(date.today().weekday(), "gm_lun")
        old_val = 0.0
        try:
            id_item = self.table.item(row, 0)
            # find previous display
            old_text = item.text()  # already new - need from all_rows
            for r in self._all_rows:
                if r.get("id") == prod_id:
                    old_val = float(r.get(col_name) or 0)
                    break
        except Exception:
            old_val = 0.0
        try:
            is_past = ordered.index(col_name) < ordered.index(hoy_key)
        except ValueError:
            is_past = False
        if is_past and old_val > 0:
            if QMessageBox.question(
                self, "Día pasado",
                f"Vas a modificar el {labels.get(col_name, col_name)}, que ya tiene {old_val:g} g.\n"
                "¿Confirmas editar un día pasado con información?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            ) != QMessageBox.Yes:
                self.refresh_table()
                return
        try:
            self.prod_repo.actualizar_gramos_dia(int(prod_id), col_name, gramos)
            self.refresh_table()
            self.data_changed.emit()
            self._show_toast(f"Guardado: {gramos if gramos is not None else 'vacío'} g")
        except Exception as e:
            self._show_toast(str(e), error=True)
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

    def _on_suministro(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Suministro diario", "suministro_hoy.xlsx", "Excel (*.xlsx)",
        )
        if not path:
            return
        try:
            import sys
            from pathlib import Path as P
            root = P(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from app.services.dia_service import DiaService
            st = DiaService().estado_hoy()
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            self.excel.exportar_suministro(
                path, st.get("trabajos") or self._all_rows,
                fecha=st["fecha"], label_dia=st["label_dia"], codigo_semana=codigo,
            )
            self._show_toast(f"Suministro: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Suministro", str(e))

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
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            fi = ff = None
            try:
                sem = self.sem_repo.obtener(self._semana_id) if self._semana_id else None
                if sem:
                    codigo = sem.get("codigo") or codigo
                    fi = str(sem.get("fecha_inicio") or "")[:10] or None
                    ff = str(sem.get("fecha_fin") or "")[:10] or None
            except Exception:
                pass
            self.excel.exportar_nomina_formal(
                path, rows, codigo_semana=codigo,
                fecha_inicio=fi, fecha_fin=ff,
            )
            # Copia automática en exports/
            try:
                from pathlib import Path as _P
                import shutil
                root = _P(__file__).resolve().parents[2]
                exp_dir = root / "exports"
                exp_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime as _dt
                stamp = _dt.now().strftime("%Y%m%d_%H%M%S")
                backup = exp_dir / f"formal_{codigo}_{stamp}.xlsx"
                shutil.copy2(path, backup)
                self._show_toast(f"Formal exportado + backup: {backup.name}")
            except Exception:
                self._show_toast(f"Formal exportado: {path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _on_export_pdf(self):
        if not self._semana_id:
            self._show_toast("Selecciona una semana.", error=True)
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar Formal PDF", "Nomina_Formal.pdf", "PDF (*.pdf)"
        )
        if not path:
            return
        try:
            codigo = self.cmb_semana.currentText().split()[0] if self.cmb_semana.currentText() else ""
            self.excel.exportar_pdf_formal(path, self._all_rows, codigo_semana=codigo)
            try:
                from pathlib import Path as _P
                import shutil
                from datetime import datetime as _dt
                root = _P(__file__).resolve().parents[2]
                exp_dir = root / "exports"
                exp_dir.mkdir(parents=True, exist_ok=True)
                backup = exp_dir / f"formal_{codigo}_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                shutil.copy2(path, backup)
                self._show_toast(f"PDF + backup: {backup.name}")
            except Exception:
                self._show_toast(f"PDF guardado: {path}")
        except Exception as e:
            self._show_toast(str(e), error=True)
            QMessageBox.critical(self, "PDF", str(e))

    def _on_export_captura(self):

        if not self._semana_id:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Exportar captura", "Nomina_Captura.xlsx", "Excel (*.xlsx)"
        )
        if not path:
            return
        try:
            trabs = self.trab_repo.listar(solo_plt=False, solo_activos=True)
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
