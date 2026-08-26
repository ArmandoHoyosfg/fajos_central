/**
 * Ordenación de tablas por clic en <th data-sort-col>.
 * Uso: th con data-sort-col="N" (índice 0-based de celda).
 * Botón [data-sort-reset] restaura orden original (data-sort-idx en tr).
 */
(function () {
  function textOf(td) {
    if (!td) return '';
    var inp = td.querySelector('input, select');
    if (inp) return (inp.value || '').trim();
    return (td.textContent || '').trim();
  }

  function parseVal(s) {
    if (s === '' || s === '—' || s === '-') return null;
    var n = s.replace(/[$,\s]/g, '').replace(',', '.');
    if (/^-?\d+(\.\d+)?$/.test(n)) return parseFloat(n);
    return s.toLowerCase();
  }

  function cmp(a, b, dir) {
    if (a === null && b === null) return 0;
    if (a === null) return 1;
    if (b === null) return -1;
    if (typeof a === 'number' && typeof b === 'number') {
      return dir === 'asc' ? a - b : b - a;
    }
    var as = String(a), bs = String(b);
    if (as < bs) return dir === 'asc' ? -1 : 1;
    if (as > bs) return dir === 'asc' ? 1 : -1;
    return 0;
  }

  function initTable(table) {
    if (!table || table.dataset.sortReady) return;
    table.dataset.sortReady = '1';
    var tbody = table.tBodies[0];
    if (!tbody) return;
    Array.prototype.forEach.call(tbody.rows, function (tr, i) {
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
      var rows = Array.prototype.slice.call(tbody.rows);
      rows.sort(function (ra, rb) {
        var va = parseVal(textOf(ra.cells[col]));
        var vb = parseVal(textOf(rb.cells[col]));
        var c = cmp(va, vb, dir);
        if (c !== 0) return c;
        return (parseInt(ra.dataset.sortIdx, 10) || 0) - (parseInt(rb.dataset.sortIdx, 10) || 0);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
      clearMarks();
      var th = table.querySelector('th[data-sort-col="' + col + '"]');
      if (th) {
        th.classList.add(dir === 'asc' ? 'sort-asc' : 'sort-desc');
        var m = th.querySelector('.sort-mark');
        if (m) m.textContent = dir === 'asc' ? ' ▲' : ' ▼';
      }
      state.col = col;
      state.dir = dir;
    }

    function reset() {
      var rows = Array.prototype.slice.call(tbody.rows);
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
        span.setAttribute('aria-hidden', 'true');
        th.appendChild(span);
      }
      th.addEventListener('click', function (e) {
        if (e.target.closest('button, a, input')) return;
        var col = parseInt(th.getAttribute('data-sort-col'), 10);
        if (isNaN(col)) return;
        var dir = (state.col === col && state.dir === 'asc') ? 'desc' : 'asc';
        sortBy(col, dir);
      });
    });

    table._fajosSortReset = reset;
  }

  function initAll() {
    document.querySelectorAll('table.sortable, table[data-sortable]').forEach(initTable);
    document.querySelectorAll('[data-sort-reset]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var sel = btn.getAttribute('data-sort-reset') || 'table.sortable';
        document.querySelectorAll(sel).forEach(function (t) {
          if (t._fajosSortReset) t._fajosSortReset();
        });
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
  window.FajosTableSort = { init: initAll };
})();
