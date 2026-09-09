/**
 * Modal de edición de fila completa (Plata / Pita / Taller).
 */
(function (global) {
  function openBackdrop(id) {
    const el = document.getElementById(id);
    if (el) el.hidden = false;
  }
  function closeBackdrop(id) {
    const el = document.getElementById(id);
    if (el) el.hidden = true;
  }

  function fillForm(form, data) {
    if (!form || !data) return;
    Object.keys(data).forEach(function (k) {
      const el = form.elements.namedItem(k);
      if (!el) return;
      if (el.type === "checkbox") {
        el.checked = !!(data[k] === true || data[k] === 1 || data[k] === "1");
      } else {
        el.value = data[k] == null ? "" : data[k];
      }
    });
  }

  async function submitRowEdit(opts) {
    const form = document.getElementById(opts.formId);
    if (!form) return false;
    const id = form.dataset.rowId;
    if (!id) return false;
    const body = new FormData(form);
    // checkbox firmado: si no está marcado no se envía
    if (form.elements.namedItem("firmado")) {
      body.set("firmado", form.elements.namedItem("firmado").checked ? "1" : "0");
    }
    const res = await fetch(opts.urlBase + id, { method: "PATCH", body });
    if (!res.ok) {
      let msg = "No se pudo guardar la fila";
      try {
        const j = await res.json();
        msg = j.detail || j.message || msg;
        if (Array.isArray(msg)) msg = msg.map(function (d) { return d.msg || d; }).join("; ");
      } catch (e) {}
      alert(msg);
      return false;
    }
    closeBackdrop(opts.modalId);
    try { document.dispatchEvent(new CustomEvent('fajos:row-saved', { detail: data || {} })); } catch(e) {} location.reload();
    return false;
  }

  function openRowEdit(opts) {
    const form = document.getElementById(opts.formId);
    if (!form) return;
    form.dataset.rowId = String(opts.id);
    fillForm(form, opts.data || {});
    const title = document.querySelector("#" + opts.modalId + " h2");
    if (title && opts.title) title.textContent = opts.title;
    openBackdrop(opts.modalId);
  }

  global.FajosRowEdit = {
    open: openRowEdit,
    submit: submitRowEdit,
    close: closeBackdrop,
  };
})(window);
