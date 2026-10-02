/**
 * Acciones de folio (Terminar / Reactivar) — event delegation.
 * Advertencia si hay avance en la semana activa.
 */
(function (global) {
  "use strict";

  function toast(msg, err) {
    try {
      if (global.FajosLive && typeof FajosLive.showToast === "function") {
        FajosLive.showToast(msg, !!err);
        return;
      }
    } catch (e) {}
    var el = document.getElementById("toast");
    if (el) {
      el.hidden = false;
      el.textContent = msg;
      el.className = "toast-web" + (err ? " err" : " ok");
      clearTimeout(global._toastT);
      global._toastT = setTimeout(function () { el.hidden = true; }, 3200);
      return;
    }
    alert(msg);
  }

  async function postJson(url) {
    var res = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    });
    var data = {};
    try { data = await res.json(); } catch (e) {}
    return { res: res, data: data };
  }

  function parseNum(txt) {
    if (txt == null || txt === "") return 0;
    var v = parseFloat(String(txt).replace(/[^0-9.,\-]/g, "").replace(",", "."));
    return isNaN(v) ? 0 : v;
  }

  /** Gramos de la semana en la fila de esta línea */
  function avanceSemana(prodId) {
    var tr = document.querySelector('tr[data-prod-id="' + prodId + '"]');
    if (!tr) return { gramos: 0, found: false };
    var sum = 0;
    tr.querySelectorAll("input.cell-gm").forEach(function (inp) {
      var v = parseNum(inp.value);
      if (v > 0) sum += v;
    });
    if (sum <= 0) {
      var tot = tr.querySelector(".cell-total");
      if (tot) sum = parseNum(tot.getAttribute("data-total") || tot.textContent);
    }
    var tarifa = parseNum(tr.dataset.tarifa || "");
    if (!tarifa) {
      var tarTd = tr.querySelector("td.col-tar, [data-field='tarifa_gr']");
      if (tarTd) tarifa = parseNum(tarTd.textContent);
    }
    return { gramos: sum, tarifa: tarifa, found: true, efectivo: sum > 0 && tarifa > 0 ? sum * tarifa : 0 };
  }

  function fmtG(n) {
    if (!n) return "0";
    var x = Math.round(n * 10) / 10;
    return (x % 1 === 0) ? String(x) : x.toFixed(1);
  }

  async function askConfirm(opts) {
    if (global.FajosModal && typeof FajosModal.confirm === "function") {
      return FajosModal.confirm(opts);
    }
    // Fallback nativo
    var msg = (opts.title || "") + "\n\n" + (opts.message || "");
    if (opts.warn) msg += "\n\n⚠ " + opts.warn;
    if (opts.detail) msg += "\n\n" + opts.detail;
    return window.confirm(msg);
  }

  async function terminar(prodId, folio) {
    prodId = Number(prodId);
    if (!prodId || prodId <= 0) {
      toast("No se identificó la línea. Recarga la página (Ctrl+F5).", true);
      return;
    }
    var label = folio ? ("folio " + folio) : ("línea #" + prodId);
    var av = avanceSemana(prodId);
    var warn = "";
    var danger = false;
    if (av.found && av.gramos > 0) {
      danger = true;
      warn =
        "Este folio TIENE AVANCE en la semana activa: " +
        fmtG(av.gramos) + " g" +
        (av.efectivo > 0 ? (" · $" + av.efectivo.toFixed(2)) : "") +
        ".\n\nSi lo marcas como terminado/cerrado:\n" +
        "• Se oculta de la tabla de captura\n" +
        "• Los gramos de esta semana SÍ se conservan para el pago\n" +
        "• No aparecerá en Captura manual ni en nuevas semanas al duplicar\n\n" +
        "¿Seguro que ya terminó el trabajo de este folio?";
    }

    var ok = await askConfirm({
      title: "Marcar como terminado",
      message: "¿Cerrar " + label + "?",
      detail: av.gramos > 0
        ? "Los gramos de esta semana se mantienen en la nómina."
        : "Se oculta de la captura. Puedes reactivarlo después desde «folios terminados».",
      warn: warn,
      okLabel: av.gramos > 0 ? "Sí, terminó (con avance)" : "Marcar terminado",
      cancelLabel: "Cancelar",
      danger: danger,
    });
    if (!ok) return;

    toast("Guardando…");
    try {
      var out = await postJson("/api/produccion/linea/" + prodId + "/terminar");
      if (!out.res.ok || out.data.ok === false) {
        toast(out.data.error || out.data.message || ("Error HTTP " + out.res.status), true);
        return;
      }
      toast("Terminado: " + (out.data.folio || label));
      setTimeout(function () { location.reload(); }, 450);
    } catch (e) {
      console.error(e);
      toast("Error de red al terminar folio", true);
    }
  }

  async function reactivar(prodId, folio) {
    prodId = Number(prodId);
    if (!prodId || prodId <= 0) {
      toast("No se identificó la línea. Recarga la página.", true);
      return;
    }
    var label = folio ? ("folio " + folio) : ("línea #" + prodId);
    var ok = await askConfirm({
      title: "Reactivar folio",
      message: "¿Reactivar " + label + " para seguir capturando?",
      detail: "Volverá a aparecer en la tabla de Plata y en Captura manual.",
      okLabel: "Reactivar",
      cancelLabel: "Cancelar",
    });
    if (!ok) return;
    toast("Reactivando…");
    try {
      var out = await postJson("/api/produccion/linea/" + prodId + "/reactivar");
      if (!out.res.ok || out.data.ok === false) {
        toast(out.data.error || out.data.message || ("Error HTTP " + out.res.status), true);
        return;
      }
      toast("Reactivado: " + (out.data.folio || label));
      setTimeout(function () { location.reload(); }, 450);
    } catch (e) {
      toast("Error de red al reactivar", true);
    }
  }

  // API global usada por menús / plantillas
  global.marcarTerminado = function (prodId, folio) {
    return terminar(prodId, folio);
  };
  global.reactivarFolio = function (prodId, folio) {
    return reactivar(prodId, folio);
  };

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t || !t.closest) return;
    var term = t.closest("[data-action='terminar-folio'], .btn-folio-terminar");
    if (term) {
      ev.preventDefault();
      terminar(
        term.getAttribute("data-prod-id") || term.dataset.prodId,
        term.getAttribute("data-folio") || term.dataset.folio || ""
      );
      return;
    }
    var reac = t.closest("[data-action='reactivar-folio'], .btn-folio-reactivar");
    if (reac) {
      ev.preventDefault();
      reactivar(
        reac.getAttribute("data-prod-id") || reac.dataset.prodId,
        reac.getAttribute("data-folio") || reac.dataset.folio || ""
      );
    }
  });

  global.terminarLoteInactivos = async function (semanaId, minSemanas, countHint) {
    var n = countHint != null ? countHint : "?";
    var ok = await askConfirm({
      title: "Terminar en lote",
      message: "¿Terminar " + n + " folio(s) con " + minSemanas + "+ semanas sin avance?",
      detail: "Solo se cierran folios sin gramos recientes. Puedes reactivar uno por uno después.",
      okLabel: "Terminar lote",
      cancelLabel: "Cancelar",
      danger: true,
    });
    if (!ok) return;
    try {
      var fd = new FormData();
      if (semanaId) fd.set("semana_id", String(semanaId));
      fd.set("min_semanas", String(minSemanas || 2));
      var res = await fetch("/api/produccion/terminar-lote", {
        method: "POST",
        headers: { Accept: "application/json" },
        credentials: "same-origin",
        body: fd,
      });
      var data = await res.json().catch(function () { return {}; });
      if (!res.ok || data.ok === false) {
        toast(data.error || data.message || "Error al terminar lote", true);
        return;
      }
      toast("Terminados: " + (data.n || data.count || n));
      setTimeout(function () { location.reload(); }, 500);
    } catch (e) {
      toast("Error de red", true);
    }
  };
})(window);
