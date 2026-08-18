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


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept.split(",")[0]


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("AppError %s: %s", exc.code, exc.message)
    if _wants_html(request):
        from fastapi.responses import HTMLResponse
        html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>Error</title>
        <style>body{{font-family:Segoe UI,sans-serif;background:#1e1e2e;color:#cdd6f4;padding:2rem}}
        a{{color:#89b4fa}}</style></head><body>
        <h1>{exc.user_message}</h1>
        <p><code>{exc.code}</code> — {exc.message}</p>
        <p><a href="/">Volver al inicio</a></p>
        <p style="color:#a6adc8;font-size:0.9rem">Si es un error de base de datos, configura la conexión en el launcher (config.ini) y reinicia el servidor.</p>
        </body></html>"""
        return HTMLResponse(status_code=exc.http_status, content=html)
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
    if _wants_html(request):
        from fastapi.responses import HTMLResponse
        html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>Error</title>
        <style>body{{font-family:Segoe UI,sans-serif;background:#1e1e2e;color:#cdd6f4;padding:2rem}}
        a{{color:#89b4fa}}; code{{color:#f9e2af}}</style></head><body>
        <h1>Error interno</h1>
        <p>{payload['user_message']}</p>
        <p><code>{type(exc).__name__}: {exc}</code></p>
        <p><a href="/">Volver al inicio</a></p>
        <p style="color:#a6adc8">Revisa logs/ y la conexión a MariaDB en el launcher.</p>
        </body></html>"""
        return HTMLResponse(status_code=500, content=html)
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
