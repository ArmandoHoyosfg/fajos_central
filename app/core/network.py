"""IP local de la red (LAN) para acceso desde otros equipos."""
from __future__ import annotations

import socket
from functools import lru_cache


@lru_cache(maxsize=1)
def local_ip() -> str:
    """
    Mejor esfuerzo: IP IPv4 de la interfaz usada para salir a la LAN.
    No es 127.0.0.1 si hay red.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        # no envía datos reales; solo elige interfaz de ruta
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            cand = info[4][0]
            if cand and not cand.startswith("127."):
                return cand
    except Exception:
        pass
    return "127.0.0.1"


def lan_urls(port: int = 8000, https: bool = False) -> dict[str, str]:
    ip = local_ip()
    scheme = "https" if https else "http"
    return {
        "ip": ip,
        "local": f"{scheme}://127.0.0.1:{port}",
        "lan": f"{scheme}://{ip}:{port}",
    }
