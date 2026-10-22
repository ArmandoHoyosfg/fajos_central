/**
 * Ordenación de tablas por clic en <th data-sort-col>.
 * Uso: th con data-sort-col="N" (índice 0-based de celda td).
 * Opcional: data-sort-type="num" en th; data-sort-val en td.
 * Botón [data-sort-reset] restaura orden original (data-sort-idx en tr).
 */
(function () {
  function textOf(td) {
    if (!td) return '';
    if (td.getAttribute && td.getAttribute('data-sort-val') != null) {
      return String(td.getAttribute('data-sort-val')).trim();
    }
    var inp = td.querySelector('input:not([type="checkbox"]):not([type="hidden"]), select');
    if (inp) return (inp.value || '').trim();
    // Evitar texto de botones/menús dentro de la celda
    var clone = td.cloneNode(true);
    Array.prototype.forEach.call(clone.querySelectorAll('button, .row-menu, .btn-row-menu'), function (el) {
      el.parentNode && el.parentNode.removeChild(el);
    });
    return (clone.textContent || '').trim();
  }

  function parseVal(s, forceNum) {
    if (s === '' || s === '—' || s === '-' || s == null) return null;
    var cleaned = String(s).replace(/[$,%\s]/g, '').replace(',', '.');
    if (forceNum || /^-?\d+(\.\d+)?$/.test(cleaned)) {
      var n = parseFloat(cleaned);
      return isNaN(n) ? String(s).toLowerCase() : n;
    }
    return String(s).toLowerCase();
  }

  function cmp(a, b, dir) {
    if (a === null && b === null) return 0;
    if (a === null) return 1;  // vacíos al final
    if (b === null) return -1;
    if (typeof a === 'number' && typeof b === 'number') {
      return dir === 'asc' ? a - b : b - a;
    }
    // Si uno es número y otro no, número primero en asc
    if (typeof a === 'number' && typeof b !== 'number') return dir === 'asc' ? -1 : 1;
    if (typeof a !== 'number' && typeof b === 'number') return dir === 'asc' ? 1 : -1;
    var as = String(a), bs = String(b);
    if (as < bs) return dir === 'asc' ? -1 : 1;
    if (as > bs) return dir === 'asc' ? 1 : -1;
    return 0;
  }

  function initTable(table) {
    if (!table || table.dataset.sortReady === '1') return;
    table.dataset.sortReady = '1';
    var tbody = table.tBodies[0];
    if (!tbody) return;

    // Solo filas de datos (no expand/filler)
    function dataRows() {
      return Array.prototype.filter.call(tbody.rows, function (tr) {
        if (tr.classList.contains('por-dia-expand')) return false;
        if (tr.dataset.sortSkip === '1') return false;
        return true;
      });
    }

    dataRows().forEach(function (tr, i) {
      if (tr.dataset.sortIdx === undefined) tr.dataset.sortIdx = String(i);
    });

    var state = { col: null, dir: null };

    function clearMarks() {
      Array.prototype.forEach.call(table.querySelectorAll('th[data-sort-col]'), function (th) {
        th.classList.remove('sort-asc', 'sort-desc');
        var m = th.querySelector('.sort-mark');
        if (m) m.textContent = '';
      });
    }

    function sortBy(col, dir) {
      var th = table.querySelector('th[data-sort-col="' + col + '"]');
      var forceNum = th && th.getAttribute('data-sort-type') === 'num';
      var rows = dataRows();
      rows.sort(function (ra, rb) {
        var va = parseVal(textOf(ra.cells[col]), forceNum);
        var vb = parseVal(textOf(rb.cells[col]), forceNum);
        var c = cmp(va, vb, dir);
        if (c !== 0) return c;
        // desempate estable por orden original
        return (parseInt(ra.dataset.sortIdx, 10) || 0) - (parseInt(rb.dataset.sortIdx, 10) || 0);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
      clearMarks();
      if (th) {
        th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
        var m = th.querySelector('.sort-mark');
        if (!m) {
          m = document.createElement('span');
          m.className = 'sort-mark';
          th.appendChild(m);
        }
        m.textContent = dir === 'asc' ? ' ▲' : ' ▼';
      }
      state.col = col;
      state.dir = dir;
      try {
        table.dispatchEvent(new CustomEvent('fajos:sorted', { detail: { col: col, dir: dir } }));
      } catch (e) {}
    }

    function reset() {
      var rows = dataRows();
      rows.sort(function (a, b) {
        return (parseInt(a.dataset.sortIdx, 10) || 0) - (parseInt(b.dataset.sortIdx, 10) || 0);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
      clearMarks();
      state.col = null;
      state.dir = null;
    }

    Array.prototype.forEach.call(table.querySelectorAll('th[data-sort-col]'), function (th) {
      th.style.cursor = 'pointer';
      th.title = (th.title ? th.title + ' · ' : '') + 'Clic para ordenar';
      if (!th.querySelector('.sort-mark')) {
        var span = document.createElement('span');
        span.className = 'sort-mark';
        th.appendChild(span);
      }
      th.addEventListener('click', function (e) {
        // no ordenar si se clicó un input dentro del th
        if (e.target && (e.target.tagName === 'INPUT' || e.target.closest('input'))) return;
        var col = parseInt(th.getAttribute('data-sort-col'), 10);
        if (isNaN(col)) return;
        var dir = (state.col === col && state.dir === 'asc') ? 'desc' : 'asc';
        sortBy(col, dir);
      });
    });

    table._fajosSortReset = reset;
    table._fajosSortBy = sortBy;
  }

  function boot() {
    document.querySelectorAll('table.sortable, table[data-sortable]').forEach(initTable);
    document.querySelectorAll('[data-sort-reset]').forEach(function (btn) {
      if (btn.dataset.sortResetBound) return;
      btn.dataset.sortResetBound = '1';
      btn.addEventListener('click', function () {
        var sel = btn.getAttribute('data-sort-reset') || 'table.sortable';
        document.querySelectorAll(sel).forEach(function (table) {
          if (table._fajosSortReset) table._fajosSortReset();
          else {
            // permitir reinicializar si se añadió tarde
            table.dataset.sortReady = '';
            initTable(table);
            if (table._fajosSortReset) table._fajosSortReset();
          }
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  // API pública por si se agregan filas dinámicamente
  window.FajosTableSort = {
    init: initTable,
    reindex: function (table) {
      if (!table) return;
      table.dataset.sortReady = '';
      var tbody = table.tBodies[0];
      if (tbody) {
        Array.prototype.forEach.call(tbody.rows, function (tr, i) {
          tr.dataset.sortIdx = String(i);
        });
      }
      initTable(table);
    }
  };
})();
