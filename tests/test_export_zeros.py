"""Regla fija: en 0 no se exporta (filtros de rutas / helpers)."""
from app.services.export_service import linea_tiene_gramos


def test_linea_sin_gramos_false():
    assert linea_tiene_gramos({"total_gramos": 0, "gm_sab": 0}) is False
    assert linea_tiene_gramos({"total_gramos": None}) is False


def test_linea_con_gramos_true():
    assert linea_tiene_gramos({"total_gramos": 10}) is True
    assert linea_tiene_gramos({"gm_lun": 5, "total_gramos": 0}) is True


def test_pita_efectivo_regla():
    """Misma regla que el export de Pita."""
    rows = [
        {"nombre": "A", "efectivo": 0},
        {"nombre": "B", "efectivo": 10.5},
        {"nombre": "C", "efectivo": None},
    ]
    exportables = [r for r in rows if float(r.get("efectivo") or 0) > 0]
    assert len(exportables) == 1
    assert exportables[0]["nombre"] == "B"


def test_taller_monto_regla():
    rows = [
        {"nombre": "A", "sueldo": 0, "extras": 0, "total": 0},
        {"nombre": "B", "sueldo": 100, "extras": 0, "total": 100},
        {"nombre": "C", "sueldo": 0, "extras": 50, "total": 50},
    ]
    exportables = [
        r for r in rows
        if float(r.get("total") or 0) > 0
        or float(r.get("sueldo") or 0) > 0
        or float(r.get("extras") or 0) > 0
    ]
    assert len(exportables) == 2
