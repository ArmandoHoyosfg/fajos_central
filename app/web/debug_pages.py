"""Página de diagnóstico (dev) — no usa Jinja complejo."""
from __future__ import annotations

from fastapi.responses import HTMLResponse


def _esc(s: object) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def render_debug_page(
    *,
    db_ok: bool,
    columns: list[dict],
    mismatches: list[dict],
    sample_vela: list[dict],
    sync_result: dict | None = None,
    error: str | None = None,
) -> HTMLResponse:
    col_rows = ""
    for c in columns:
        col_rows += (
            f"<tr><td>{_esc(c.get('TABLE_NAME'))}</td>"
            f"<td>{_esc(c.get('COLUMN_NAME'))}</td>"
            f"<td>{_esc(c.get('COLUMN_TYPE') or c.get('DATA_TYPE'))}</td>"
            f"<td>{_esc(c.get('IS_NULLABLE'))}</td>"
            f"<td>{_esc(c.get('COLUMN_KEY'))}</td></tr>"
        )
    mm_rows = ""
    for m in mismatches:
        mm_rows += (
            f"<tr><td>{_esc(m.get('area'))}</td>"
            f"<td>{_esc(m.get('prod_id'))}</td>"
            f"<td>{_esc(m.get('trabajador_id'))}</td>"
            f"<td>{_esc(m.get('nombre_fila'))} / {_esc(m.get('ubic_fila'))}</td>"
            f"<td>{_esc(m.get('cat_nombre'))} / {_esc(m.get('cat_ubic'))}</td></tr>"
        )
    if not mm_rows:
        mm_rows = '<tr><td colspan="5" class="muted">Sin desajustes nombre/ubic vs catálogo (por trabajador_id).</td></tr>'
    vela_rows = ""
    for m in sample_vela:
        vela_rows += (
            f"<tr><td>{_esc(m.get('src'))}</td><td>{_esc(m.get('id'))}</td>"
            f"<td>{_esc(m.get('nombre'))}</td><td>{_esc(m.get('ubic'))}</td>"
            f"<td>{_esc(m.get('trabajador_id'))}</td><td>{_esc(m.get('extra'))}</td></tr>"
        )
    sync_html = ""
    if sync_result:
        sync_html = f"<pre class='card'>{_esc(sync_result)}</pre>"
    err_html = f'<p class="flash err">{_esc(error)}</p>' if error else ""
    html = f"""<!DOCTYPE html>
<html lang="es" data-theme="oscuro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dev / Debug — Fajos Central</title>
  <link rel="stylesheet" href="/static/app.css">
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span>Fajos Piteados Central</span></a>
    <a class="btn btn-secondary" href="/trabajadores">Trabajadores</a>
    <a class="btn btn-secondary" href="/produccion">Plata</a>
  </header>
  <main class="container page-enter">
    <div class="page-head">
      <div>
        <h1>Dev / Debug</h1>
        <p class="muted">Diagnóstico de BD, tipos y sincronización catálogo ↔ nóminas.
        BD: <strong style="color:{'#a6e3a1' if db_ok else '#f38ba8'}">{'OK' if db_ok else 'ERROR'}</strong></p>
      </div>
      <div class="toolbar">
        <form method="post" action="/dev/sync" style="display:inline">
          <button type="submit" class="btn">Sincronizar todo ahora</button>
        </form>
        <a class="btn btn-secondary" href="/dev">Refrescar</a>
      </div>
    </div>
    {err_html}
    {sync_html}

    <h2>Desajustes nombre/ubic (Plata / Pita / Taller vs catálogo)</h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Área</th><th>ID fila</th><th>trab_id</th><th>En nómina</th><th>En catálogo</th></tr></thead>
      <tbody>{mm_rows}</tbody>
    </table>
    </div>

    <h2>Muestra «Vela» / nombre similar</h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Origen</th><th>ID</th><th>Nombre</th><th>Ubic</th><th>trab_id</th><th>Extra</th></tr></thead>
      <tbody>{vela_rows or '<tr><td colspan="6" class="muted">Sin coincidencias</td></tr>'}</tbody>
    </table>
    </div>

    <h2>Tipos de columnas (tablas clave)</h2>
    <div class="table-wrap">
    <table>
      <thead><tr><th>Tabla</th><th>Columna</th><th>Tipo</th><th>Null</th><th>Key</th></tr></thead>
      <tbody>{col_rows or '<tr><td colspan="5" class="muted">No se pudieron leer information_schema</td></tr>'}</tbody>
    </table>
    </div>
  </main>
</body>
</html>"""
    return HTMLResponse(html)
