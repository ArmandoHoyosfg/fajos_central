"""
Ventana principal de la aplicación.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QToolBar,
)

from config import APP_NAME, APP_VERSION, WINDOW_MIN_HEIGHT, WINDOW_MIN_WIDTH
from db import Database
from ui.production_widget import ProductionWidget
from ui.styles import DARK_QSS
from ui.summary_widget import SummaryWidget
from ui.workers_widget import WorkersWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME}  v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
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
        act_quit = QAction("Salir", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        m_file.addAction(act_quit)

        m_db = menubar.addMenu("&Base de datos")
        act_reconnect = QAction("Reconectar", self)
        act_reconnect.triggered.connect(self._try_connect)
        m_db.addAction(act_reconnect)

        m_help = menubar.addMenu("A&yuda")
        act_about = QAction("Acerca de", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_refresh = QAction("🔄 Actualizar todo", self)
        act_refresh.triggered.connect(self._refresh_all)
        tb.addAction(act_refresh)

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.workers = WorkersWidget()
        self.production = ProductionWidget()
        self.summary = SummaryWidget()

        self.workers.data_changed.connect(self.production.reload_workers)
        self.production.data_changed.connect(self.summary.refresh)

        self.tabs.addTab(self.workers, "  Trabajadores  ")
        self.tabs.addTab(self.production, "  Producción / Nómina  ")
        self.tabs.addTab(self.summary, "  Resumen  ")
        self.setCentralWidget(self.tabs)

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Listo")

    def _try_connect(self):
        try:
            self._db.connect()
            self.status.showMessage("✓ Conectado a fajos_central")
            self._refresh_all()
        except Exception as e:
            self.status.showMessage("✗ Sin conexión a la base de datos")
            QMessageBox.critical(
                self,
                "Conexión",
                f"No se pudo conectar a MariaDB:\n\n{e}\n\n"
                "Revisa host, usuario y contraseña en config.py",
            )

    def _refresh_all(self):
        self.workers.refresh()
        self.production._load_semanas()
        self.production._load_trabajadores()
        self.production.refresh_table()
        self.summary.refresh()
        self.status.showMessage("Datos actualizados", 3000)

    def _about(self):
        QMessageBox.about(
            self,
            "Acerca de",
            f"<b>{APP_NAME}</b><br>"
            f"Versión {APP_VERSION}<br><br>"
            "Sistema de nóminas del Taller de Fajos Central.<br>"
            "Python + PySide6 + MariaDB<br><br>"
            "• Catálogo de trabajadores<br>"
            "• Captura semanal de producción (plata)<br>"
            "• Cálculo automático de totales<br>"
            "• Importar / Exportar Excel potenciado<br>"
            "• Resumen de nóminas PLT + PIT + TLL",
        )

    def closeEvent(self, event):
        self._db.close()
        event.accept()
