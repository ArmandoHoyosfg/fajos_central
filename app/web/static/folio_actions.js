/**
 * Acciones de folio (Terminar / Reactivar) — event delegation.
 * No depende de onclick inline ni de que FajosLive esté listo.
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

  async function terminar(prodId, folio) {
    prodId = Number(prodId);
    if (!prodId || prodId <= 0) {
      toast("No se identificó la línea. Recarga la página (Ctrl+F5).", true);
      return;
    }
    var label = folio ? ("folio " + folio) : ("línea #" + prodId);
    if (!window.confirm(
      "¿Marcar " + label + " como terminado?\n\n" +
      "• Se oculta de la captura\n" +
      "• Los gramos de esta semana se conservan para el pago\n" +
      "• Puedes reactivarlo desde «folios terminados»"
    )) return;

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
    if (!window.confirm("¿Reactivar " + label + " para seguir capturando?")) return;
    toast("Reactivando…");
    try {
      var out = await postJson("/api/produccion/linea/" + prodId + "/reactivar");
      if (!out.res.ok || out.data.ok === false) {
        toast(out.data.error || out.data.message || ("Error HTTP " + out.res.status), true);
        return;
      }
      toast("Reactivado: " + (out.data.folio || label));
      setTimeout(function () { location.reload(); }, 400);
    } catch (e) {
      console.error(e);
      toast("Error de red al reactivar", true);
    }
  }

  // API global (row menu, onclick legacy)
  global.marcarTerminado = function (prodId, folio) {
    return terminar(prodId, folio);
  };
  global.reactivarFolio = function (prodId, folio) {
    return reactivar(prodId, folio);
  };

  // Delegación: funciona aunque el HTML se regenere
  document.addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t || !t.closest) return;
    var term = t.closest("[data-action='terminar-folio'], .btn-folio-terminar");
    if (term) {
      ev.preventDefault();
      ev.stopPropagation();
      terminar(term.getAttribute("data-prod-id") || term.dataset.prodId, term.getAttribute("data-folio") || term.dataset.folio || "");
      return;
    }
    var reac = t.closest("[data-action='reactivar-folio'], .btn-folio-reactivar");
    if (reac) {
      ev.preventDefault();
      ev.stopPropagation();
      reactivar(reac.getAttribute("data-prod-id") || reac.dataset.prodId, reac.getAttribute("data-folio") || reac.dataset.folio || "");
    }
  }, true); // capture phase: gana a otros handlers
})(window);
