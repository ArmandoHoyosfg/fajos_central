"""Página Dev: diagnóstico operativo (estilo panel interno, no menú de usuario)."""
from __future__ import annotations

from fastapi.responses import HTMLResponse


def _esc(s: object) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_debug_page(
    *,
    db_ok: bool,
    columns: list[dict],
    mismatches: list[dict],
    sample_vela: list[dict],
    meta: dict | None = None,
    counts: dict | None = None,
    sync_result: dict | None = None,
    error: str | None = None,
) -> HTMLResponse:
    meta = meta or {}
    counts = counts or {}
    n_mm = len(mismatches)

    col_rows = "".join(
        f"<tr><td>{_esc(c.get('TABLE_NAME'))}</td>"
        f"<td>{_esc(c.get('COLUMN_NAME'))}</td>"
        f"<td><code>{_esc(c.get('COLUMN_TYPE') or c.get('DATA_TYPE'))}</code></td>"
        f"<td>{_esc(c.get('IS_NULLABLE'))}</td>"
        f"<td>{_esc(c.get('COLUMN_KEY'))}</td></tr>"
        for c in columns
    )
    mm_rows = "".join(
        f"<tr><td>{_esc(m.get('area'))}</td>"
        f"<td>{_esc(m.get('prod_id'))}</td>"
        f"<td>{_esc(m.get('trabajador_id'))}</td>"
        f"<td>{_esc(m.get('nombre_fila'))} / {_esc(m.get('ubic_fila'))}</td>"
        f"<td>{_esc(m.get('cat_nombre'))} / {_esc(m.get('cat_ubic'))}</td></tr>"
        for m in mismatches
    ) or '<tr><td colspan="5" class="muted">Sin desajustes por trabajador_id. OK.</td></tr>'

    vela_rows = "".join(
        f"<tr><td>{_esc(m.get('src'))}</td><td>{_esc(m.get('id'))}</td>"
        f"<td>{_esc(m.get('nombre'))}</td><td>{_esc(m.get('ubic'))}</td>"
        f"<td>{_esc(m.get('trabajador_id'))}</td><td>{_esc(m.get('extra'))}</td></tr>"
        for m in sample_vela
    ) or '<tr><td colspan="6" class="muted">Sin coincidencias «Vela»</td></tr>'

    sync_html = f"<div class='card'><strong>Última sincronización</strong><pre style='margin:0.5rem 0 0'>{_esc(sync_result)}</pre></div>" if sync_result else ""
    err_html = f'<p class="flash err">{_esc(error)}</p>' if error else ""

    status_color = "#a6e3a1" if db_ok else "#f38ba8"
    mm_color = "#a6e3a1" if n_mm == 0 else "#f9e2af"

    html = f"""<!DOCTYPE html>
<html lang="es" data-theme="oscuro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dev — Fajos Central</title>
  <link rel="stylesheet" href="/static/app.css">
  <style>
    .dev-kpis {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(140px,1fr)); gap:0.75rem; margin:1rem 0; }}
    .dev-kpis .card {{ padding:0.85rem 1rem; }}
    .dev-kpis .label {{ font-size:0.75rem; opacity:0.75; }}
    .dev-kpis .value {{ font-size:1.15rem; font-weight:700; margin-top:0.2rem; }}
    .dev-actions {{ display:flex; flex-wrap:wrap; gap:0.5rem; margin:1rem 0; }}
    .dev-section {{ margin-top:1.75rem; }}
    .dev-section h2 {{ font-size:1.05rem; margin-bottom:0.5rem; }}
    .dev-hint {{ font-size:0.85rem; opacity:0.8; margin-bottom:0.75rem; }}
    code {{ font-size:0.8rem; }}
  </style>
</head>
<body>
  <header class="topbar">
    <a class="brand" href="/"><span>Fajos Piteados Central</span></a>
    <span class="version-badge">v{_esc(meta.get('version', '?'))}</span>
    <span class="lan-badge">{_esc(meta.get('lan', '—'))}</span>
    <a class="dev-badge" href="/dev">Dev</a>
  </header>
  <main class="container page-enter">
    <div class="page-head">
      <div>
        <h1>Panel Dev</h1>
        <p class="muted">Diagnóstico operativo: integridad de datos, esquema y acciones de reparación.
        No es menú de captura diaria.</p>
      </div>
      <div class="toolbar">
        <a class="btn btn-secondary" href="/">← Inicio</a>
        <a class="btn btn-secondary" href="/produccion">Plata</a>
        <a class="btn btn-secondary" href="/trabajadores">Trabajadores</a>
      </div>
    </div>
    {err_html}
    {sync_html}

    <div class="dev-kpis">
      <div class="card">
        <div class="label">Base de datos</div>
        <div class="value" style="color:{status_color}">{'OK' if db_ok else 'ERROR'}</div>
      </div>
      <div class="card">
        <div class="label">Desajustes catálogo</div>
        <div class="value" style="color:{mm_color}">{n_mm}</div>
      </div>
      <div class="card">
        <div class="label">Trabajadores</div>
        <div class="value">{_esc(counts.get('trabajadores', '—'))}</div>
      </div>
      <div class="card">
        <div class="label">Líneas Plata (total)</div>
        <div class="value">{_esc(counts.get('plata', '—'))}</div>
      </div>
      <div class="card">
        <div class="label">Semanas</div>
        <div class="value">{_esc(counts.get('semanas', '—'))}</div>
      </div>
      <div class="card">
        <div class="label">Versión</div>
        <div class="value" style="font-size:1rem">v{_esc(meta.get('version', '?'))}</div>
      </div>
    </div>

    <div class="dev-actions">
      <form method="post" action="/dev/sync" style="display:inline">
        <button type="submit" class="btn">Sincronizar catálogo → nóminas</button>
      </form>
      <a class="btn btn-secondary" href="/dev">Refrescar diagnóstico</a>
      <a class="btn btn-secondary" href="/docs" target="_blank" rel="noopener">API docs</a>
      <a class="btn btn-secondary" href="/api/trabajadores">API trabajadores</a>
    </div>

    <section class="dev-section">
      <h2>Integridad: nombre / ubic vs catálogo</h2>
      <p class="dev-hint">Filas de Plata, Pita o Taller cuyo nombre o ubicación no coinciden con el trabajador ligado.
      Tras sincronizar deberían quedar en cero. La captura ya muestra el catálogo por JOIN; esto limpia el dato guardado.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Área</th><th>ID fila</th><th>trab_id</th><th>En nómina</th><th>En catálogo</th></tr></thead>
          <tbody>{mm_rows}</tbody>
        </table>
      </div>
    </section>

    <section class="dev-section">
      <h2>Muestra «Vela» (búsqueda de ejemplo)</h2>
      <p class="dev-hint">Compara catálogo vs producción para el mismo apellido — útil al depurar ubicaciones.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Origen</th><th>ID</th><th>Nombre</th><th>Ubic</th><th>trab_id</th><th>Extra</th></tr></thead>
          <tbody>{vela_rows}</tbody>
        </table>
      </div>
    </section>

    <section class="dev-section">
      <h2>Esquema (information_schema)</h2>
      <p class="dev-hint">Tipos reales en MariaDB. Si falta una columna de v3.17+, ejecuta la migración SQL correspondiente.</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Tabla</th><th>Columna</th><th>Tipo</th><th>Null</th><th>Key</th></tr></thead>
          <tbody>{col_rows or '<tr><td colspan="5" class="muted">No legible</td></tr>'}</tbody>
        </table>
      </div>
    </section>

    <section class="dev-section">
      <h2>Atajos útiles</h2>
      <ul class="dev-hint">
        <li><code>/api/trabajadores/sincronizar-todo</code> — POST sync global</li>
        <li><code>/trabajadores/{{id}}/qr</code> — ficha QR</li>
        <li><code>/m/t/{{id}}</code> — vista móvil por QR</li>
        <li>Migraciones: <code>db/schema/003_taller_fijo_folio_qr.sql</code></li>
      </ul>
    </section>
  </main>
</body>
</html>"""
    return HTMLResponse(html)
