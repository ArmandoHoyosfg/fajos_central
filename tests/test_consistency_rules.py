"""Reglas del motor de consistencia (sin BD)."""
def test_desfase_threshold():
    vivos = 100.0
    guardado = 100.04
    assert abs(vivos - guardado) <= 0.05
    guardado2 = 99.9
    assert abs(vivos - guardado2) > 0.05
