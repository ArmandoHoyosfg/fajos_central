"""
Ventana principal — Fajos Piteados Central (escritorio).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QWidget,
)

from config import APP_NAME, APP_VERSION, RESOURCES_DIR, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from db import Database
from ui.production_widget import ProductionWidget
from ui.styles import DARK_QSS
from ui.summary_widget import SummaryWidget
from ui.workers_widget import WorkersWidget
from ui.trabajos_widget import TrabajosWidget
from ui.calendar_util import format_fecha_larga, format_fecha_corta, today


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        logo = RESOURCES_DIR / "logo.png"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))

        self.setStyleSheet(DARK_QSS)
        self._db = Database()

        self._build_menu()
        self._build_toolbar()
        self._build_tabs()
        self._build_statusbar()
        self._try_connect()

    def _build_menu(self):
        menubar = self.menuBar()

        m_file = menubar.addMenu("&Archivo")
        act_refresh = QAction("Actualizar datos", self)
        act_refresh.setShortcut(QKeySequence.Refresh)
        act_refresh.triggered.connect(self._refresh_all)
        m_file.addAction(act_refresh)
        m_file.addSeparator()
        act_quit = QAction("Salir", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_view = menubar.addMenu("&Ver")
        act_w = QAction("Trabajadores", self)
        act_w.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        act_j = QAction("Trabajos activos", self)
        act_j.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        act_p = QAction("Producción", self)
        act_p.triggered.connect(lambda: self.tabs.setCurrentIndex(2))
        act_s = QAction("Resumen", self)
        act_s.triggered.connect(lambda: self.tabs.setCurrentIndex(3))
        m_view.addAction(act_w)
        m_view.addAction(act_j)
        m_view.addAction(act_p)
        m_view.addAction(act_s)

        m_help = menubar.addMenu("A&yuda")
        act_about = QAction("Acerca de", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_refresh = QAction("Actualizar", self)
        act_refresh.triggered.connect(self._refresh_all)
        tb.addAction(act_refresh)
        tb.addSeparator()

        # Fecha actual (siempre visible)
        self.lbl_fecha = QLabel()
        self.lbl_fecha.setProperty("cssClass", "fecha")
        self.lbl_fecha.setStyleSheet(
            "QLabel { color: #c9a227; font-weight: 700; font-size: 13px; "
            "padding: 4px 14px; background: #313244; border-radius: 8px; }"
        )
        tb.addWidget(self.lbl_fecha)
        tb.addSeparator()

        # Búsqueda global (trabajadores)
        wrap = QWidget()
        row = QHBoxLayout(wrap)
        row.setContentsMargins(8, 0, 8, 0)
        row.addWidget(QLabel("Buscar:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Nombre o ubic de trabajador…")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.setMinimumWidth(220)
        self.search_box.textChanged.connect(self._on_global_search)
        self.search_box.returnPressed.connect(self._focus_workers_search)
        row.addWidget(self.search_box)
        tb.addWidget(wrap)

        self._update_fecha_label()
        self._fecha_timer = QTimer(self)
        self._fecha_timer.timeout.connect(self._update_fecha_label)
        self._fecha_timer.start(30_000)  # cada 30 s por si cruza medianoche

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.workers = WorkersWidget()
        self.trabajos = TrabajosWidget()
        self.production = ProductionWidget()
        self.summary = SummaryWidget()

        self.workers.data_changed.connect(self._refresh_all)
        self.trabajos.data_changed.connect(self._refresh_all)

        self.tabs.addTab(self.workers, "  Trabajadores  ")
        self.tabs.addTab(self.trabajos, "  Trabajos activos  ")
        self.tabs.addTab(self.production, "  Producción / Nómina  ")
        self.tabs.addTab(self.summary, "  Resumen  ")
        self.setCentralWidget(self.tabs)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_fecha_status = QLabel()
        self.lbl_db = QLabel("BD: —")
        self.status.addPermanentWidget(self.lbl_fecha_status)
        self.status.addPermanentWidget(self.lbl_db)
        self.status.showMessage("Listo")
        self._update_fecha_label()

    def _update_fecha_label(self) -> None:
        d = today()
        larga = format_fecha_larga(d)
        corta = format_fecha_corta(d)
        if hasattr(self, "lbl_fecha"):
            self.lbl_fecha.setText(f"📅  Hoy: {larga}")
            self.lbl_fecha.setToolTip(f"Fecha del sistema: {corta}")
        if hasattr(self, "lbl_fecha_status"):
            self.lbl_fecha_status.setText(f"  {corta}  ")
        # Propagar a producción por si cambió el día
        if hasattr(self, "production"):
            try:
                self.production.on_fecha_sistema_changed(d)
            except Exception:
                pass

    def _try_connect(self):

        try:
            self._db.connect()
            self.lbl_db.setText("BD: conectada")
            self.lbl_db.setStyleSheet("color: #a6e3a1;")
            self.status.showMessage("Conectado a fajos_central")
            self._refresh_all()
            QTimer.singleShot(600, self._show_startup_avisos)
        except Exception as e:
            self.lbl_db.setText("BD: sin conexión")
            self.lbl_db.setStyleSheet("color: #f38ba8;")
            self.status.showMessage("Sin conexión a la base de datos")
            QMessageBox.critical(
                self,
                "Conexión",
                f"No se pudo conectar a MariaDB:\n\n{e}\n\n"
                "Configura la conexión en el launcher (config.ini)\n"
                "o en la raíz del proyecto.",
            )

    def _show_startup_avisos(self) -> None:
        try:
            import sys
            from pathlib import Path
            root = Path(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from app.services.dia_service import DiaService
            msgs = DiaService().avisos_apertura()
            if not msgs:
                return
            texto = "\n\n".join(f"• {m}" for m in msgs)
            QMessageBox.information(self, "Avisos del día", texto)
        except Exception as e:
            self.status.showMessage(f"Avisos: {e}", 4000)

    def _on_global_search(self, text: str):

        self.workers.apply_filter(text)

    def _focus_workers_search(self):
        self.tabs.setCurrentIndex(0)
        self.workers.apply_filter(self.search_box.text())

    def _refresh_all(self):
        try:
            self.workers.refresh()
            self.trabajos.reload()
            self.production._load_semanas()
            self.production._load_trabajadores()
            self.production.refresh_table()
            self.summary.refresh()
            # reapply filter
            self.workers.apply_filter(self.search_box.text())
            self.status.showMessage("Datos actualizados", 3000)
        except Exception as e:
            self.status.showMessage(f"Error al actualizar: {e}", 5000)

    def _about(self):
        QMessageBox.about(
            self,
            f"Acerca de {APP_NAME}",
            f"<b>{APP_NAME}</b><br>"
            f"Versión <b>{APP_VERSION}</b><br><br>"
            "Sistema de nóminas del Taller de Fajos Central.<br>"
            "Python · PySide6 · MariaDB<br><br>"
            "• Catálogo de trabajadores (nombre + ubic)<br>"
            "• Captura semanal de producción (plata)<br>"
            "• Cálculo automático de totales<br>"
            "• Exportar nómina formal ordenada<br>"
            "• La app web (launcher) comparte la misma base<br><br>"
            "<span style='color:#a6adc8'>Misma identidad visual que la interfaz web.</span>",
        )

    def closeEvent(self, event):
        self._db.close()
        event.accept()
