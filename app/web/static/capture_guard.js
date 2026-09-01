/**
 * Bloque A — captura diaria más segura:
 * - Normaliza gramos a 1 decimal (sin 0.01)
 * - Confirma si el valor es "raro" vs promedio del trabajador (umbral ops)
 * - Deshacer último cambio de gramos (sesión)
 * - Enter avanza al siguiente pendiente en Solo hoy / Plata hoy
 */
(function (global) {
  var undoStack = [];
  var MAX_UNDO = 30;
  var anomalyPct = 0.30;

  function parseNum(v) {
    if (v === null || v === undefined || v === "") return null;
    var n = parseFloat(String(v).replace(",", "."));
    return isNaN(n) ? null : n;
  }

  /** Un decimal máximo; vacío si null */
  function formatGram(v) {
    var n = parseNum(v);
    if (n === null) return "";
    // redondear a 1 decimal
    n = Math.round(n * 10) / 10;
    if (Math.abs(n - Math.round(n)) < 1e-9) return String(Math.round(n));
    return n.toFixed(1);
  }

  function normalizeInput(inp) {
    if (!inp) return;
    var n = parseNum(inp.value);
    if (n === null) {
      inp.value = "";
      return;
    }
    inp.value = formatGram(n);
  }

  function loadAnomaly() {
    fetch("/api/ops/settings")
      .then(function (r) { return r.json(); })
      .then(function (s) {
        if (s && s.anomaly_pct != null) anomalyPct = Number(s.anomaly_pct) || 0.3;
      })
      .catch(function () {});
  }

  function avgOtherDays(tr, excludeDia) {
    if (!tr) return null;
    var sum = 0, n = 0;
    tr.querySelectorAll("input.cell-gm").forEach(function (inp) {
      if (excludeDia && inp.dataset.dia === excludeDia) return;
      var v = parseNum(inp.value);
      if (v !== null && v > 0) {
        sum += v;
        n += 1;
      }
    });
    return n ? sum / n : null;
  }

  function isAnomalous(value, avg) {
    if (value === null || value === 0) return false;
    if (avg === null || avg <= 0) {
      // sin historial: umbral absoluto suave
      return value >= 40;
    }
    var lo = avg * (1 - anomalyPct);
    var hi = avg * (1 + anomalyPct);
    // también flag valores muy altos absolutos
    if (value >= Math.max(hi, avg * 2, 25) || value > hi) return true;
    if (value < lo && avg >= 2) return true;
    return false;
  }

  function pushUndo(entry) {
    undoStack.push(entry);
    if (undoStack.length > MAX_UNDO) undoStack.shift();
    updateUndoBtn();
  }

  function updateUndoBtn() {
    var btn = document.getElementById("btn-undo-gram");
    if (!btn) return;
    btn.disabled = undoStack.length === 0;
    btn.title = undoStack.length
      ? "Deshacer último gramo (" + undoStack.length + ")"
      : "Nada que deshacer";
  }

  async function undoLast() {
    var last = undoStack.pop();
    updateUndoBtn();
    if (!last) return;
    var inp = document.querySelector(
      'input.cell-gm[data-id="' + last.id + '"][data-dia="' + last.dia + '"]'
    );
    if (!inp) {
      if (window.FajosLive) FajosLive.showToast("No se encontró la celda", true);
      return;
    }
    inp.value = last.prev === null || last.prev === "" ? "" : formatGram(last.prev);
    inp.dataset._prev = inp.value;
    try {
      if (typeof global.__fajosSaveGram === "function") {
        await global.__fajosSaveGram(inp);
      }
      if (window.FajosLive) FajosLive.showToast("Deshecho");
    } catch (e) {
      if (window.FajosLive) FajosLive.showToast("No se pudo deshacer", true);
    }
  }

  /**
   * beforeSave: retorna false para cancelar
   * skipRare: true en undo
   */
  async function guardBeforeSave(inp, opts) {
    opts = opts || {};
    normalizeInput(inp);
    var val = parseNum(inp.value);
    var prev = opts.prevValue;
    if (prev === undefined) prev = inp.dataset._prev;
    if (String(formatGram(val)) === String(formatGram(prev)) || (val === null && (prev === "" || prev == null))) {
      return true; // sin cambio
    }
    if (opts.skipRare) return true;
    var tr = inp.closest("tr");
    var avg = avgOtherDays(tr, inp.dataset.dia);
    if (isAnomalous(val, avg)) {
      var msg =
        "¿Confirmas " +
        formatGram(val) +
        " g?\n\n" +
        (avg != null
          ? "Promedio otros días ≈ " + formatGram(avg) + " g (±" + Math.round(anomalyPct * 100) + "%)."
          : "Es un valor alto sin historial en la fila.") +
        "\n\nAceptar = guardar · Cancelar = volver.";
      if (!confirm(msg)) {
        inp.value = prev === null || prev === undefined ? "" : formatGram(prev);
        return false;
      }
    }
    pushUndo({
      id: inp.dataset.id,
      dia: inp.dataset.dia,
      prev: prev,
      next: val,
      saveFn: opts.saveFn,
    });
    return true;
  }

  function bindCellGm(inp, saveFn) {
    if (!inp || inp.dataset.guardBound) return;
    inp.dataset.guardBound = "1";
    inp.step = "0.1";
    inp.setAttribute("step", "0.1");
    inp.setAttribute("inputmode", "decimal");
    // normalizar valor inicial
    if (inp.value) inp.value = formatGram(inp.value);

    inp.addEventListener("focus", function () {
      inp.dataset._prev = inp.value;
    });

    var saving = false;
    async function doSave(skipRare) {
      if (saving || inp.readOnly || inp.disabled) return;
      var prev = inp.dataset._prev;
      var ok = await guardBeforeSave(inp, { prevValue: prev, skipRare: skipRare, saveFn: saveFn });
      if (!ok) return;
      if (String(inp.value) === String(prev)) return;
      saving = true;
      try {
        await saveFn(inp);
        inp.dataset._prev = inp.value;
      } finally {
        saving = false;
      }
    }

    // blur handled carefully: only if value changed
    inp.addEventListener("blur", function () {
      doSave(false);
    });

    inp.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        doSave(false).then(function () {
          focusNextPending(inp);
        });
      }
    });
  }

  function focusNextPending(fromInp) {
    var list = Array.prototype.slice.call(
      document.querySelectorAll("input.cell-gm.hoy-input, input.cell-gm[data-dia].cell-hoy, input.cell-gm")
    ).filter(function (el) {
      return !el.readOnly && !el.disabled && el.offsetParent !== null;
    });
    // Prefer pending (empty) after current
    var idx = list.indexOf(fromInp);
    var i, el;
    for (i = idx + 1; i < list.length; i++) {
      el = list[i];
      if (!parseNum(el.value)) {
        el.focus();
        el.select && el.select();
        return;
      }
    }
    for (i = 0; i < list.length; i++) {
      el = list[i];
      if (el === fromInp) continue;
      if (!parseNum(el.value)) {
        el.focus();
        el.select && el.select();
        return;
      }
    }
    // siguiente cualquiera
    if (idx >= 0 && idx + 1 < list.length) {
      list[idx + 1].focus();
    }
  }

  function ensureUndoButton() {
    if (document.getElementById("btn-undo-gram")) return;
    var toolbar = document.querySelector(".toolbar") || document.querySelector(".page-head");
    if (!toolbar) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.id = "btn-undo-gram";
    btn.className = "btn btn-secondary";
    btn.textContent = "↩ Deshacer gramo";
    btn.disabled = true;
    btn.addEventListener("click", function () {
      undoLast();
    });
    toolbar.appendChild(btn);
  }

  function init(saveFnFactory) {
    loadAnomaly();
    ensureUndoButton();
    document.querySelectorAll("input.cell-gm").forEach(function (inp) {
      bindCellGm(inp, async function (el) {
        if (typeof global.__fajosSaveGram === "function") {
          await global.__fajosSaveGram(el);
        } else if (typeof saveFnFactory === "function") {
          await saveFnFactory(el);
        }
      });
    });
    var colHoy = global.COL_HOY;
    if (colHoy) {
      document.querySelectorAll('input.cell-gm[data-dia="' + colHoy + '"]').forEach(function (inp) {
        inp.classList.add("hoy-input");
      });
    }
    updateUndoBtn();
  }

  global.FajosCaptureGuard = {
    init: init,
    formatGram: formatGram,
    normalizeInput: normalizeInput,
    undoLast: undoLast,
    bindCellGm: bindCellGm,
  };
})(window);
