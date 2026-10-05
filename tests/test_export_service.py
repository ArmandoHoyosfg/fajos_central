"""Tests del servicio de exportación multi-formato."""
from decimal import Decimal

import pytest

from app.core.exceptions import ValidationAppError
from app.services.export_service import ExportService


SAMPLE = [
    {
        "nombre": "William",
        "ubic": 776,
        "folio": "F-001",
        "modelo": "SECUENCIA",
        "material": "AG3",
        "tarifa_gr": Decimal("12.00"),
        "gm_sab": Decimal("10"),
        "gm_dom": None,
        "gm_lun": Decimal("5"),
        "gm_mar": None,
        "gm_mie": None,
        "gm_jue": None,
        "gm_vie": None,
        "total_gramos": Decimal("15"),
        "efectivo": Decimal("180.00"),
    }
]


@pytest.fixture
def svc():
    return ExportService()


def test_export_xlsx(svc):
    content, media, name = svc.export_produccion(SAMPLE, "xlsx", codigo_semana="01-08")
    assert content[:2] == b"PK"  # zip/xlsx magic
    assert "spreadsheet" in media
    assert name.endswith(".xlsx")


def test_export_csv(svc):
    content, media, name = svc.export_produccion(SAMPLE, "csv")
    text = content.decode("utf-8-sig")
    assert "William" in text
    assert "Nombre" in text
    assert name.endswith(".csv")


def test_export_json(svc):
    content, media, name = svc.export_produccion(SAMPLE, "json", codigo_semana="01-08")
    import json
    data = json.loads(content.decode("utf-8"))
    assert data["semana"] == "01-08"
    assert data["total_lineas"] == 1
    assert data["lineas"][0]["nombre"] == "William"
    assert name.endswith(".json")


def test_export_pdf(svc):
    content, media, name = svc.export_produccion(SAMPLE, "pdf", codigo_semana="01-08")
    assert content[:4] == b"%PDF"
    assert media == "application/pdf"
    assert name.endswith(".pdf")


def test_formato_invalido(svc):
    with pytest.raises(ValidationAppError) as excinfo:
        svc.export_produccion(SAMPLE, "docx")  # type: ignore
    err = excinfo.value
    assert err.code == "VALIDATION_ERROR"
    assert "docx" in err.message or "docx" in str(err.details)
