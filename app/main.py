"""
Aplicación FastAPI — Fajos Central Nóminas v2
Acceso web en la red local + API REST.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app import __version__
from app.api.routes import router
from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Fajos Central — Nóminas",
    version=__version__,
    description="Sistema de nóminas del Taller de Fajos Central. API + interfaz web.",
)

static_dir = Path(__file__).parent / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

app.include_router(router)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("AppError %s: %s", exc.code, exc.message)
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    payload = {
        "error": True,
        "code": "INTERNAL_ERROR",
        "message": str(exc),
        "user_message": "Ocurrió un error interno. Revisa los logs o contacta soporte.",
        "http_status": 500,
        "details": {
            "path": str(request.url.path),
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
    }
    return JSONResponse(status_code=500, content=payload)


@app.on_event("startup")
async def on_startup():
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Fajos Central v%s iniciado (debug=%s)", __version__, settings.debug)


def run():
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    run()
