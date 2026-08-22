/**
 * Menú de fila — panel en document.body (position:fixed)
 * para no quedar recortado por overflow de .table-wrap.
 */
(function (global) {
  var activeMenu = null;
  var activeBtn = null;
  var portal = null;

  function ensurePortal() {
    if (portal && document.body.contains(portal)) return portal;
    portal = document.createElement("div");
    portal.id = "fajos-row-menu-portal";
    portal.className = "row-menu-portal";
    portal.hidden = true;
    document.body.appendChild(portal);
    portal.addEventListener("click", function (e) {
      e.stopPropagation();
    });
    return portal;
  }

  function closeAll() {
    if (portal) {
      portal.hidden = true;
      portal.innerHTML = "";
    }
    document.querySelectorAll(".row-menu.open").forEach(function (m) {
      m.classList.remove("open");
    });
    if (activeBtn) {
      activeBtn.setAttribute("aria-expanded", "false");
    }
    activeMenu = null;
    activeBtn = null;
  }

  function placePortal(btn) {
    var p = ensurePortal();
    var rect = btn.getBoundingClientRect();
    // Preferir abrir hacia abajo-derecha; si no cabe, hacia arriba
    var top = rect.bottom + 4;
    var left = rect.left;
    p.hidden = false;
    // medir después de mostrar
    var ph = p.offsetHeight || 120;
    var pw = p.offsetWidth || 160;
    if (top + ph > window.innerHeight - 8) {
      top = Math.max(8, rect.top - ph - 4);
    }
    if (left + pw > window.innerWidth - 8) {
      left = Math.max(8, window.innerWidth - pw - 8);
    }
    p.style.top = Math.round(top) + "px";
    p.style.left = Math.round(left) + "px";
  }

  function toggle(btn, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!btn) return;

    // Si ya estaba abierto este botón → cerrar
    if (activeBtn === btn && portal && !portal.hidden) {
      closeAll();
      return;
    }

    closeAll();

    var menu = btn.closest(".row-menu");
    var sourcePanel = menu && menu.querySelector(".row-menu-panel");
    if (!sourcePanel) return;

    activeBtn = btn;
    activeMenu = menu;
    if (menu) menu.classList.add("open");
    btn.setAttribute("aria-expanded", "true");

    var p = ensurePortal();
    // Clonar acciones al portal
    p.innerHTML = "";
    var box = document.createElement("div");
    box.className = "row-menu-portal-inner";
    sourcePanel.querySelectorAll("button").forEach(function (srcBtn) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = srcBtn.className;
      b.textContent = srcBtn.textContent;
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        closeAll();
        // Ejecutar la acción original
        srcBtn.click();
      });
      box.appendChild(b);
    });
    p.appendChild(box);
    p.hidden = false;
    placePortal(btn);
  }

  document.addEventListener(
    "click",
    function (e) {
      if (e.target && e.target.closest) {
        if (e.target.closest(".row-menu") || e.target.closest("#fajos-row-menu-portal")) {
          return;
        }
      }
      closeAll();
    },
    true
  );

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  window.addEventListener(
    "scroll",
    function () {
      if (activeBtn && portal && !portal.hidden) placePortal(activeBtn);
    },
    true
  );
  window.addEventListener("resize", function () {
    if (activeBtn && portal && !portal.hidden) placePortal(activeBtn);
  });

  global.FajosRowMenu = { toggle: toggle, closeAll: closeAll };
})(window);
