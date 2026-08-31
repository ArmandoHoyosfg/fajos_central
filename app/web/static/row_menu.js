/**
 * Row menu (three dots) - portal to body so table overflow does not clip it.
 */
(function (global) {
  "use strict";

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
    if (activeBtn) activeBtn.setAttribute("aria-expanded", "false");
    activeBtn = null;
  }

  function placePortal(btn) {
    var p = ensurePortal();
    var rect = btn.getBoundingClientRect();
    p.hidden = false;
    var ph = p.offsetHeight || 140;
    var pw = p.offsetWidth || 180;
    var top = rect.bottom + 4;
    var left = rect.left;
    if (top + ph > window.innerHeight - 8) top = Math.max(8, rect.top - ph - 4);
    if (left + pw > window.innerWidth - 8) left = Math.max(8, window.innerWidth - pw - 8);
    p.style.top = Math.round(top) + "px";
    p.style.left = Math.round(left) + "px";
  }

  function toggle(btn, e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    if (!btn) return;
    if (activeBtn === btn && portal && !portal.hidden) {
      closeAll();
      return;
    }
    closeAll();

    var menu = btn.closest(".row-menu");
    var sourcePanel = menu && menu.querySelector(".row-menu-panel");
    if (!sourcePanel) {
      console.warn("[FajosRowMenu] panel not found");
      return;
    }

    activeBtn = btn;
    if (menu) menu.classList.add("open");
    btn.setAttribute("aria-expanded", "true");

    var p = ensurePortal();
    p.innerHTML = "";
    var box = document.createElement("div");
    box.className = "row-menu-portal-inner";

    sourcePanel.querySelectorAll("button").forEach(function (srcBtn) {
      var b = document.createElement("button");
      b.type = "button";
      b.className = srcBtn.className || "";
      b.textContent = (srcBtn.textContent || "").trim();
      // copy data-* for folio actions
      Array.prototype.forEach.call(srcBtn.attributes, function (attr) {
        if (attr.name.indexOf("data-") === 0) {
          b.setAttribute(attr.name, attr.value);
        }
      });
      b.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        closeAll();
        // Prefer data-action handlers; else native click on original
        if (srcBtn.getAttribute("data-action") === "terminar-folio" && global.marcarTerminado) {
          global.marcarTerminado(srcBtn.getAttribute("data-prod-id"), srcBtn.getAttribute("data-folio") || "");
          return;
        }
        try {
          srcBtn.click();
        } catch (err) {
          console.error(err);
        }
      });
      box.appendChild(b);
    });
    p.appendChild(box);
    p.hidden = false;
    placePortal(btn);
  }

  // Event delegation for the dots button (works even if onclick is broken)
  document.addEventListener(
    "click",
    function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      var btn = t.closest(".btn-row-menu, [data-action='row-menu-toggle']");
      if (btn) {
        e.preventDefault();
        e.stopPropagation();
        toggle(btn, e);
        return;
      }
      // outside click closes (bubble phase so toggle can run first)
      if (portal && !portal.hidden) {
        if (t.closest("#fajos-row-menu-portal") || t.closest(".row-menu")) return;
        closeAll();
      }
    },
    false
  );

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });

  global.FajosRowMenu = { toggle: toggle, closeAll: closeAll };
})(window);
