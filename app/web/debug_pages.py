"""Página Dev: diagnóstico operativo."""
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
    orphans: list[dict] | None = None,
    migrations: list[dict] | None = None,
    folios_dup: list[dict] | None = None,
    semana_actual: dict | None = None,
    sync_result: dict | None = None,
    action_result: dict | None = None,
    error: str | None = None,
    aprendizaje: dict | None = None,
) -> HTMLResponse:
    meta = meta or {}
    counts = counts or {}
    orphans = orphans or []
    migrations = migrations or []
    folios_dup = folios_dup or []
    semana_actual = semana_actual or {}
    n_mm = len(mismatches)
    n_or = len(orphans)
    n_fd = len(folios_dup)
    mig_bad = [m for m in migrations if m.get("status") != "ok"]

    def rows_mm() -> str:
        if not mismatches:
            return '<tr><td colspan="5" class="muted">Sin desajustes. OK.</td></tr>'
        return "".join(
            f"<tr><td>{_esc(m.get('area'))}</td><td>{_esc(m.get('prod_id'))}</td>"
            f"<td>{_esc(m.get('trabajador_id'))}</td>"
            f"<td>{_esc(m.get('nombre_fila'))} / {_esc(m.get('ubic_fila'))}</td>"
            f"<td>{_esc(m.get('cat_nombre'))} / {_esc(m.get('cat_ubic'))}</td></tr>"
            for m in mismatches
        )

    def rows_or() -> str:
        if not orphans:
            return '<tr><td colspan="5" class="muted">Sin huérfanos. OK.</td></tr>'
        return "".join(
            f"<tr><td>{_esc(m.get('area'))}</td><td>{_esc(m.get('prod_id'))}</td>"
            f"<td>{_esc(m.get('nombre'))}</td><td>{_esc(m.get('ubic'))}</td>"
            f"<td>{_esc(m.get('trabajador_id'))}</td></tr>"
            for m in orphans
        )

    def rows_fd() -> str:
        if not folios_dup:
            return '<tr><td colspan="4" class="muted">No hay folios compartidos entre trabajadores distintos.</td></tr>'
        return "".join(
            f"<tr class='row-warn'><td><code>{_esc(m.get('folio'))}</code></td>"
            f"<td>{_esc(m.get('semana_codigo') or m.get('semana_id'))}</td>"
            f"<td>{_esc(m.get('n_trabajadores'))}</td>"
            f"<td>{_esc(m.get('quienes'))}</td></tr>"
            for m in folios_dup
        )

    def rows_mig() -> str:
        if not migrations:
            return '<tr><td colspan="4" class="muted">Sin comprobación</td></tr>'
        return "".join(
            f"<tr><td>{_esc(m.get('table'))}</td><td><code>{_esc(m.get('column'))}</code></td>"
            f"<td>{_esc(m.get('script'))}</td>"
            f"<td style='color:{'#a6e3a1' if m.get('status')=='ok' else '#f38ba8'}'>"
            f"{_esc(m.get('status'))}</td></tr>"
            for m in migrations
        )

    def rows_col() -> str:
        return "".join(
            f"<tr><td>{_esc(c.get('TABLE_NAME'))}</td><td>{_esc(c.get('COLUMN_NAME'))}</td>"
            f"<td><code>{_esc(c.get('COLUMN_TYPE') or c.get('DATA_TYPE'))}</code></td>"
            f"<td>{_esc(c.get('IS_NULLABLE'))}</td><td>{_esc(c.get('COLUMN_KEY'))}</td></tr>"
            for c in columns
        ) or '<tr><td colspan="5" class="muted">—</td></tr>'

    def rows_vela() -> str:
        return "".join(
            f"<tr><td>{_esc(m.get('src'))}</td><td>{_esc(m.get('id'))}</td>"
            f"<td>{_esc(m.get('nombre'))}</td><td>{_esc(m.get('ubic'))}</td>"
            f"<td>{_esc(m.get('trabajador_id'))}</td><td>{_esc(m.get('extra'))}</td></tr>"
            for m in sample_vela
        ) or '<tr><td colspan="6" class="muted">—</td></tr>'

    sa = semana_actual
    existe = bool(sa.get("existe"))
    if existe:
        estado_bd = (
            f"Sí · id={_esc(sa.get('semana_id'))}"
            + (" · CERRADA" if sa.get("cerrada") else " · abierta")
        )
        form_crear = ""
    else:
        estado_bd = '<span style="color:#f9e2af">No existe aún</span>'
        form_crear = (
            '<form method="post" action="/dev/crear-semana-actual" style="margin-top:0.5rem">'
            '<button type="submit" class="btn">Crear semana actual</button></form>'
        )

    semana_html = f"""
    <div class="card" style="margin:0.5rem 0 1rem">
      <p><strong>Hoy:</strong> {_esc(sa.get('hoy'))}</p>
      <p><strong>Rango calculado (sáb–vie):</strong>
         {_esc(sa.get('fecha_inicio'))} → {_esc(sa.get('fecha_fin'))}
         · código <code>{_esc(sa.get('codigo'))}</code></p>
      <p><strong>En BD:</strong> {estado_bd}</p>
      {form_crear}
    </div>
    """

    payload = action_result or sync_result
    action_html = (
        f"<div class='card'><strong>Última acción</strong>"
        f"<pre style='margin:0.5rem 0 0'>{_esc(payload)}</pre></div>"
        if payload
        else ""
    )
    err_html = f'<p class="flash err">{_esc(error)}</p>' if error else ""
    status_color = "#a6e3a1" if db_ok else "#f38ba8"

    apr = aprendizaje or {}
    folio_inact = apr.get("folios_inactivos") or []
    cands = apr.get("candidatos_dup") or []
    fi_rows = "".join(
        (
            "<tr><td><code>" + _esc(x.get("folio")) + "</code></td>"
            "<td>" + _esc(x.get("nombre")) + " / " + _esc(x.get("ubic")) + "</td>"
            "<td>" + _esc(x.get("hint")) + "</td>"
            "<td>" + _esc((x.get("prev") or {}).get("nombre"))
            + " (" + _esc((x.get("prev") or {}).get("gramos")) + " g)</td></tr>"
        )
        for x in folio_inact
    ) or '<tr><td colspan="4" class="muted">Ningún folio inactivo detectado.</td></tr>'
    cand_rows = ""
    for c in cands:
        det = c.get("detalle") or []
        opts = "".join(
            '<option value="' + _esc(d["id"]) + '">' + _esc(d["id"]) + " · ubic " + _esc(d["ubic"])
            + " · " + ("act" if d.get("activo") else "baja") + "</option>"
            for d in det
        )
        ids = c.get("ids") or []
        cand_rows += (
            "<tr><td>" + _esc(c.get("nombre")) + "</td><td>" + _esc(c.get("n")) + "</td>"
            "<td>" + _esc(", ".join(str(i) for i in ids)) + "</td>"
            "<td><form method='post' action='/dev/merge-trabajadores' "
            "style='display:flex;gap:0.35rem;flex-wrap:wrap;align-items:center' "
            "onsubmit=\"return confirm('Fusionar: el secundario se da de baja y sus lineas pasan al principal.');\">"
            "<select name='id_keep' required>" + opts + "</select>"
            "<span class='muted'>keep</span>"
            "<select name='id_merge' required>" + opts + "</select>"
            "<button type='submit' class='btn btn-secondary' style='padding:0.2rem 0.5rem;font-size:0.8rem'>Fusionar</button>"
            "</form></td></tr>"
        )
    if not cand_rows:
        cand_rows = '<tr><td colspan="4" class="muted">No hay nombres repetidos en el catálogo.</td></tr>'
    apr_note = ""
    if apr and not apr.get("tabla_ok", True):
        apr_note = '<p class="flash err">Ejecuta <code>db/schema/004_aprendizaje_merge.sql</code> en HeidiSQL.</p>'


    html = f"""<!DOCTYPE html>
<html lang="es" data-theme="oscuro">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dev — Fajos Central</title>
  <link rel="stylesheet" href="/static/app.css">
  <style>
    .dev-kpis {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(130px,1fr)); gap:0.75rem; margin:1rem 0; }}
    .dev-kpis .card {{ padding:0.85rem 1rem; }}
    .dev-kpis .label {{ font-size:0.75rem; opacity:0.75; }}
    .dev-kpis .value {{ font-size:1.15rem; font-weight:700; margin-top:0.2rem; }}
    .dev-actions {{ display:flex; flex-wrap:wrap; gap:0.5rem; margin:1rem 0; }}
    .dev-section {{ margin-top:1.75rem; }}
    .dev-section h2 {{ font-size:1.05rem; margin-bottom:0.35rem; }}
    .dev-hint {{ font-size:0.85rem; opacity:0.8; margin-bottom:0.75rem; }}
    tr.row-warn td {{ background: rgba(249, 226, 175, 0.12); }}
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
        <p class="muted">Integridad, migraciones, semana actual y reparación.</p>
      </div>
      <div class="toolbar">
        <a class="btn btn-secondary" href="/">← Inicio</a>
        <a class="btn btn-secondary" href="/produccion">Plata</a>
      </div>
    </div>
    {err_html}
    {action_html}

    <div class="dev-kpis">
      <div class="card"><div class="label">Base de datos</div>
        <div class="value" style="color:{status_color}">{'OK' if db_ok else 'ERROR'}</div></div>
      <div class="card"><div class="label">Desajustes</div>
        <div class="value">{n_mm}</div></div>
      <div class="card"><div class="label">Huérfanos</div>
        <div class="value" style="color:{'#a6e3a1' if n_or==0 else '#f9e2af'}">{n_or}</div></div>
      <div class="card"><div class="label">Folios duplicados</div>
        <div class="value" style="color:{'#a6e3a1' if n_fd==0 else '#f38ba8'}">{n_fd}</div></div>
      <div class="card"><div class="label">Migraciones</div>
        <div class="value" style="color:{'#a6e3a1' if not mig_bad else '#f38ba8'}">{'OK' if not mig_bad else str(len(mig_bad))+' faltan'}</div></div>
      <div class="card"><div class="label">Semana actual</div>
        <div class="value" style="font-size:0.95rem">{'Sí' if existe else 'No'}</div></div>
    </div>

    <div class="dev-actions">
      <form method="post" action="/dev/sync" style="display:inline">
        <button type="submit" class="btn">Sincronizar catálogo → nóminas</button>
      </form>
      <form method="post" action="/dev/reparar-huerfanos" style="display:inline">
        <button type="submit" class="btn btn-secondary">Reparar huérfanos</button>
      </form>
      <a class="btn btn-secondary" href="/dev">Refrescar</a>
      <a class="btn btn-secondary" href="/docs" target="_blank" rel="noopener">API</a>
    </div>

    <section class="dev-section">
      <h2>Semana actual (calendario sáb–vie)</h2>
      <p class="dev-hint">Lo que el sistema considera esta semana de pago según la fecha de hoy.</p>
      {semana_html}
    </section>

    <section class="dev-section">
      <h2>Migraciones / columnas esperadas</h2>
      <p class="dev-hint">Si algo está faltante, ejecuta el script en HeidiSQL.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Tabla</th><th>Columna</th><th>Script</th><th>Estado</th></tr></thead>
        <tbody>{rows_mig()}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Folios repetidos entre trabajadores</h2>
      <p class="dev-hint">Mismo folio en 2+ personas distintas. También se resaltan en Plata.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Folio</th><th>Semana</th><th>Nº personas</th><th>Quiénes</th></tr></thead>
        <tbody>{rows_fd()}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Huérfanos (sin trabajador válido)</h2>
      <p class="dev-hint">Reparar enlaza por nombre + ubic exactos del catálogo.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Área</th><th>ID</th><th>Nombre</th><th>Ubic</th><th>trab_id</th></tr></thead>
        <tbody>{rows_or()}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Desajustes nombre/ubic</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Área</th><th>ID</th><th>trab_id</th><th>Nómina</th><th>Catálogo</th></tr></thead>
        <tbody>{rows_mm()}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Muestra «Vela»</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Origen</th><th>ID</th><th>Nombre</th><th>Ubic</th><th>trab_id</th><th>Extra</th></tr></thead>
        <tbody>{rows_vela()}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Aprendizaje ligero</h2>
      {apr_note}
      <p class="dev-hint">Eventos 7 días: <strong>{_esc(apr.get('eventos_7d', 0))}</strong>.</p>
    </section>

    <section class="dev-section">
      <h2>Folios sin avance (posible fin / reasignación)</h2>
      <p class="dev-hint">0 g esta semana; con historial previo sugiere finalizado o reasignado.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Folio</th><th>Ahora</th><th>Sugerencia</th><th>Semana previa</th></tr></thead>
        <tbody>{fi_rows}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Posibles trabajadores duplicados</h2>
      <p class="dev-hint">Mismo nombre, varias fichas. Conservar uno y fusionar el otro en toda la BD.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Nombre</th><th>Nº</th><th>IDs</th><th>Fusionar</th></tr></thead>
        <tbody>{cand_rows}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Esquema</h2>
      <div class="table-wrap"><table>
        <thead><tr><th>Tabla</th><th>Columna</th><th>Tipo</th><th>Null</th><th>Key</th></tr></thead>
        <tbody>{rows_col()}</tbody>
      </table></div>
    </section>
  </main>
</body>
</html>"""
    return HTMLResponse(html)
