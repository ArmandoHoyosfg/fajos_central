/**
 * Cierre seguro de modales:
 * - Solo cierra si mousedown y click fueron en el backdrop (no al soltar tras seleccionar texto).
 * - Escape cierra el modal visible.
 */
(function (global) {
  function bindBackdrop(bg) {
    if (!bg || bg.dataset.modalBound) return;
    bg.dataset.modalBound = "1";
    bg.addEventListener("mousedown", function (e) {
      bg.dataset.closeIntent = e.target === bg ? "1" : "0";
    });
    bg.addEventListener("click", function (e) {
      if (e.target !== bg) return;
      if (bg.dataset.closeIntent !== "1") return;
      // Si hay selección de texto, no cerrar
      var sel = window.getSelection && window.getSelection();
      if (sel && String(sel).length > 0) return;
      bg.hidden = true;
    });
    // Evitar que mousedown dentro del panel burbujee como intención de cierre
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
    document.querySelectorAll(".modal-backdrop:not([hidden])").forEach(function (m) {
      m.hidden = true;
    });
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindAll);
  } else {
    bindAll();
  }

  // Por si se inyectan modales después
  global.FajosModal = { bindAll: bindAll, bindBackdrop: bindBackdrop };
})(window);
