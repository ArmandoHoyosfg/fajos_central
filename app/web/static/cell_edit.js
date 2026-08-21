/**
 * Edición inline con confirmación (doble clic).
 * Restaura valor original con Escape.
 */
(function (global) {
  function toast(msg, err) {
    if (window.FajosLive && FajosLive.showToast) return FajosLive.showToast(msg, err);
    if (err) console.warn(msg);
  }

  async function patchField(url, field, value) {
    const body = new FormData();
    body.set(field, value == null ? "" : String(value));
    const res = await fetch(url, { method: "PATCH", body });
    if (!res.ok) {
      let detail = "No se pudo guardar";
      try {
        const j = await res.json();
        detail = j.detail || j.message || detail;
        if (Array.isArray(detail)) detail = detail.map(function (d) { return d.msg || d; }).join("; ");
      } catch (e) {}
      toast(detail, true);
      return false;
    }
    toast("Guardado");
    return true;
  }

  function bindCellEdits(options) {
    const urlFor = options.urlFor; // (id) => url
    const onSaved = options.onSaved || function () {};
    document.querySelectorAll(options.selector || "input.cell-edit").forEach(function (inp) {
      if (inp.dataset.boundEdit) return;
      inp.dataset.boundEdit = "1";
      inp.addEventListener("dblclick", function () {
        if (!inp.readOnly) return;
        if (!confirm("¿Editar este campo?")) return;
        inp.dataset.orig = inp.value;
        inp.readOnly = false;
        inp.focus();
        try { inp.select(); } catch (e) {}
      });
      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          inp.blur();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          if (inp.dataset.orig != null) inp.value = inp.dataset.orig;
          inp.readOnly = true;
          inp.blur();
        }
      });
      inp.addEventListener("blur", async function () {
        if (inp.readOnly) return;
        const tr = inp.closest("tr");
        const id = tr && tr.dataset.id;
        const field = inp.dataset.field;
        if (!id || !field) {
          inp.readOnly = true;
          return;
        }
        // sin cambios → no llamar API
        if (inp.dataset.orig != null && String(inp.value) === String(inp.dataset.orig)) {
          inp.readOnly = true;
          return;
        }
        const ok = await patchField(urlFor(id), field, inp.value);
        inp.readOnly = true;
        if (!ok && inp.dataset.orig != null) {
          inp.value = inp.dataset.orig;
        } else if (ok) {
          inp.dataset.orig = inp.value;
          onSaved(id, field, inp.value, tr);
        }
      });
    });
  }

  global.FajosCellEdit = { bindCellEdits: bindCellEdits, patchField: patchField };
})(window);
