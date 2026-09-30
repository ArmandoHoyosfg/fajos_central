"""
Cronómetro gráfico (PySide6) para medir el tiempo real de bloques de trabajo IA.

Uso:
    python scripts/task_timer_gui.py

Flujo de uso (hacer equipo):
  1. Cuando vas a mandarme el mensaje del bloque → presiona INICIAR
  2. Yo trabajo...
  3. Cuando termino de escribir → presiona REGISTRO IA (marca cuándo terminé)
  4. Presiona DETENER para cerrar la sesión
  5. El historial queda en logs/task_timer_YYYYmmdd.jsonl (mismo formato que la CLI)
  6. Si te equivocaste o quieres empezar de nuevo → presiona RESET (vuelve a 0, sin guardar)

También puedes arrancar con un nombre de tarea pre-cargado:
    python scripts/task_timer_gui.py --task "Bloque 3: migrar cierre_dia"
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# Forzar UTF-8 en consolas Windows antes de cualquier print
if sys.platform == "win32":
    import os
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import (
        QApplication,
        QWidget,
        QVBoxLayout,
        QHBoxLayout,
        QPushButton,
        QLabel,
        QLineEdit,
        QTableWidget,
        QTableWidgetItem,
        QHeaderView,
        QMessageBox,
    )
except ImportError:
    print("ERROR: PySide6 no está instalado.")
    print("Instálalo con:  pip install PySide6")
    sys.exit(1)


# ─── colores (tema claro, texto oscuro) ───────────────────────────────────────
C_BG        = "#fafafa"
C_BG_CARD   = "#ffffff"
C_BORDER    = "#d0d0d0"
C_TEXT      = "#212121"
C_TEXT_DIM  = "#616161"
C_GREEN     = "#2e7d32"
C_GREEN_BG  = "#e8f5e9"
C_BLUE      = "#1565c0"
C_BLUE_BG   = "#e3f2fd"
C_RED       = "#c62828"
C_RED_BG    = "#ffebee"
C_ORANGE    = "#e65100"
C_ORANGE_BG = "#fff3e0"
C_GRAY      = "#9e9e9e"
C_GRAY_BG   = "#f5f5f5"


def _btn_style(bg: str, fg: str = "white", size: str = "16px") -> str:
    return (
        f"font-size: {size}; font-weight: bold; padding: 10px 20px;"
        f"background-color: {bg}; color: {fg}; border: none; border-radius: 8px;"
    )


# ─── utilidades ────────────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now().astimezone()


def _fmt_duration(seconds: float) -> str:
    if seconds < 0:
        seconds = 0.0
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m {s:02d}s"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s:.1f} s"


def _load_history(log_dir: Path) -> list[dict]:
    if not log_dir.exists():
        return []
    stamp = datetime.now().strftime("%Y%m%d")
    path = log_dir / f"task_timer_{stamp}.jsonl"
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return records


def _append_record(log_dir: Path, record: dict) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    path = log_dir / f"task_timer_{stamp}.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


# ─── widget principal ──────────────────────────────────────────────────────────

class TaskTimerGUI(QWidget):
    def __init__(self, log_dir: Path, initial_task: str = ""):
        super().__init__()
        self.log_dir = log_dir
        self._running = False
        self._start_time: datetime | None = None
        self._ia_time: datetime | None = None
        self._stop_time: datetime | None = None
        self._task_name: str = initial_task
        self._session_count: int = 0

        self._init_ui()
        self._refresh_history()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.setInterval(200)

    # ── UI ──────────────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        self.setWindowTitle("⏱  Cronómetro — Fajos Central")
        self.setMinimumSize(580, 540)
        self.setStyleSheet(self._stylesheet())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # --- título ---
        title = QLabel("Cronómetro de bloques de trabajo")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {C_TEXT};")
        layout.addWidget(title)

        # --- campo de tarea ---
        row_task = QHBoxLayout()
        lbl_task = QLabel("Tarea:")
        lbl_task.setStyleSheet(f"color: {C_TEXT}; font-size: 13px;")
        self.ed_task = QLineEdit(self._task_name)
        self.ed_task.setPlaceholderText("Ej: Bloque 3 — migrar cierre_dia")
        self.ed_task.setStyleSheet(
            f"background: {C_BG_CARD}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
            "border-radius: 4px; padding: 6px 10px; font-size: 13px;"
        )
        row_task.addWidget(lbl_task)
        row_task.addWidget(self.ed_task, stretch=1)
        layout.addLayout(row_task)

        # --- display del tiempo ---
        self.lbl_display = QLabel("0.0 s")
        self.lbl_display.setAlignment(Qt.AlignCenter)
        self.lbl_display.setMinimumHeight(80)
        self._set_display_color(C_GREEN, C_GREEN_BG)
        layout.addWidget(self.lbl_display)

        # --- etiquetas de estado ---
        self.lbl_status = QLabel("Detenido")
        self.lbl_status.setAlignment(Qt.AlignCenter)
        self.lbl_status.setStyleSheet(f"color: {C_TEXT_DIM}; font-size: 13px;")
        layout.addWidget(self.lbl_status)

        # --- botones principales ---
        row_btns = QHBoxLayout()
        row_btns.setSpacing(10)

        self.btn_start = QPushButton("▶  INICIAR")
        self.btn_start.setMinimumHeight(52)
        self.btn_start.setStyleSheet(_btn_style(C_GREEN))
        self.btn_start.clicked.connect(self._on_start)

        self.btn_ia = QPushButton("🤖  REGISTRO IA")
        self.btn_ia.setMinimumHeight(52)
        self.btn_ia.setEnabled(False)
        self.btn_ia.setStyleSheet(_btn_style(C_GRAY, size="14px"))
        self.btn_ia.clicked.connect(self._on_ia)

        self.btn_stop = QPushButton("⏹  DETENER")
        self.btn_stop.setMinimumHeight(52)
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(_btn_style(C_GRAY, size="16px"))
        self.btn_stop.clicked.connect(self._on_stop)

        self.btn_reset = QPushButton("↺  RESET")
        self.btn_reset.setMinimumHeight(52)
        self.btn_reset.setStyleSheet(_btn_style(C_ORANGE, size="14px"))
        self.btn_reset.setToolTip("Vuelve el cronómetro a 0 (sin guardar). Útil si te equivocaste.")
        self.btn_reset.clicked.connect(self._on_reset)

        row_btns.addWidget(self.btn_start)
        row_btns.addWidget(self.btn_ia)
        row_btns.addWidget(self.btn_stop)
        row_btns.addWidget(self.btn_reset)
        layout.addLayout(row_btns)

        # --- separador ---
        sep = QLabel("─" * 64)
        sep.setStyleSheet(f"color: {C_BORDER}; font-size: 10px;")
        layout.addWidget(sep)

        # --- historial ---
        lbl_hist = QLabel("Historial de hoy")
        lbl_hist.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {C_TEXT};")
        layout.addWidget(lbl_hist)

        self.tbl_history = QTableWidget(0, 5)
        self.tbl_history.setHorizontalHeaderLabels([
            "Tarea", "Inicio", "Fin IA", "Fin", "Duración",
        ])
        self.tbl_history.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 5):
            self.tbl_history.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.tbl_history.setAlternatingRowColors(True)
        self.tbl_history.setEditTriggers(QTableWidget.NoEditTriggers)
        self.tbl_history.setSelectionBehavior(QTableWidget.SelectRows)
        self.tbl_history.setMaximumHeight(180)
        layout.addWidget(self.tbl_history)

        # --- botón exportar ---
        row_export = QHBoxLayout()
        self.btn_export = QPushButton("📋  Copiar historial al portapapeles")
        self.btn_export.setStyleSheet(
            f"font-size: 12px; padding: 6px 12px; border-radius: 4px;"
            f"background: {C_BG_CARD}; color: {C_TEXT}; border: 1px solid {C_BORDER};"
        )
        self.btn_export.clicked.connect(self._on_export)
        row_export.addStretch()
        row_export.addWidget(self.btn_export)
        layout.addLayout(row_export)

    def _stylesheet(self) -> str:
        return f"""
            QWidget {{
                background-color: {C_BG};
                color: {C_TEXT};
                font-family: "Segoe UI", sans-serif;
            }}
            QTableWidget {{
                background-color: {C_BG_CARD};
                color: {C_TEXT};
                border: 1px solid {C_BORDER};
                border-radius: 4px;
                font-size: 12px;
                gridline-color: {C_BORDER};
            }}
            QTableWidget::item {{
                padding: 4px;
                color: {C_TEXT};
            }}
            QTableWidget::item:selected {{
                background-color: {C_BLUE_BG};
                color: {C_TEXT};
            }}
            QHeaderView::section {{
                background-color: {C_GRAY_BG};
                color: {C_TEXT};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {C_BORDER};
                font-weight: bold;
            }}
            QLineEdit {{
                selection-background-color: {C_BLUE};
                selection-color: white;
            }}
        """

    # ── helpers de display ──────────────────────────────────────────────────

    def _set_display_color(self, fg: str, bg: str) -> None:
        self.lbl_display.setStyleSheet(
            f"font-size: 36px; font-weight: bold; color: {fg};"
            f"background-color: {bg}; border-radius: 8px;"
        )

    # ── lógica ──────────────────────────────────────────────────────────────

    def _elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return max(0.0, (_now() - self._start_time).total_seconds())

    def _tick(self) -> None:
        if not self._running:
            return
        dur = self._elapsed()
        self.lbl_display.setText(_fmt_duration(dur))
        if dur > 3600:
            self._set_display_color(C_RED, C_RED_BG)
        elif dur > 1800:
            self._set_display_color(C_ORANGE, C_ORANGE_BG)
        else:
            self._set_display_color(C_GREEN, C_GREEN_BG)

    def _on_start(self) -> None:
        self._task_name = self.ed_task.text().strip() or "Tarea sin nombre"
        self._start_time = _now()
        self._ia_time = None
        self._stop_time = None
        self._running = True
        self._session_count += 1

        self.btn_start.setEnabled(False)
        self.btn_start.setStyleSheet(_btn_style(C_GRAY))
        self.btn_ia.setEnabled(True)
        self.btn_ia.setStyleSheet(_btn_style(C_BLUE))
        self.btn_stop.setEnabled(True)
        self.btn_stop.setStyleSheet(_btn_style(C_RED))
        self.btn_reset.setEnabled(True)
        self.btn_reset.setStyleSheet(_btn_style(C_ORANGE, size="14px"))

        self.lbl_status.setText(f"Corriendo — {self._task_name}")
        self.lbl_status.setStyleSheet(f"color: {C_GREEN}; font-size: 13px; font-weight: bold;")
        self.lbl_display.setText("0.0 s")
        self._set_display_color(C_GREEN, C_GREEN_BG)
        self._timer.start()

    def _on_ia(self) -> None:
        if self._ia_time is not None:
            return
        self._ia_time = _now()
        dur_ia = (self._ia_time - self._start_time).total_seconds()
        self.lbl_status.setText(
            f"🤖 IA terminó a los {_fmt_duration(dur_ia)} — presiona DETENER para cerrar"
        )
        self.lbl_status.setStyleSheet(f"color: {C_BLUE}; font-size: 13px; font-weight: bold;")
        self.btn_ia.setEnabled(False)
        self.btn_ia.setStyleSheet(_btn_style(C_GRAY, size="14px"))

    def _on_stop(self) -> None:
        if not self._running:
            return
        self._timer.stop()
        self._running = False
        self._stop_time = _now()
        total = (self._stop_time - self._start_time).total_seconds()

        ia_elapsed = None
        if self._ia_time:
            ia_elapsed = (self._ia_time - self._start_time).total_seconds()

        record = {
            "task": self._task_name,
            "start": self._start_time.isoformat(),
            "end": self._stop_time.isoformat(),
            "ia_end": self._ia_time.isoformat() if self._ia_time else None,
            "ia_duration_seconds": round(ia_elapsed, 2) if ia_elapsed is not None else None,
            "duration_seconds": round(total, 2),
            "ts": _now().isoformat(),
        }
        _append_record(self.log_dir, record)

        self.lbl_display.setText(_fmt_duration(total))
        self._set_display_color(C_TEXT_DIM, C_GRAY_BG)
        self.lbl_status.setText("Sesión guardada ✅")
        self.lbl_status.setStyleSheet(f"color: {C_GREEN}; font-size: 13px;")

        self.btn_start.setEnabled(True)
        self.btn_start.setStyleSheet(_btn_style(C_GREEN))
        self.btn_ia.setEnabled(False)
        self.btn_ia.setStyleSheet(_btn_style(C_GRAY, size="14px"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(_btn_style(C_GRAY))
        self.btn_reset.setEnabled(True)
        self.btn_reset.setStyleSheet(_btn_style(C_ORANGE, size="14px"))

        self._refresh_history()

    def _on_reset(self) -> None:
        """Vuelve el cronómetro a 0. Si estaba corriendo, detiene sin guardar."""
        if self._running:
            reply = QMessageBox.question(
                self,
                "Reset",
                "El cronómetro está corriendo.\n¿Detener sin guardar y volver a 0?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self._timer.stop()
            self._running = False

        self._start_time = None
        self._ia_time = None
        self._stop_time = None
        self.lbl_display.setText("0.0 s")
        self._set_display_color(C_GREEN, C_GREEN_BG)
        self.lbl_status.setText("Reset — listo para iniciar")
        self.lbl_status.setStyleSheet(f"color: {C_ORANGE}; font-size: 13px; font-weight: bold;")

        self.btn_start.setEnabled(True)
        self.btn_start.setStyleSheet(_btn_style(C_GREEN))
        self.btn_ia.setEnabled(False)
        self.btn_ia.setStyleSheet(_btn_style(C_GRAY, size="14px"))
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet(_btn_style(C_GRAY))
        self.btn_reset.setEnabled(True)
        self.btn_reset.setStyleSheet(_btn_style(C_ORANGE, size="14px"))

    # ── historial ───────────────────────────────────────────────────────────

    def _refresh_history(self) -> None:
        records = _load_history(self.log_dir)
        records = records[-20:][::-1]
        self.tbl_history.setRowCount(len(records))
        for row, rec in enumerate(records):
            task = rec.get("task", "?")
            start = rec.get("start", "?")
            end = rec.get("end", "?")
            dur = rec.get("duration_seconds", 0)
            ia_end = rec.get("ia_end", "")
            ia_fmt = ia_end.split("T")[-1][:8] if ia_end else "—"

            fmt_start = start.split("T")[-1][:8] if "T" in start else start
            fmt_end = end.split("T")[-1][:8] if "T" in end else end

            items = [
                QTableWidgetItem(task),
                QTableWidgetItem(fmt_start),
                QTableWidgetItem(ia_fmt),
                QTableWidgetItem(fmt_end),
                QTableWidgetItem(_fmt_duration(dur)),
            ]
            for col, item in enumerate(items):
                self.tbl_history.setItem(row, col, item)

    def _on_export(self) -> None:
        records = _load_history(self.log_dir)
        if not records:
            QMessageBox.information(self, "Historial", "No hay registros para hoy.")
            return
        lines = [f"Cronómetro Fajos Central — {datetime.now().strftime('%Y-%m-%d')}"]
        lines.append("=" * 60)
        for rec in records:
            task = rec.get("task", "?")
            dur = rec.get("duration_seconds", 0)
            ia_dur = rec.get("ia_duration_seconds")
            ia_str = f"  (IA: {_fmt_duration(ia_dur)})" if ia_dur is not None else ""
            lines.append(f"  {task:<40}  {_fmt_duration(dur):>10}{ia_str}")
        lines.append("=" * 60)
        total = sum(r.get("duration_seconds", 0) for r in records)
        lines.append(f"  Total del día: {_fmt_duration(total)}")
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Portapapeles", "Historial copiado al portapapeles ✅")

    def closeEvent(self, event) -> None:
        if self._running:
            reply = QMessageBox.question(
                self,
                "Salir",
                "El cronómetro está corriendo.\n¿Detener la sesión y salir?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self._on_stop()
        event.accept()


# ─── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    import argparse

    p = argparse.ArgumentParser(description="Cronómetro gráfico para bloques de trabajo.")
    p.add_argument("--task", default="", help="Nombre inicial de la tarea.")
    p.add_argument("--log-dir", default=None, help="Directorio de logs (default: logs/).")
    args = p.parse_args()

    if args.log_dir:
        log_dir = Path(args.log_dir).resolve()
    else:
        here = Path(__file__).resolve().parent
        for candidate in [here.parent / "logs", Path.cwd() / "logs"]:
            if candidate.parent.name == "fajos_central" or (candidate.parent / "app").exists():
                log_dir = candidate
                break
        else:
            log_dir = Path.cwd() / "logs"

    app = QApplication(sys.argv)
    app.setApplicationName("TaskTimer — Fajos Central")
    window = TaskTimerGUI(log_dir=log_dir, initial_task=args.task)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())