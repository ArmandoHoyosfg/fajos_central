/**
 * Selección de filas Plata + cierre por lote + meta de folio.
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
  }

  function selectedProdIds() {
    return Array.prototype.slice
      .call(document.querySelectorAll("input.row-sel:checked"))
      .map(function (c) { return parseInt(c.value, 10); })
      .filter(function (n) { return n > 0; });
  }

  async function cerrarFoliosSeleccionados() {
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

  global.toggleSelAll = toggleSelAll;
  global.selectedProdIds = selectedProdIds;
  global.cerrarFoliosSeleccionados = cerrarFoliosSeleccionados;
  global.sugerirFolioMeta = sugerirFolioMeta;
})(window);
