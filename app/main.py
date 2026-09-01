"""
Aplicación FastAPI — Fajos Piteados Central
Web en red local + API REST. HTTPS opcional con redirección.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router
from app.core.config import BASE_DIR, settings
from app.core.exceptions import AppError
from app.core.logging_config import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)
try:
    from app.core.event_log import push as _elog
    _elog("info", "Servidor iniciando…", source="boot")
except Exception:
    pass


# Se activa en run() si hay certificados SSL
_FORCE_HTTPS_RUNTIME = False

app = FastAPI(
    title="Fajos Piteados Central — Nóminas",
    version=__version__,
    description="Sistema de nóminas. API + interfaz web en red local.",
)

static_dir = Path(__file__).parent / "web" / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(router)


@app.on_event("startup")
async def _startup_migrations() -> None:
    """Aplica migraciones pendientes de db/schema/ al iniciar el servidor."""
    try:
        from app.db.migrate import run_migrations_on_startup
        result = run_migrations_on_startup()
        if result.get("applied"):
            logger.info("Migraciones nuevas: %s", result["applied"])
        if result.get("errors"):
            logger.warning("Migraciones con error: %s", result["errors"])
    except Exception as e:
        logger.warning("Startup migrations: %s", e)



def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    return "text/html" in accept and "application/json" not in accept.split(",")[0]


def _is_secure(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    proto = request.headers.get("x-forwarded-proto", "").lower()
    return proto == "https"


@app.middleware("http")
async def https_and_slash_middleware(request: Request, call_next):
    """
    - Si force_https: redirige HTTP → HTTPS (útil detrás de proxy o con TLS).
    - Normaliza barra final en rutas HTML (excepto / y estáticos).
    """
    path = request.url.path

    if (settings.force_https or _FORCE_HTTPS_RUNTIME) and not _is_secure(request):
        # Construir URL https conservando host/path/query
        host = request.headers.get("host") or f"127.0.0.1:{settings.app_port}"
        qs = f"?{request.url.query}" if request.url.query else ""
        target = f"https://{host}{path}{qs}"
        return RedirectResponse(url=target, status_code=307)

    # Redirección inteligente de barra final (solo GET de páginas)
    if (
        request.method == "GET"
        and path != "/"
        and path.endswith("/")
        and not path.startswith("/static")
        and not path.startswith("/docs")
        and not path.startswith("/api")
    ):
        qs = f"?{request.url.query}" if request.url.query else ""
        return RedirectResponse(url=path.rstrip("/") + qs, status_code=307)

    return await call_next(request)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    logger.warning("AppError %s: %s", exc.code, exc.message)
    try:
        from app.core.event_log import push as log_push
        log_push("warning", f"AppError {exc.code}: {exc.message}", source="api", path=str(request.url.path))
    except Exception:
        pass
    if _wants_html(request):
        from fastapi.responses import HTMLResponse

        html = f"""<!DOCTYPE html><html><head><meta charset=utf-8><title>Error</title>
        <link rel="stylesheet" href="/static/app.css">
        </head><body>
        <main class="container">
        <h1>{exc.user_message}</h1>
        <p class="muted"><code>{exc.code}</code> — {exc.message}</p>
        <p><a class="btn" href="/">Volver al inicio</a></p>
        <p class="faint">Si es error de base de datos, configura la conexión en el launcher (config.ini).</p>
        </main></body></html>"""
        return HTMLResponse(status_code=exc.http_status, content=html)
    return JSONResponse(status_code=exc.http_status, content=exc.to_dict())


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Error no controlado en %s", request.url.path)
    try:
        from app.core.event_log import push as log_push
        import traceback
        log_push(
            "error",
            f"{type(exc).__name__}: {exc}",
            source="api",
            path=str(request.url.path),
            detail="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[-3000:],
        )
    except Exception:
        pass
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
        <link rel="stylesheet" href="/static/app.css">
        </head><body>
        <main class="container">
        <h1>Error interno</h1>
        <p>{payload['user_message']}</p>
        <p class="muted"><code>{type(exc).__name__}: {exc}</code></p>
        <p><a class="btn" href="/">Volver al inicio</a></p>
        </main></body></html>"""
        return HTMLResponse(status_code=500, content=html)
    return JSONResponse(status_code=500, content=payload)


@app.on_event("startup")
async def on_startup():
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Fajos Piteados Central v%s (debug=%s, force_https=%s)",
        __version__,
        settings.debug,
        settings.force_https,
    )


def _ssl_kwargs() -> dict:
    cert = (settings.ssl_certfile or "").strip()
    key = (settings.ssl_keyfile or "").strip()
    if not cert or not key:
        # Rutas por defecto si existen
        default_cert = BASE_DIR / "certs" / "cert.pem"
        default_key = BASE_DIR / "certs" / "key.pem"
        if default_cert.exists() and default_key.exists():
            cert, key = str(default_cert), str(default_key)
        else:
            return {}
    cert_p, key_p = Path(cert), Path(key)
    if not cert_p.is_absolute():
        cert_p = BASE_DIR / cert_p
    if not key_p.is_absolute():
        key_p = BASE_DIR / key_p
    if cert_p.exists() and key_p.exists():
        return {"ssl_certfile": str(cert_p), "ssl_keyfile": str(key_p)}
    logger.warning("Certificados SSL configurados pero no encontrados: %s %s", cert_p, key_p)
    return {}


def run():
    import uvicorn

    ssl_kw = _ssl_kwargs()
    if ssl_kw:
        global _FORCE_HTTPS_RUNTIME
        _FORCE_HTTPS_RUNTIME = True
        logger.info("Iniciando con HTTPS (certificados SSL; redirección HTTP→HTTPS activa)")
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug and not ssl_kw,  # reload + SSL a veces problemático
        **ssl_kw,
    )


if __name__ == "__main__":
    run()
