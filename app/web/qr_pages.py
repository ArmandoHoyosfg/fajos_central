"""Páginas QR en HTML plano (sin Jinja) para no acoplar al motor de plantillas."""
from __future__ import annotations

from fastapi.responses import HTMLResponse


def html_esc(s: object) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def page_shell(*, title: str, heading: str, sub: str, body: str, extra_toolbar: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="es" data-theme="oscuro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <link rel="stylesheet" href="/static/app.css">
  <style>
    .qr-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:1rem; }}
    .qr-card {{ background:var(--surface,#1e1e2e); border:1px solid var(--border,#333);
               border-radius:12px; padding:1rem; text-align:center; }}
    .qr-card img {{ background:#fff; padding:6px; border-radius:8px; }}
    .qr-meta {{ margin-top:0.5rem; display:flex; flex-direction:column; gap:0.15rem; font-size:0.85rem; }}
    @media print {{ .topbar, .toolbar, .btn {{ display:none !important; }} }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span>Fajos Piteados Central</span></a>
  </header>
  <main class="container page-enter">
    <div class="page-head">
      <div>
        <h1>{heading}</h1>
        <p class="muted">{sub}</p>
      </div>
      <div class="toolbar">
        {extra_toolbar}
        <button type="button" class="btn" onclick="window.print()">Imprimir</button>
      </div>
    </div>
    {body}
  </main>
</body>
</html>"""


def response_trabajador_qr(trabajador_id: int, t: dict | None) -> HTMLResponse:
    nombre = f"#{trabajador_id}"
    ubic = "—"
    code = f"FC{trabajador_id:06d}"
    if isinstance(t, dict):
        nombre = str(t.get("nombre_mostrar") or nombre)
        if t.get("ubic") is not None:
            ubic = t.get("ubic")
        code = str(t.get("codigo_qr") or code)
    body = (
        f'<div class="card" style="max-width:360px;margin:1.5rem auto;text-align:center;padding:1.5rem;">'
        f'<img src="/api/trabajadores/{trabajador_id}/qr.png" alt="QR" width="220" height="220" '
        f'style="background:#fff;padding:8px;border-radius:8px;">'
        f'<p style="margin-top:1rem;font-weight:600;">{html_esc(nombre)}</p>'
        f'<p class="muted">Ubic {html_esc(ubic)} · ID {trabajador_id} · {html_esc(code)}</p>'
        f'<p class="muted faint" style="font-size:0.8rem;">Escaneo → /m/t/{trabajador_id}</p>'
        f"</div>"
    )
    html = page_shell(
        title=f"QR {html_esc(nombre)} — Fajos Central",
        heading="Código QR",
        sub=f"{html_esc(nombre)} · Ubic {html_esc(ubic)} · {html_esc(code)}",
        body=body,
        extra_toolbar=(
            '<a class="btn btn-secondary" href="/trabajadores">← Trabajadores</a> '
            '<a class="btn btn-secondary" href="/trabajadores/qr-lote">Todos los QR</a>'
        ),
    )
    return HTMLResponse(html)


def response_qr_lote(rows: list) -> HTMLResponse:
    cards = []
    for t in rows or []:
        try:
            tid = int(t["id"])
            nombre = str(t.get("nombre_mostrar") or "")
            ubic = t.get("ubic") or ""
            code = str(t.get("codigo_qr") or f"FC{tid:06d}")
            cards.append(
                f'<div class="qr-card">'
                f'<img src="/api/trabajadores/{tid}/qr.png" alt="QR" width="140" height="140">'
                f'<div class="qr-meta"><strong>{html_esc(nombre)}</strong>'
                f'<span class="muted">Ubic {html_esc(ubic)} · {html_esc(code)}</span></div></div>'
            )
        except Exception:
            continue
    body = (
        f'<div class="qr-grid">{"".join(cards)}</div>'
        if cards
        else '<p class="muted">No hay trabajadores activos.</p>'
    )
    html = page_shell(
        title="QR lote — Fajos Central",
        heading="Códigos QR — todos los activos",
        sub=f"{len(cards)} trabajadores",
        body=body,
        extra_toolbar='<a class="btn btn-secondary" href="/trabajadores">← Trabajadores</a>',
    )
    return HTMLResponse(html)


def response_movil_trabajador(
    trabajador_id: int, t: dict | None, des: dict | None
) -> HTMLResponse:
    nombre = f"#{trabajador_id}"
    ubic = "—"
    tipo = ""
    if isinstance(t, dict):
        nombre = str(t.get("nombre_mostrar") or nombre)
        if t.get("ubic") is not None:
            ubic = t.get("ubic")
        tipo = str(t.get("tipo") or "")
    des = des or {}
    abiertos = int(des.get("folios_abiertos") or 0)
    terminados = int(des.get("folios_terminados") or 0)
    gramos = float(des.get("gramos_registrados") or 0)
    items = ""
    for w in (des.get("trabajos") or [])[:20]:
        folio = w.get("folio") or "—"
        modelo = w.get("modelo") or ""
        est = "activo" if w.get("activo") else "terminado"
        items += f"<li>{html_esc(folio)} · {html_esc(modelo)} · {est}</li>"
    if not items:
        items = '<li class="muted">Sin folios</li>'
    body = (
        f'<div class="card" style="padding:1rem;">'
        f"<p><strong>Folios abiertos:</strong> {abiertos}</p>"
        f"<p><strong>Terminados:</strong> {terminados}</p>"
        f"<p><strong>Gramos (hist.):</strong> {gramos:.1f}</p>"
        f"</div>"
        f'<ul style="margin-top:1rem;">{items}</ul>'
        f'<p class="muted" style="font-size:0.85rem;">Vista móvil mínima (QR).</p>'
    )
    html = page_shell(
        title=f"{html_esc(nombre)} — Móvil",
        heading=html_esc(nombre),
        sub=f"Ubic {html_esc(ubic)} · {html_esc(tipo)}",
        body=body,
        extra_toolbar='<a class="btn btn-secondary" href="/trabajadores">Trabajadores</a>',
    )
    return HTMLResponse(html)
