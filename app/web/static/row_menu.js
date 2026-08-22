/**
 * Menú de fila compacto.
 * - No se cierra en el mismo clic que lo abre (closest .row-menu).
 * - Escape y clic fuera lo cierran.
 */
(function (global) {
  function closeAll() {
    document.querySelectorAll(".row-menu.open").forEach(function (m) {
      m.classList.remove("open");
      var p = m.querySelector(".row-menu-panel");
      if (p) {
        p.hidden = true;
        p.setAttribute("aria-hidden", "true");
      }
      var b = m.querySelector(".btn-row-menu");
      if (b) b.setAttribute("aria-expanded", "false");
    });
  }

  function toggle(btn, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!btn) return;
    var menu = btn.closest(".row-menu");
    if (!menu) return;
    var wasOpen = menu.classList.contains("open");
    closeAll();
    if (wasOpen) return;
    menu.classList.add("open");
    var p = menu.querySelector(".row-menu-panel");
    if (p) {
      p.hidden = false;
      p.removeAttribute("hidden");
      p.setAttribute("aria-hidden", "false");
    }
    btn.setAttribute("aria-expanded", "true");
  }

  // Cerrar solo si el clic fue fuera de cualquier menú
  document.addEventListener("click", function (e) {
    if (e.target && e.target.closest && e.target.closest(".row-menu")) return;
    closeAll();
  }, true);

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  global.FajosRowMenu = { toggle: toggle, closeAll: closeAll };
})(window);
