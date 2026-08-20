"""
Estilos modernos (Fusion + QSS).
"""

DARK_QSS = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item:selected { background-color: #313244; }
QMenu {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #313244;
}
QMenu::item:selected { background-color: #45475a; }
QToolBar {
    background-color: #181825;
    border-bottom: 1px solid #313244;
    spacing: 6px;
    padding: 4px;
}
QStatusBar {
    background-color: #181825;
    color: #a6adc8;
}
QTabWidget::pane {
    border: 1px solid #313244;
    background: #1e1e2e;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 8px 18px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected {
    background: #313244;
    color: #cdd6f4;
    font-weight: bold;
}
QTabBar::tab:hover { background: #45475a; }
QPushButton {
    background-color: #c9a227;
    color: #1e1e2e;
    font-weight: 600;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
}
QPushButton:hover { background-color: #a68520; color: #1e1e2e; }
QPushButton:pressed { background-color: #8a7018; color: #1e1e2e; }
QPushButton:disabled { background-color: #45475a; color: #6c7086; }
QPushButton[cssClass="danger"] {
    background-color: #f38ba8;
}
QPushButton[cssClass="danger"]:hover { background-color: #eba0ac; }
QPushButton[cssClass="success"] {
    background-color: #a6e3a1;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 5px;
    padding: 5px 8px;
    selection-background-color: #c9a227;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {
    border: 1px solid #c9a227;
}
QTableWidget, QTableView {
    background-color: #1e1e2e;
    alternate-background-color: #262637;
    gridline-color: #313244;
    color: #cdd6f4;
    border: 1px solid #313244;
    border-radius: 6px;
}
QHeaderView::section {
    background-color: #181825;
    color: #cdd6f4;
    padding: 6px;
    border: none;
    border-right: 1px solid #313244;
    border-bottom: 1px solid #313244;
    font-weight: 600;
}
QTableWidget::item:selected, QTableView::item:selected {
    background-color: #45475a;
    color: #cdd6f4;
}
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #c9a227;
}
QLabel[cssClass="title"] {
    font-size: 18px;
    font-weight: bold;
    color: #c9a227;
}
QLabel[cssClass="subtitle"] {
    color: #a6adc8;
    font-size: 12px;
}
QScrollBar:vertical {
    background: #1e1e2e;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMessageBox {
    background-color: #1e1e2e;
}
"""
