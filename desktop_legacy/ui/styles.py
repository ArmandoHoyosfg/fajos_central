"""
Estilos escritorio alineados con la web (temas Oscuro / Claro / Taller).
"""
from __future__ import annotations

# Tokens aproximados a app/web/static/app.css
THEMES = {
    "oscuro": {
        "bg": "#1e1e2e",
        "bg_elev": "#181825",
        "surface": "#313244",
        "border": "#45475a",
        "text": "#cdd6f4",
        "muted": "#a6adc8",
        "accent": "#c9a227",
        "accent_text": "#1e1e2e",
        "blue": "#89b4fa",
        "green": "#a6e3a1",
        "peach": "#fab387",
        "input_bg": "#11111b",
    },
    "claro": {
        "bg": "#f5f6fa",
        "bg_elev": "#ffffff",
        "surface": "#e8ecf5",
        "border": "#c5c9d6",
        "text": "#1e1e2e",
        "muted": "#5c6370",
        "accent": "#b8860b",
        "accent_text": "#ffffff",
        "blue": "#1e66f5",
        "green": "#40a02b",
        "peach": "#d20f39",
        "input_bg": "#ffffff",
    },
    "taller": {
        "bg": "#1a1612",
        "bg_elev": "#241f1a",
        "surface": "#3d3429",
        "border": "#5c4f3d",
        "text": "#f0e6d3",
        "muted": "#b8a890",
        "accent": "#d4a017",
        "accent_text": "#1a1612",
        "blue": "#89b4fa",
        "green": "#a6e3a1",
        "peach": "#fab387",
        "input_bg": "#120f0c",
    },
}


def build_qss(theme: str = "oscuro") -> str:
    t = THEMES.get(theme, THEMES["oscuro"])
    return f"""
QMainWindow, QWidget {{
    background-color: {t['bg']};
    color: {t['text']};
    font-family: "Segoe UI", "Ubuntu", sans-serif;
    font-size: 13px;
}}
QMenuBar {{
    background-color: {t['bg_elev']};
    color: {t['text']};
    border-bottom: 1px solid {t['border']};
}}
QMenuBar::item:selected {{ background-color: {t['surface']}; }}
QMenu {{
    background-color: {t['bg_elev']};
    color: {t['text']};
    border: 1px solid {t['border']};
}}
QMenu::item:selected {{ background-color: {t['surface']}; }}
QToolBar {{
    background-color: {t['bg_elev']};
    border-bottom: 1px solid {t['border']};
    spacing: 6px;
    padding: 4px;
}}
QStatusBar {{
    background-color: {t['bg_elev']};
    color: {t['muted']};
}}
QTabWidget::pane {{
    border: 1px solid {t['border']};
    background: {t['bg']};
}}
QTabBar::tab {{
    background: {t['bg_elev']};
    color: {t['muted']};
    padding: 8px 14px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}}
QTabBar::tab:selected {{
    background: {t['surface']};
    color: {t['text']};
    font-weight: bold;
    border-bottom: 2px solid {t['accent']};
}}
QTabBar::tab:hover {{ background: {t['surface']}; }}
QPushButton {{
    background-color: {t['accent']};
    color: {t['accent_text']};
    font-weight: 600;
    border: none;
    border-radius: 6px;
    padding: 7px 16px;
}}
QPushButton:hover {{ background-color: {t['accent']}; opacity: 0.9; }}
QPushButton:disabled {{ background-color: {t['border']}; color: {t['muted']}; }}
QPushButton[cssClass="secondary"] {{
    background-color: {t['surface']};
    color: {t['text']};
    border: 1px solid {t['border']};
}}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QPlainTextEdit, QTextEdit {{
    background-color: {t['input_bg']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {t['accent']};
}}
QTableWidget, QTableView {{
    background-color: {t['bg']};
    alternate-background-color: {t['bg_elev']};
    gridline-color: {t['border']};
    color: {t['text']};
    border: 1px solid {t['border']};
    border-radius: 8px;
}}
QHeaderView::section {{
    background-color: {t['surface']};
    color: {t['muted']};
    padding: 6px 8px;
    border: none;
    border-right: 1px solid {t['border']};
    border-bottom: 1px solid {t['border']};
    font-weight: 600;
}}
QScrollBar:vertical {{
    background: {t['bg_elev']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {t['border']};
    border-radius: 4px;
    min-height: 24px;
}}
QLabel[cssClass="fecha"] {{
    color: {t['accent']};
    font-weight: 700;
}}
QLabel[cssClass="muted"] {{
    color: {t['muted']};
}}
QFrame[cssClass="card"] {{
    background-color: {t['bg_elev']};
    border: 1px solid {t['border']};
    border-radius: 10px;
}}
QToolTip {{
    background-color: {t['bg_elev']};
    color: {t['text']};
    border: 1px solid {t['border']};
}}
"""


DARK_QSS = build_qss("oscuro")  # compat
