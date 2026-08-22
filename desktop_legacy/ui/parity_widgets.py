"""
Pestañas de paridad con la web: Solo hoy, Pita, Taller, Inicio (resumen vivo).
Usan la misma BD; la captura completa de Plata sigue en ProductionWidget.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
    QAbstractItemView,
)


def _try_app_repos():
    """Intenta repositorios compartidos de app/; si falla, None."""
    try:
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from app.db.repository import (
            ProduccionRepo,
            ProduccionPitaRepo,
            NominaTallerRepo,
            SemanasRepo,
        )
        from app.services.insights_service import InsightsService
        from app.core.dias import col_hoy, DAY_LABELS
        return {
            "prod": ProduccionRepo,
            "pita": ProduccionPitaRepo,
            "taller": NominaTallerRepo,
            "semanas": SemanasRepo,
            "insights": InsightsService,
            "col_hoy": col_hoy,
            "DAY_LABELS": DAY_LABELS,
        }
    except Exception as e:
        return {"error": str(e)}


class SoloHoyWidget(QWidget):
    """Equivalente web /solo-hoy: solo gramos del día."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mods = _try_app_repos()
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Solo hoy — captura rápida del día (como en la web)")
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        row = QHBoxLayout()
        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.clicked.connect(self.reload)
        row.addWidget(self.btn_refresh)
        row.addStretch()
        lay.addLayout(row)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Nombre", "Ubic", "Folio", "Modelo", "Mat", "Gramos hoy"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        lay.addWidget(self.table)
        self.lbl_status = QLabel("")
        self.lbl_status.setProperty("cssClass", "muted")
        lay.addWidget(self.lbl_status)
        self.reload()

    def reload(self):
        mods = self._mods
        if "error" in mods or "insights" not in mods:
            self.lbl_status.setText(
                "Usa la web (Solo hoy) si no carga aquí: " + str(mods.get("error", ""))
            )
            return
        try:
            data = mods["insights"]().captura_solo_hoy()
        except Exception as e:
            self.lbl_status.setText(f"Error: {e}")
            return
        self.lbl.setText(
            f"Solo hoy — {data.get('label')} · {data.get('fecha')} · "
            f"semana {((data.get('semana') or {}).get('codigo') or '—')}"
        )
        rows = data.get("lineas") or []
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            vals = [
                r.get("nombre"),
                r.get("ubic"),
                r.get("folio") or "—",
                r.get("modelo") or "—",
                r.get("material") or "—",
                r.get("gramos_hoy") if r.get("gramos_hoy") else "",
            ]
            for c, v in enumerate(vals):
                item = QTableWidgetItem("" if v is None else str(v))
                if c == 5:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                item.setData(Qt.UserRole, r.get("id"))
                self.table.setItem(i, c, item)
        self.lbl_status.setText(
            f"{data.get('capturados', 0)} con gramos · {data.get('pendientes', 0)} pendientes"
        )
        self.table.cellChanged.connect(self._on_cell)

    def _on_cell(self, row: int, col: int):
        if col != 5:
            return
        mods = self._mods
        if "prod" not in mods:
            return
        item = self.table.item(row, col)
        if not item:
            return
        prod_id = item.data(Qt.UserRole)
        if not prod_id:
            # id on nombre cell
            n = self.table.item(row, 0)
            prod_id = n.data(Qt.UserRole) if n else None
        if not prod_id:
            return
        try:
            g = float(item.text().replace(",", ".") or 0)
        except ValueError:
            return
        col_name = mods["col_hoy"]()
        try:
            mods["prod"]().actualizar_gramos_dia(int(prod_id), col_name, g if g else None)
        except Exception as e:
            QMessageBox.warning(self, "Guardar", str(e))


class AreaNominaWidget(QWidget):
    """Vista de solo lectura + recarga para Pita o Taller (paridad visual con web)."""

    def __init__(self, area: str, parent=None):
        super().__init__(parent)
        self.area = area  # "pita" | "taller"
        self._mods = _try_app_repos()
        lay = QVBoxLayout(self)
        title = "Nómina Pita" if area == "pita" else "Nómina Taller"
        self.lbl = QLabel(f"{title} — mismos datos que la web")
        lay.addWidget(self.lbl)
        top = QHBoxLayout()
        self.cmb = QComboBox()
        self.cmb.currentIndexChanged.connect(self.reload)
        top.addWidget(QLabel("Semana"))
        top.addWidget(self.cmb)
        btn = QPushButton("Actualizar")
        btn.clicked.connect(self.reload)
        top.addWidget(btn)
        top.addStretch()
        lay.addLayout(top)
        self.table = QTableWidget(0, 0)
        self.table.setAlternatingRowColors(True)
        lay.addWidget(self.table)
        self.lbl_tot = QLabel("")
        lay.addWidget(self.lbl_tot)
        self._load_semanas()
        self.reload()

    def _load_semanas(self):
        self.cmb.blockSignals(True)
        self.cmb.clear()
        mods = self._mods
        if "semanas" not in mods:
            self.cmb.blockSignals(False)
            return
        try:
            for s in mods["semanas"]().listar():
                self.cmb.addItem(str(s.get("codigo") or s["id"]), s["id"])
        except Exception:
            pass
        self.cmb.blockSignals(False)

    def reload(self):
        mods = self._mods
        if "error" in mods:
            self.lbl_tot.setText("Conecta la BD / usa la web: " + str(mods.get("error")))
            return
        sid = self.cmb.currentData()
        if not sid:
            return
        try:
            if self.area == "pita":
                rows = mods["pita"]().listar_por_semana(int(sid))
                headers = ["Nombre", "Ubic", "Modelo", "Folio", "Material", "Producto", "Pitas", "Efectivo", "Firma"]
                keys = ["nombre", "ubic", "modelo", "folio", "material", "producto", "pitas", "efectivo", "firmado"]
                tot = mods["pita"]().totales(int(sid))
                self.lbl_tot.setText(f"Total Pita: ${float(tot.get('total') or 0):.2f}")
            else:
                rows = mods["taller"]().listar_por_semana(int(sid))
                headers = ["Nombre", "Ubic", "Puesto", "Sueldo", "Extras", "Total", "Firma"]
                keys = ["nombre", "ubic", "puesto", "sueldo", "extras", "total", "firmado"]
                tot = mods["taller"]().totales(int(sid))
                self.lbl_tot.setText(f"Total Taller: ${float(tot.get('total') or 0):.2f}")
        except Exception as e:
            self.lbl_tot.setText(f"Error: {e}")
            return
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for c, k in enumerate(keys):
                v = r.get(k)
                if k == "firmado":
                    v = "Sí" if v else ""
                self.table.setItem(i, c, QTableWidgetItem("" if v is None else str(v)))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)


class DashboardLiteWidget(QWidget):
    """Inicio con avisos (paridad con panel web 'Qué revisar hoy')."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mods = _try_app_repos()
        lay = QVBoxLayout(self)
        self.lbl = QLabel("Inicio")
        self.lbl.setStyleSheet("font-size: 18px; font-weight: 700;")
        lay.addWidget(self.lbl)
        self.body = QLabel("Cargando…")
        self.body.setWordWrap(True)
        self.body.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        lay.addWidget(self.body, 1)
        btn = QPushButton("Actualizar avisos")
        btn.clicked.connect(self.reload)
        lay.addWidget(btn)
        self.reload()

    def reload(self):
        mods = self._mods
        if "insights" not in mods:
            self.body.setText(
                "No se pudo cargar insights.\n"
                "La web en el launcher tiene el dashboard completo.\n"
                + str(mods.get("error", ""))
            )
            return
        try:
            avisos = mods["insights"]().avisos_hoy()
            lines = [f"<b>Hoy:</b> {avisos.get('col_hoy_label')} · {avisos.get('fecha')}<br><br>"]
            for a in avisos.get("avisos") or []:
                lines.append(f"• <b>{a.get('titulo')}</b><br><span style='color:#a6adc8'>{a.get('detalle') or ''}</span><br>")
            pr = avisos.get("pronostico") or {}
            if pr.get("ok"):
                lines.append(
                    f"<br><b>Pronóstico Plata:</b> ${pr.get('estimado_efectivo', 0):.2f} "
                    f"({pr.get('estimado_gramos', 0):.1f} g)"
                )
            self.body.setText("".join(lines))
        except Exception as e:
            self.body.setText(f"Error: {e}")
