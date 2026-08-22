/**
 * Menú ⋮ compacto por fila + cierre al clic fuera / Escape.
 */
(function (global) {
  function closeAll() {
    document.querySelectorAll(".row-menu.open").forEach(function (m) {
      m.classList.remove("open");
      const p = m.querySelector(".row-menu-panel");
      if (p) p.hidden = true;
    });
  }

  function toggle(btn, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const menu = btn.closest(".row-menu");
    if (!menu) return;
    const wasOpen = menu.classList.contains("open");
    closeAll();
    if (!wasOpen) {
      menu.classList.add("open");
      const p = menu.querySelector(".row-menu-panel");
      if (p) p.hidden = false;
    }
  }

  document.addEventListener("click", function () {
    closeAll();
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  global.FajosRowMenu = { toggle: toggle, closeAll: closeAll };
})(window);
