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
    reasig = apr.get("reasignaciones") or []
    cands = apr.get("candidatos_dup") or []

    def _hint_label(h: str) -> str:
        return {
            "posible_finalizado": "Parece terminado (sin avance esta semana)",
            "posible_reasignacion": "Puede haberse pasado a otra persona",
            "sin_avance_esta_semana": "Sin gramos esta semana",
        }.get(h or "", h or "Revisar")

    fi_rows = ""
    for x in folio_inact:
        pid = x.get("prod_id") or ""
        hint = _hint_label(str(x.get("hint") or ""))
        prev = x.get("prev") or {}
        prev_txt = "—"
        if prev:
            prev_txt = f"{_esc(prev.get('nombre'))} · {_esc(prev.get('gramos'))} g · sem {_esc(prev.get('semana'))}"
        actions = (
            f"<form method='post' action='/dev/folio-accion' style='display:flex;gap:0.35rem;flex-wrap:wrap'>"
            f"<input type='hidden' name='prod_id' value='{_esc(pid)}'/>"
            f"<input type='hidden' name='accion' value='terminar'/>"
            f"<button type='submit' class='btn btn-secondary' style='padding:0.2rem 0.5rem;font-size:0.78rem'"
            f" title='Marca el trabajo como terminado'>Marcar terminado</button>"
            f"<a class='btn btn-secondary' style='padding:0.2rem 0.5rem;font-size:0.78rem' "
            f"href='/produccion?semana_id={_esc(x.get('semana_id'))}'>Abrir en Plata</a>"
            f"</form>"
        )
        fi_rows += (
            f"<tr><td><code>{_esc(x.get('folio'))}</code></td>"
            f"<td>{_esc(x.get('nombre'))}<br><span class='muted'>ubic {_esc(x.get('ubic'))}</span></td>"
            f"<td>{_esc(hint)}</td>"
            f"<td class='muted' style='font-size:0.85rem'>{prev_txt}</td>"
            f"<td>{actions}</td></tr>"
        )
    if not fi_rows:
        fi_rows = '<tr><td colspan="5" class="muted">Ningún folio inactivo detectado.</td></tr>'

    reasig_rows = ""
    for x in reasig:
        reasig_rows += (
            f"<tr><td><code>{_esc(x.get('folio'))}</code></td>"
            f"<td>{_esc((x.get('de') or {}).get('nombre'))} "
            f"<span class='muted'>(ubic {_esc((x.get('de') or {}).get('ubic'))})</span></td>"
            f"<td>→</td>"
            f"<td>{_esc((x.get('a') or {}).get('nombre'))} "
            f"<span class='muted'>(ubic {_esc((x.get('a') or {}).get('ubic'))})</span></td>"
            f"<td><a class='btn btn-secondary' style='padding:0.2rem 0.5rem;font-size:0.78rem' "
            f"href='/produccion?semana_id={_esc(x.get('semana_id'))}'>Ver en Plata</a></td></tr>"
        )
    if not reasig_rows:
        reasig_rows = '<tr><td colspan="5" class="muted">No se detectaron cambios de persona en folios.</td></tr>'

    cand_rows = ""
    for c in cands:
        det = c.get("detalle") or []
        if len(det) < 2:
            continue
        # Tarjetas claras: elegir A (se queda) vs B (se da de baja)
        cards = ""
        for i, d in enumerate(det):
            cards += (
                f"<label class='merge-card'>"
                f"<input type='radio' name='pick_{_esc(c.get('nombre'))}' value='{_esc(d['id'])}' "
                f"{'checked' if i==0 else ''} form='merge-{_esc(det[0]['id'])}'/>"
                f"<strong>ID {_esc(d['id'])}</strong><br>"
                f"Ubicación <b>{_esc(d['ubic'])}</b><br>"
                f"<span class='muted'>{'Activo' if d.get('activo') else 'Ya de baja'} · {_esc(d.get('tipo'))}</span>"
                f"</label>"
            )
        # Form with two selects labeled clearly, default different
        opts_keep = "".join(
            f"<option value='{_esc(d['id'])}'{' selected' if i==0 else ''}>"
            f"ID {_esc(d['id'])} — ubic {_esc(d['ubic'])} ({'activo' if d.get('activo') else 'baja'})</option>"
            for i, d in enumerate(det)
        )
        opts_merge = "".join(
            f"<option value='{_esc(d['id'])}'{' selected' if i==1 else ''}>"
            f"ID {_esc(d['id'])} — ubic {_esc(d['ubic'])} ({'activo' if d.get('activo') else 'baja'})</option>"
            for i, d in enumerate(det)
        )
        cand_rows += (
            f"<tr><td colspan='4' style='padding:0.75rem 1rem'>"
            f"<div style='margin-bottom:0.4rem'><strong style='text-transform:capitalize'>{_esc(c.get('nombre'))}</strong> "
            f"<span class='muted'>— {len(det)} fichas con el mismo nombre</span></div>"
            f"<form method='post' action='/dev/merge-trabajadores' id='merge-{_esc(det[0]['id'])}' "
            f"style='display:grid;gap:0.5rem;max-width:640px' "
            f"onsubmit=\"return confirm('Se quedará la ficha PRINCIPAL. La otra pasará a baja y todas sus líneas de nómina se moverán a la principal. ¿Continuar?');\">"
            f"<div style='display:grid;grid-template-columns:1fr 1fr;gap:0.75rem'>"
            f"<div><label class='muted' style='font-size:0.8rem'>1. Ficha que SE QUEDA (principal)</label>"
            f"<select name='id_keep' required style='width:100%'>{opts_keep}</select></div>"
            f"<div><label class='muted' style='font-size:0.8rem'>2. Ficha que se ELIMINA (baja + mover datos)</label>"
            f"<select name='id_merge' required style='width:100%'>{opts_merge}</select></div>"
            f"</div>"
            f"<button type='submit' class='btn' style='justify-self:start'>Unir fichas</button>"
            f"</form></td></tr>"
        )
    if not cand_rows:
        cand_rows = '<tr><td colspan="4" class="muted">No hay nombres repetidos en el catálogo.</td></tr>'
    apr_note = ""
    if apr and not apr.get("tabla_ok", True):
        apr_note = '<p class="flash err">Para guardar el historial de aprendizaje, ejecuta en HeidiSQL: <code>db/schema/004_aprendizaje_merge.sql</code></p>'

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
<section class="card" style="margin:1rem 0;padding:1rem;border:1px solid var(--border,#333);border-radius:10px;">
  <h2 style="margin:0 0 0.5rem;display:flex;align-items:center;gap:0.4rem;">
    <img src="/static/icons/repair.svg" width="20" height="20" alt=""/> Reparación inteligente
  </h2>
  <p class="muted" style="font-size:0.9rem">Ejecuta en orden: migraciones → totales → consistencia → huérfanos → sync catálogo.</p>
  <form method="post" action="/dev/reparar-inteligente" style="display:inline">
    <button type="submit" class="btn">Ejecutar reparación completa</button>
  </form>
  <form method="post" action="/dev/migrar" style="display:inline;margin-left:0.4rem">
    <button type="submit" class="btn btn-secondary">Solo migraciones</button>
  </form>
</section>
<section class="card" style="margin:1rem 0;padding:1rem;border:1px solid var(--border,#333);border-radius:10px;">
  <h2 style="margin:0 0 0.5rem;display:flex;align-items:center;gap:0.4rem;">
    <img src="/static/icons/dev.svg" width="20" height="20" alt=""/> Comandos útiles
  </h2>
  <div style="display:flex;flex-wrap:wrap;gap:0.4rem;">
    <form method="post" action="/dev/sync"><button class="btn btn-secondary" type="submit">Sync nóminas</button></form>
    <form method="post" action="/dev/reparar-huerfanos"><button class="btn btn-secondary" type="submit">Reparar huérfanos</button></form>
    <form method="post" action="/dev/crear-semana-actual"><button class="btn btn-secondary" type="submit">Crear semana actual</button></form>
    <a class="btn btn-secondary" href="/api/consistencia">API consistencia</a>
    <a class="btn btn-secondary" href="/api/consistencia/reparar" onclick="event.preventDefault();fetch(this.href.replace('/api','/api'),{{method:'POST'}}).then(r=>r.json()).then(d=>alert(JSON.stringify(d))).catch(e=>alert(e))">API reparar</a>
    <a class="btn btn-secondary" href="/docs" target="_blank">OpenAPI /docs</a>
    <a class="btn btn-secondary" href="/api/export/master">Master Excel</a>
    <a class="btn btn-secondary" href="/">Dashboard</a>
  </div>
  <p class="muted" style="margin-top:0.6rem;font-size:0.82rem">
    Consola visible solo con <code>start_dev.bat</code>. Uso diario: <code>start.bat</code> (sin ventana negra).
  </p>
</section>

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

    
        <section class="dev-section" id="dev-console-section">
      <h2>Consola en vivo <span class="muted" style="font-weight:400;font-size:0.85rem">(solo lectura)</span></h2>
      <p class="dev-hint">Eventos del servidor y del navegador. Si un botón no responde, el error suele aparecer aquí.</p>
      <div class="dev-console-toolbar">
        <label><input type="checkbox" id="dev-log-autoscroll" checked> Auto-scroll</label>
        <label><input type="checkbox" id="dev-log-pause"> Pausar</label>
        <button type="button" class="btn btn-secondary btn-xs" id="dev-log-clear">Limpiar</button>
        <span class="muted" id="dev-log-status">conectando…</span>
      </div>
      <pre id="dev-console" class="dev-console" aria-live="polite"></pre>
    </section>
    <script src="/static/dev_console.js"></script>


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
      <h2 id="folios">Folios sin avance</h2>
      <p class="dev-hint">Sin gramos esta semana. Puedes marcar como terminado o abrir Plata para corregir.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Folio</th><th>Quién lo tiene ahora</th><th>Qué parece</th><th>Semana pasada</th><th>Qué hacer</th></tr></thead>
        <tbody>{fi_rows}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2>Folios que cambiaron de persona</h2>
      <p class="dev-hint">La semana pasada tenía gramos una persona; esta semana otra. Revisa si es reasignación real.</p>
      <div class="table-wrap"><table>
        <thead><tr><th>Folio</th><th>Antes</th><th></th><th>Ahora</th><th></th></tr></thead>
        <tbody>{reasig_rows}</tbody>
      </table></div>
    </section>

    <section class="dev-section">
      <h2 id="dup">Personas con el mismo nombre (posibles duplicados)</h2>
      <p class="dev-hint">Elige la ficha <strong>principal</strong> (se queda) y la que se da de baja.
      Todas las nóminas del secundario pasan a la principal.</p>
      <div class="table-wrap"><table>
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
