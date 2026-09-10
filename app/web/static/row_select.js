/**
 * Selección de filas Plata + acciones en lote + meta de folio.
 */
(function (global) {
  "use strict";

  function toast(msg, err) {
    if (typeof global.showToast === "function") global.showToast(msg, !!err);
    else if (err) console.error(msg);
    else console.log(msg);
  }

  function toggleSelAll(master) {
    var on = !!(master && master.checked);
    document.querySelectorAll("input.row-sel").forEach(function (c) {
      var tr = c.closest("tr");
      if (tr && tr.style.display === "none") return;
      c.checked = on;
    });
    updateSelUI();
  }

  function selectedProdIds() {
    return Array.prototype.slice
      .call(document.querySelectorAll("input.row-sel:checked"))
      .map(function (c) { return parseInt(c.value, 10); })
      .filter(function (n) { return n > 0; });
  }

  function updateSelUI() {
    var n = selectedProdIds().length;
    var countEl = document.getElementById("sel-count");
    var bar = document.getElementById("sel-actions-bar");
    var btn = document.getElementById("btn-sel-acciones");
    if (countEl) countEl.textContent = n ? (n + " seleccionada" + (n === 1 ? "" : "s")) : "";
    if (bar) bar.hidden = n === 0;
    if (btn) {
      btn.disabled = n === 0;
      btn.setAttribute("aria-disabled", n === 0 ? "true" : "false");
    }
    var master = document.getElementById("sel-all-folios");
    if (master) {
      var visible = Array.prototype.slice.call(document.querySelectorAll("input.row-sel")).filter(function (c) {
        var tr = c.closest("tr");
        return !(tr && tr.style.display === "none");
      });
      var checked = visible.filter(function (c) { return c.checked; });
      master.checked = visible.length > 0 && checked.length === visible.length;
      master.indeterminate = checked.length > 0 && checked.length < visible.length;
    }
  }

  function closeAccionesMenu() {
    var panel = document.getElementById("sel-acciones-panel");
    if (panel) panel.hidden = true;
    var btn = document.getElementById("btn-sel-acciones");
    if (btn) btn.setAttribute("aria-expanded", "false");
  }

  function toggleAccionesMenu(ev) {
    if (ev) {
      ev.preventDefault();
      ev.stopPropagation();
    }
    var ids = selectedProdIds();
    if (!ids.length) {
      toast("Selecciona al menos una fila", true);
      return;
    }
    var panel = document.getElementById("sel-acciones-panel");
    var btn = document.getElementById("btn-sel-acciones");
    if (!panel) return;
    var open = panel.hidden;
    panel.hidden = !open;
    if (btn) btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  async function cerrarFoliosSeleccionados() {
    closeAccionesMenu();
    var ids = selectedProdIds();
    if (!ids.length) {
      toast("Selecciona al menos una fila", true);
      return;
    }
    if (!global.confirm(
      "¿Cerrar " + ids.length + " folio(s) seleccionado(s)?\n" +
      "Solo se cierran si llevan 2+ semanas sin avance."
    )) return;
    var fd = new FormData();
    if (global.SEMANA_ID) fd.set("semana_id", String(global.SEMANA_ID));
    fd.set("min_semanas", "2");
    ids.forEach(function (id) { fd.append("prod_ids", String(id)); });
    try {
      var res = await fetch("/api/produccion/terminar-lote", {
        method: "POST",
        body: fd,
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      });
      var data = await res.json().catch(function () { return {}; });
      if (!res.ok || data.ok === false) {
        toast(data.error || "Error al cerrar", true);
        return;
      }
      toast(
        "Cerrados: " + (data.terminados || 0) +
        (data.fallidos ? " · omitidos: " + data.fallidos : "")
      );
      setTimeout(function () { location.reload(); }, 500);
    } catch (e) {
      toast("Error de red", true);
    }
  }

  async function duplicarSeleccionadosEnDOL() {
    closeAccionesMenu();
    var ids = selectedProdIds();
    if (!ids.length) {
      toast("Selecciona al menos una fila", true);
      return;
    }
    if (!global.confirm(
      "¿Duplicar " + ids.length + " fila(s) en material DOL?\n\n" +
      "• Mismo trabajador, folio y modelo\n" +
      "• Gramos en blanco\n" +
      "• Si ya existía en DOL, se reutiliza"
    )) return;
    var ok = 0, fail = 0, reused = 0;
    toast("Duplicando…");
    for (var i = 0; i < ids.length; i++) {
      try {
        var fd = new FormData();
        fd.set("material", "DOL");
        var res = await fetch("/api/produccion/linea/" + ids[i] + "/duplicar", {
          method: "POST",
          body: fd,
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        var data = await res.json().catch(function () { return {}; });
        if (res.ok && data.ok !== false) {
          ok++;
          if (data.reused) reused++;
        } else {
          fail++;
        }
      } catch (e) {
        fail++;
      }
    }
    toast(
      "DOL: " + ok + " ok" +
      (reused ? (" (" + reused + " reutilizadas)") : "") +
      (fail ? (" · " + fail + " fallidas") : "")
    );
    setTimeout(function () { location.reload(); }, 600);
  }

  function limpiarSeleccion() {
    closeAccionesMenu();
    document.querySelectorAll("input.row-sel").forEach(function (c) { c.checked = false; });
    var master = document.getElementById("sel-all-folios");
    if (master) {
      master.checked = false;
      master.indeterminate = false;
    }
    updateSelUI();
  }

  async function sugerirFolioMeta(el) {
    if (!el) return;
    var folio = String(el.value || "").trim();
    var hint = document.getElementById("linea-folio-hint");
    if (!folio) {
      if (hint) hint.textContent = "";
      return;
    }
    try {
      var url = "/api/produccion/folio-meta?folio=" + encodeURIComponent(folio);
      if (global.SEMANA_ID) url += "&semana_id=" + global.SEMANA_ID;
      var res = await fetch(url, { credentials: "same-origin" });
      var data = await res.json().catch(function () { return {}; });
      if (!data.ok) return;
      var form = el.form || document.getElementById("form-linea");
      if (!form) return;
      if (data.modelo && form.modelo && !String(form.modelo.value || "").trim())
        form.modelo.value = data.modelo;
      if (data.material && form.material) {
        form.material.value = data.material;
        if (global.CatalogAssist) global.CatalogAssist.onMaterialInput(form.material);
      }
      if (data.tarifa_gr != null && form.tarifa_gr && form.tarifa_gr.dataset.userEdited !== "1")
        form.tarifa_gr.value = data.tarifa_gr;
      if (hint) {
        hint.textContent =
          "Folio conocido: " +
          (data.modelo || "—") + " · " +
          (data.material || "—") + " · $" +
          (data.tarifa_gr != null ? data.tarifa_gr : "—");
      }
    } catch (e) {}
  }

  // Cerrar menú al clic fuera
  document.addEventListener("click", function (ev) {
    var panel = document.getElementById("sel-acciones-panel");
    if (!panel || panel.hidden) return;
    var wrap = document.getElementById("sel-acciones-wrap");
    if (wrap && wrap.contains(ev.target)) return;
    closeAccionesMenu();
  });

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("input.row-sel").forEach(function (c) {
      c.addEventListener("change", updateSelUI);
    });
    var master = document.getElementById("sel-all-folios");
    if (master) master.addEventListener("change", function () { updateSelUI(); });
    updateSelUI();
  });

  global.toggleSelAll = toggleSelAll;
  global.selectedProdIds = selectedProdIds;
  global.cerrarFoliosSeleccionados = cerrarFoliosSeleccionados;
  global.duplicarSeleccionadosEnDOL = duplicarSeleccionadosEnDOL;
  global.limpiarSeleccion = limpiarSeleccion;
  global.toggleAccionesMenu = toggleAccionesMenu;
  global.updateSelUI = updateSelUI;
  global.sugerirFolioMeta = sugerirFolioMeta;
})(window);
