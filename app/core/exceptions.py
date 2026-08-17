"""
Jerarquía de excepciones de la aplicación.

Diseñada para:
- Programadores: traceback + código de error + contexto
- IA / soporte: mensaje claro, código estable, detalles estructurados
- Usuario final: mensaje amigable sin jerga técnica
"""
from __future__ import annotations

from typing import Any, Optional


class AppError(Exception):
    """Error base de la aplicación Fajos Central."""

    code: str = "APP_ERROR"
    http_status: int = 500
    user_message: str = "Ocurrió un error inesperado."

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ):
        self.message = message or self.user_message
        self.details = details or {}
        self.cause = cause
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Reporte estructurado entendible por humanos e IA."""
        payload: dict[str, Any] = {
            "error": True,
            "code": self.code,
            "message": self.message,
            "user_message": self.user_message,
            "http_status": self.http_status,
        }
        if self.details:
            payload["details"] = self.details
        if self.cause is not None:
            payload["cause"] = {
                "type": type(self.cause).__name__,
                "message": str(self.cause),
            }
        return payload

    def __str__(self) -> str:
        base = f"[{self.code}] {self.message}"
        if self.details:
            base += f" | details={self.details}"
        if self.cause:
            base += f" | cause={type(self.cause).__name__}: {self.cause}"
        return base


class NotFoundError(AppError):
    code = "NOT_FOUND"
    http_status = 404
    user_message = "No se encontró el recurso solicitado."


class ValidationAppError(AppError):
    code = "VALIDATION_ERROR"
    http_status = 422
    user_message = "Los datos enviados no son válidos."


class DatabaseError(AppError):
    code = "DATABASE_ERROR"
    http_status = 503
    user_message = "No se pudo completar la operación en la base de datos."


class ExportError(AppError):
    code = "EXPORT_ERROR"
    http_status = 500
    user_message = "No se pudo generar el archivo de exportación."


class ConflictError(AppError):
    code = "CONFLICT"
    http_status = 409
    user_message = "La operación entra en conflicto con datos existentes."
