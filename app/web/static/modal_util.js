/**
 * Modales: cierre seguro + confirmaciones grandes y visibles.
 */
(function (global) {
  "use strict";

  function bindBackdrop(bg) {
    if (!bg || bg.dataset.modalBound) return;
    bg.dataset.modalBound = "1";
    bg.addEventListener("mousedown", function (e) {
      bg.dataset.closeIntent = e.target === bg ? "1" : "0";
    });
    bg.addEventListener("click", function (e) {
      if (e.target !== bg) return;
      if (bg.dataset.closeIntent !== "1") return;
      var sel = window.getSelection && window.getSelection();
      if (sel && String(sel).length > 0) return;
      bg.hidden = true;
    });
    var panel = bg.querySelector(".modal");
    if (panel) {
      panel.addEventListener("mousedown", function (e) {
        e.stopPropagation();
        bg.dataset.closeIntent = "0";
      });
    }
  }

  function bindAll() {
    document.querySelectorAll(".modal-backdrop").forEach(bindBackdrop);
  }

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    // Si hay un confirm pendiente, cancelarlo
    var conf = document.getElementById("fajos-confirm-backdrop");
    if (conf && !conf.hidden) {
      var cancel = conf.querySelector("[data-confirm-cancel]");
      if (cancel) cancel.click();
      return;
    }
    document.querySelectorAll(".modal-backdrop:not([hidden])").forEach(function (m) {
      m.hidden = true;
    });
  });

  /**
   * Confirmación grande (sustituye window.confirm).
   * @returns {Promise<boolean>}
   */
  function confirmDialog(opts) {
    opts = opts || {};
    var title = opts.title || "Confirmar";
    var message = opts.message || "¿Continuar?";
    var detail = opts.detail || "";
    var warn = opts.warn || "";
    var okLabel = opts.okLabel || "Confirmar";
    var cancelLabel = opts.cancelLabel || "Cancelar";
    var danger = !!opts.danger;

    return new Promise(function (resolve) {
      var bg = document.getElementById("fajos-confirm-backdrop");
      if (!bg) {
        bg = document.createElement("div");
        bg.id = "fajos-confirm-backdrop";
        bg.className = "modal-backdrop fajos-confirm-backdrop";
        bg.hidden = true;
        document.body.appendChild(bg);
        bindBackdrop(bg);
      }
      bg.innerHTML =
        '<div class="modal modal-confirm" role="dialog" aria-modal="true">' +
          '<h2 class="modal-confirm-title"></h2>' +
          '<p class="modal-confirm-msg"></p>' +
          '<div class="modal-confirm-warn" hidden></div>' +
          '<p class="modal-confirm-detail muted"></p>' +
          '<div class="actions modal-confirm-actions">' +
            '<button type="button" class="btn btn-secondary" data-confirm-cancel></button>' +
            '<button type="button" class="btn" data-confirm-ok></button>' +
          "</div>" +
        "</div>";

      bg.querySelector(".modal-confirm-title").textContent = title;
      bg.querySelector(".modal-confirm-msg").textContent = message;
      var det = bg.querySelector(".modal-confirm-detail");
      if (detail) {
        det.textContent = detail;
        det.hidden = false;
      } else {
        det.hidden = true;
      }
      var warnEl = bg.querySelector(".modal-confirm-warn");
      if (warn) {
        warnEl.hidden = false;
        warnEl.innerHTML = "<strong>⚠ Atención</strong><br>" + String(warn).replace(/\n/g, "<br>");
      } else {
        warnEl.hidden = true;
        warnEl.innerHTML = "";
      }
      var btnOk = bg.querySelector("[data-confirm-ok]");
      var btnCancel = bg.querySelector("[data-confirm-cancel]");
      btnOk.textContent = okLabel;
      btnCancel.textContent = cancelLabel;
      btnOk.className = danger ? "btn btn-danger" : "btn";

      function finish(val) {
        bg.hidden = true;
        btnOk.onclick = null;
        btnCancel.onclick = null;
        resolve(!!val);
      }
      btnOk.onclick = function () { finish(true); };
      btnCancel.onclick = function () { finish(false); };
      bg.hidden = false;
      try { btnOk.focus(); } catch (e) {}
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindAll);
  } else {
    bindAll();
  }

  global.FajosModal = {
    bindAll: bindAll,
    bindBackdrop: bindBackdrop,
    confirm: confirmDialog,
  };
})(window);
