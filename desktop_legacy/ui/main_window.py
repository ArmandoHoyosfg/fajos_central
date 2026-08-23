import webbrowser
"""
Ventana principal — Fajos Piteados Central (escritorio).
Navegación alineada con la web: Inicio, Solo hoy, Plata, Pita, Taller, Folios, Trabajadores.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
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
from ui.styles import build_qss
from ui.summary_widget import SummaryWidget
from ui.workers_widget import WorkersWidget
from ui.trabajos_widget import TrabajosWidget
from ui.parity_widgets import SoloHoyWidget, AreaNominaWidget, DashboardLiteWidget
from ui.calendar_util import format_fecha_larga, format_fecha_corta, today


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._theme = "oscuro"
        self.setWindowTitle(f"{APP_NAME}  ·  v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        logo = RESOURCES_DIR / "logo.png"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))

        self.setStyleSheet(build_qss(self._theme))
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
        labels = [
            "Inicio", "Solo hoy", "Plata", "Pita", "Taller", "Folios", "Trabajadores", "Resumen",
        ]
        for i, name in enumerate(labels):
            act = QAction(name, self)
            act.triggered.connect(lambda checked=False, idx=i: self.tabs.setCurrentIndex(idx))
            m_view.addAction(act)

        m_theme = menubar.addMenu("&Tema")
        for key, label in [("oscuro", "Oscuro"), ("claro", "Claro"), ("taller", "Taller")]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, k=key: self._set_theme(k))
            m_theme.addAction(act)

        m_help = menubar.addMenu("A&yuda")
        act_web = QAction("Abrir interfaz web…", self)
        act_web.triggered.connect(self._open_web)
        m_help.addAction(act_web)
        act_parity = QAction("Qué hace la app vs la web…", self)
        act_parity.triggered.connect(self._show_parity)
        m_help.addAction(act_parity)
        m_help.addSeparator()
        act_about = QAction("Acerca de", self)
        act_about.triggered.connect(self._about)
        m_help.addAction(act_about)

    def _set_theme(self, key: str):
        self._theme = key
        self.setStyleSheet(build_qss(key))
        self.status.showMessage(f"Tema: {key}", 3000)

    def _build_toolbar(self):
        tb = QToolBar("Principal")
        tb.setMovable(False)
        self.addToolBar(tb)

        act_refresh = QAction("Actualizar", self)
        act_refresh.triggered.connect(self._refresh_all)
        tb.addAction(act_refresh)
        act_web = QAction("Abrir web", self)
        act_web.setToolTip("Abre la interfaz web completa (requiere servidor del launcher)")
        act_web.triggered.connect(self._open_web)
        tb.addAction(act_web)
        tb.addSeparator()

        self.lbl_fecha = QLabel()
        self.lbl_fecha.setProperty("cssClass", "fecha")
        self.lbl_fecha.setStyleSheet(
            "QLabel { color: #c9a227; font-weight: 700; font-size: 13px; "
            "padding: 4px 14px; background: #313244; border-radius: 8px; }"
        )
        tb.addWidget(self.lbl_fecha)
        self.lbl_ver_tb = QLabel(f"v{APP_VERSION}")
        self.lbl_ver_tb.setStyleSheet(
            "QLabel { color: #a6adc8; font-weight: 600; font-size: 12px; padding: 0 10px; }"
        )
        tb.addWidget(self.lbl_ver_tb)
        tb.addSeparator()

        tb.addWidget(QLabel("Tema:"))
        self.cmb_theme = QComboBox()
        self.cmb_theme.addItem("Oscuro", "oscuro")
        self.cmb_theme.addItem("Claro", "claro")
        self.cmb_theme.addItem("Taller", "taller")
        self.cmb_theme.currentIndexChanged.connect(
            lambda: self._set_theme(self.cmb_theme.currentData())
        )
        tb.addWidget(self.cmb_theme)

        # Buscar (paridad con web)
        tb.addSeparator()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Buscar trabajador…")
        self.txt_search.setMaximumWidth(200)
        self.txt_search.returnPressed.connect(self._quick_search)
        tb.addWidget(self.txt_search)

    def _quick_search(self):
        q = (self.txt_search.text() or "").strip()
        if not q:
            return
        # Ir a trabajadores (índice 6) — el widget filtra si expone método
        self.tabs.setCurrentIndex(6)
        w = self.tabs.widget(6)
        if hasattr(w, "filter_text"):
            w.filter_text(q)
        elif hasattr(w, "set_filter"):
            w.set_filter(q)

    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Orden alineado con la barra de la web
        self.tab_inicio = DashboardLiteWidget()
        self.tab_hoy = SoloHoyWidget()
        self.tab_prod = ProductionWidget()
        self.tab_pita = AreaNominaWidget("pita")
        self.tab_taller = AreaNominaWidget("taller")
        self.tab_folios = TrabajosWidget()
        self.tab_workers = WorkersWidget()
        self.tab_summary = SummaryWidget()

        self.tabs.addTab(self.tab_inicio, "Inicio")
        self.tabs.addTab(self.tab_hoy, "Solo hoy")
        self.tabs.addTab(self.tab_prod, "Plata")
        self.tabs.addTab(self.tab_pita, "Pita")
        self.tabs.addTab(self.tab_taller, "Taller")
        self.tabs.addTab(self.tab_folios, "Folios")
        self.tabs.addTab(self.tab_workers, "Trabajadores")
        self.tabs.addTab(self.tab_summary, "Resumen")

    def _build_statusbar(self):
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.lbl_fecha_status = QLabel()
        self.lbl_version = QLabel(f"  v{APP_VERSION}  ")
        self.lbl_version.setStyleSheet("color: #c9a227; font-weight: 700; padding: 0 8px;")
        self.lbl_version.setToolTip(f"{APP_NAME} versión {APP_VERSION}")
        self.lbl_lan = QLabel("  Red: —  ")
        self.lbl_lan.setStyleSheet("color: #89b4fa; font-weight: 600; padding: 0 8px;")
        self.lbl_db = QLabel("BD: —")
        self.status.addPermanentWidget(self.lbl_fecha_status)
        self.status.addPermanentWidget(self.lbl_version)
        self.status.addPermanentWidget(self.lbl_lan)
        self.status.addPermanentWidget(self.lbl_db)
        self._update_lan_label()
        self.status.showMessage("Listo")
        self._update_fecha_label()

    def _update_lan_label(self) -> None:
        try:
            import sys
            from pathlib import Path as _P
            root = _P(__file__).resolve().parents[2]
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from app.core.network import lan_urls
            port = 8000
            try:
                import configparser
                from config import PROJECT_ROOT
                cp = configparser.ConfigParser()
                cp.read(PROJECT_ROOT / "config.ini", encoding="utf-8")
                if cp.has_section("server"):
                    port = int(cp["server"].get("port", "8000"))
            except Exception:
                pass
            urls = lan_urls(port)
            if urls:
                self.lbl_lan.setText(f"  Web: {urls[0]}  ")
            else:
                self.lbl_lan.setText("  Web: —  ")
        except Exception:
            self.lbl_lan.setText("  Web: —  ")

    def _update_fecha_label(self) -> None:
        try:
            larga = format_fecha_larga(today())
            corta = format_fecha_corta(today())
        except Exception:
            larga = corta = str(today())
        self.lbl_fecha.setText(f"  {larga}  ·  {corta}  ")
        self.lbl_fecha_status.setText(f"  {corta}  ")

    def _try_connect(self) -> None:
        try:
            self._db.connect()
            self.lbl_db.setText("BD: OK")
            self.lbl_db.setStyleSheet("color: #a6e3a1; font-weight: 600;")
            self._refresh_all()
        except Exception as e:
            self.lbl_db.setText("BD: error")
            self.lbl_db.setStyleSheet("color: #fab387; font-weight: 600;")
            self.status.showMessage(f"Sin BD: {e}", 8000)

    def _refresh_all(self) -> None:
        self._update_fecha_label()
        self._update_lan_label()
        for w in (
            self.tab_inicio,
            self.tab_hoy,
            self.tab_prod,
            self.tab_pita,
            self.tab_taller,
            self.tab_folios,
            self.tab_workers,
            self.tab_summary,
        ):
            try:
                if hasattr(w, "reload"):
                    w.reload()
                elif hasattr(w, "refresh"):
                    w.refresh()
                elif hasattr(w, "refresh_table"):
                    w.refresh_table()
            except Exception:
                pass
        self.status.showMessage("Datos actualizados", 2500)


    def _open_web(self) -> None:
        """Abre la UI web (funciones completas: Semanas, rarezas, etc.)."""
        port = 8000
        try:
            import configparser
            from config import PROJECT_ROOT, CONFIG_INI
            cp = configparser.ConfigParser()
            if CONFIG_INI.exists():
                cp.read(CONFIG_INI, encoding="utf-8")
                if cp.has_section("server"):
                    port = int(cp["server"].get("port", port))
        except Exception:
            pass
        url = f"http://127.0.0.1:{port}"
        try:
            webbrowser.open(url)
            self.status.showMessage(f"Abriendo {url} — el servidor debe estar iniciado en el launcher", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Web", str(e))

    def _show_parity(self) -> None:
        QMessageBox.information(
            self,
            "App de escritorio vs web",
            "Esta app (PySide6) es práctica para captura local y catálogos.\n\n"
            "En ESCRITORIO puedes:\n"
            "• Solo hoy, Plata (gramos), Pita/Taller básicos\n"
            "• Trabajadores, Folios, cerrar/reabrir semana, exports\n\n"
            "Solo en la WEB (launcher → Iniciar → Abrir web):\n"
            "• Gestión de Semanas (alinear, eliminar, editar fechas)\n"
            "• Rarezas / deshacer gramo / captura guiada\n"
            "• Captura manual formal, checklist export, insights completos\n"
            "• Acceso desde otros equipos de la red\n\n"
            "HTTPS y vista móvil reducida: pendientes (no implementados aún).\n"
            "Usa Ayuda → Abrir interfaz web cuando necesites lo completo.",
        )

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "Acerca de",
            f"<b>{APP_NAME}</b><br>Versión {APP_VERSION}<br><br>"
            "Escritorio alineado con la interfaz web.<br>"
            "Launcher → servidor web para la experiencia completa en red.",
        )
