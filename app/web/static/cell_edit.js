/**
 * Edición inline con confirmación (doble clic o botón ✎).
 * - Quita/pone el atributo HTML readonly (no solo la propiedad).
 * - Evita carrera blur↔confirm del diálogo nativo.
 * - Escape restaura valor original.
 */
(function (global) {
  function toast(msg, err) {
    if (window.FajosLive && FajosLive.showToast) return FajosLive.showToast(msg, err);
    if (err) console.warn(msg);
    else if (typeof msg === "string" && msg) {
      try { console.info(msg); } catch (e) {}
    }
  }

  function lock(inp) {
    inp.readOnly = true;
    inp.setAttribute("readonly", "readonly");
    inp.classList.remove("is-editing");
    inp.removeAttribute("data-editing");
  }

  function unlock(inp) {
    inp.readOnly = false;
    inp.removeAttribute("readonly");
    inp.classList.add("is-editing");
    inp.setAttribute("data-editing", "1");
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
        if (Array.isArray(detail)) {
          detail = detail.map(function (d) { return d.msg || JSON.stringify(d); }).join("; ");
        }
      } catch (e) {}
      toast(detail, true);
      alert(detail);
      return false;
    }
    toast("Guardado");
    return true;
  }

  function beginEdit(inp) {
    if (!inp || inp.getAttribute("data-editing") === "1") return;
    if (!confirm("¿Editar este campo?")) return;
    inp.dataset.orig = inp.value;
    unlock(inp);
    // Tras confirm() el foco es inestable: diferir focus/select
    setTimeout(function () {
      try {
        inp.focus();
        if (typeof inp.select === "function") inp.select();
      } catch (e) {}
    }, 30);
  }

  function bindCellEdits(options) {
    const urlFor = options.urlFor;
    const onSaved = options.onSaved || function () {};
    const selector = options.selector || "input.cell-edit";

    document.querySelectorAll(selector).forEach(function (inp) {
      if (inp.dataset.boundEdit === "1") return;
      inp.dataset.boundEdit = "1";
      // Estado inicial forzado
      lock(inp);

      inp.addEventListener("dblclick", function (e) {
        e.preventDefault();
        e.stopPropagation();
        beginEdit(inp);
      });

      // Clic en el icono ✎ (si existe en la celda)
      const td = inp.closest("td");
      if (td && !td.querySelector(".btn-edit-cell")) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-edit-cell";
        btn.title = "Editar";
        btn.setAttribute("aria-label", "Editar");
        btn.textContent = "✎";
        btn.addEventListener("click", function (e) {
          e.preventDefault();
          e.stopPropagation();
          beginEdit(inp);
        });
        td.classList.add("cell-with-edit");
        td.appendChild(btn);
      }

      inp.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          inp.blur();
        }
        if (e.key === "Escape") {
          e.preventDefault();
          if (inp.dataset.orig != null) inp.value = inp.dataset.orig;
          lock(inp);
        }
      });

      inp.addEventListener("blur", async function () {
        // Solo guardar si estábamos en modo edición
        if (inp.getAttribute("data-editing") !== "1") return;
        const tr = inp.closest("tr");
        const id = tr && tr.dataset.id;
        const field = inp.dataset.field;
        if (!id || !field) {
          lock(inp);
          return;
        }
        if (inp.dataset.orig != null && String(inp.value) === String(inp.dataset.orig)) {
          lock(inp);
          return;
        }
        const ok = await patchField(urlFor(id), field, inp.value);
        lock(inp);
        if (!ok && inp.dataset.orig != null) {
          inp.value = inp.dataset.orig;
        } else if (ok) {
          inp.dataset.orig = inp.value;
          onSaved(id, field, inp.value, tr);
        }
      });
    });
  }

  global.FajosCellEdit = {
    bindCellEdits: bindCellEdits,
    patchField: patchField,
    beginEdit: beginEdit,
  };
})(window);
