"""Tests de la jerarquía de errores (entendibles por humanos e IA)."""
from app.core.exceptions import (
    AppError,
    DatabaseError,
    NotFoundError,
    ValidationAppError,
    ExportError,
)


def test_app_error_to_dict_structure():
    err = AppError("fallo de prueba", details={"campo": "x"})
    d = err.to_dict()
    assert d["error"] is True
    assert d["code"] == "APP_ERROR"
    assert d["message"] == "fallo de prueba"
    assert "user_message" in d
    assert d["details"]["campo"] == "x"
    assert d["http_status"] == 500


def test_not_found_status():
    err = NotFoundError("no existe", details={"id": 99})
    assert err.http_status == 404
    assert err.code == "NOT_FOUND"
    assert err.to_dict()["details"]["id"] == 99


def test_validation_status():
    err = ValidationAppError("nombre vacío", details={"field": "nombre"})
    assert err.http_status == 422
    assert "field" in err.to_dict()["details"]


def test_database_error_with_cause():
    cause = RuntimeError("connection refused")
    err = DatabaseError("no conecta", cause=cause)
    d = err.to_dict()
    assert d["code"] == "DATABASE_ERROR"
    assert d["cause"]["type"] == "RuntimeError"
    assert "connection refused" in d["cause"]["message"]


def test_export_error():
    err = ExportError("pdf falló", details={"format": "pdf"})
    assert err.code == "EXPORT_ERROR"
    assert str(err).startswith("[EXPORT_ERROR]")


def test_str_includes_code_and_details():
    err = ValidationAppError("dato malo", details={"field": "ubic"})
    s = str(err)
    assert "VALIDATION_ERROR" in s
    assert "dato malo" in s
