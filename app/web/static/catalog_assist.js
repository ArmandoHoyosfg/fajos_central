/**
 * Catálogos como asistencia (no candado):
 * - datalist sugiere materiales/modelos de BD
 * - si coincide → aplica tarifa / material por defecto
 * - si no coincide → valor libre, se guarda en la nómina igual
 * - opcional: añadir el valor libre al catálogo
 */
(function (global) {
  "use strict";

  function tariffs() {
    try {
      return JSON.parse((document.getElementById("catalog-tarifas") || {}).textContent || "{}");
    } catch (e) {
      return {};
    }
  }
  function models() {
    try {
      return JSON.parse((document.getElementById("catalog-modelos") || {}).textContent || "{}");
    } catch (e) {
      return {};
    }
  }

  function findKey(map, key) {
    if (!key) return null;
    if (map[key] != null) return key;
    var low = String(key).toLowerCase();
    for (var k of Object.keys(map)) {
      if (k.toLowerCase() === low) return k;
    }
    return null;
  }

  function setHint(el, text, kind) {
    if (!el) return;
    var id = el.getAttribute("data-hint-id");
    var hint = id ? document.getElementById(id) : null;
    if (!hint) {
      hint = document.createElement("div");
      hint.className = "cat-hint";
      hint.id = "hint-" + Math.random().toString(36).slice(2, 9);
      el.setAttribute("data-hint-id", hint.id);
      el.parentNode.appendChild(hint);
    }
    hint.textContent = text || "";
    hint.className = "cat-hint" + (kind ? " cat-hint--" + kind : "");
    hint.hidden = !text;
  }

  function formOf(el) {
    return el.form || el.closest("form") || el.closest(".modal") || document;
  }

  function onMaterialInput(el) {
    if (!el) return;
    var form = formOf(el);
    var key = String(el.value || "").trim();
    var map = tariffs();
    var t = form.querySelector
      ? form.querySelector('[name="tarifa_gr"]')
      : (form.elements && form.elements.namedItem("tarifa_gr"));
    if (!key) {
      setHint(el, "", "");
      el.dataset.fromCatalog = "0";
      return;
    }
    var k = findKey(map, key);
    if (k != null && map[k] != null && map[k] !== "") {
      el.dataset.fromCatalog = "1";
      if (t && t.dataset.userEdited !== "1") {
        t.value = map[k];
      }
      setHint(el, "Catálogo · $" + map[k] + "/g", "ok");
    } else {
      el.dataset.fromCatalog = "0";
      setHint(el, "Valor libre (no está en catálogo)", "free");
    }
  }

  function onModeloInput(el) {
    if (!el) return;
    var form = formOf(el);
    var key = String(el.value || "").trim();
    var map = models();
    if (!key) {
      setHint(el, "", "");
      return;
    }
    var k = findKey(map, key);
    if (k == null) {
      setHint(el, "Modelo libre (no está en catálogo)", "free");
      return;
    }
    var info = map[k] || {};
    setHint(el, "Catálogo" + (info.material ? " · mat. " + info.material : ""), "ok");
    var mat = form.querySelector
      ? form.querySelector('[name="material"]')
      : (form.elements && form.elements.namedItem("material"));
    if (mat && info.material) {
      // solo sugiere si material vacío o venía del catálogo
      if (!String(mat.value || "").trim() || mat.dataset.fromCatalog === "1") {
        mat.value = info.material;
        onMaterialInput(mat);
      }
    }
    var t = form.querySelector
      ? form.querySelector('[name="tarifa_gr"]')
      : (form.elements && form.elements.namedItem("tarifa_gr"));
    if (t && info.tarifa != null && t.dataset.userEdited !== "1") {
      t.value = info.tarifa;
    }
  }

  function markTarifaEdited(el) {
    if (el) el.dataset.userEdited = "1";
  }

  function resetTarifaEdited(form) {
    var t = form && (form.querySelector('[name="tarifa_gr"]'));
    if (t) t.dataset.userEdited = "0";
  }

  /** Chips clicables bajo el input de material */
  function renderMaterialChips(container, input) {
    if (!container || !input) return;
    var map = tariffs();
    var keys = Object.keys(map).sort();
    if (!keys.length) {
      container.innerHTML = '<span class="muted" style="font-size:0.8rem">Sin materiales en catálogo. <a href="/catalogos">Gestionar</a></span>';
      return;
    }
    container.innerHTML = keys
      .map(function (k) {
        return (
          '<button type="button" class="cat-chip" data-mat="' +
          k.replace(/"/g, "&quot;") +
          '" title="$' +
          map[k] +
          '/g">' +
          k +
          "</button>"
        );
      })
      .join("") +
      ' <a class="cat-chip cat-chip-link" href="/catalogos" title="Abrir catálogos">⚙</a>';
    container.querySelectorAll(".cat-chip[data-mat]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        input.value = btn.getAttribute("data-mat") || "";
        onMaterialInput(input);
        input.dispatchEvent(new Event("change", { bubbles: true }));
      });
    });
  }

  async function saveMaterialToCatalog(material, tarifa) {
    var fd = new FormData();
    fd.append("material", material);
    fd.append("tarifa_por_gramo", String(tarifa));
    fd.append("activo", "1");
    var res = await fetch("/api/catalogos/material", { method: "POST", body: fd });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
    return data;
  }

  async function saveModeloToCatalog(modelo, material, tarifa) {
    var fd = new FormData();
    fd.append("modelo", modelo);
    fd.append("tipo", "PLT");
    if (material) fd.append("material_default", material);
    if (tarifa != null && tarifa !== "") fd.append("tarifa_default", String(tarifa));
    var res = await fetch("/api/catalogos/modelo", { method: "POST", body: fd });
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
    return data;
  }

  function wireForm(form) {
    if (!form || form.dataset.catalogWired) return;
    form.dataset.catalogWired = "1";
    var mat = form.querySelector('[name="material"]');
    var mod = form.querySelector('[name="modelo"]');
    var tar = form.querySelector('[name="tarifa_gr"]');
    if (mat) {
      mat.addEventListener("input", function () { onMaterialInput(mat); });
      mat.addEventListener("change", function () { onMaterialInput(mat); });
      var chips = form.querySelector(".mat-chips");
      if (chips) renderMaterialChips(chips, mat);
    }
    if (mod) {
      mod.addEventListener("input", function () { onModeloInput(mod); });
      mod.addEventListener("change", function () { onModeloInput(mod); });
    }
    if (tar) {
      tar.addEventListener("input", function () { markTarifaEdited(tar); });
    }
    var btnMat = form.querySelector(".btn-save-mat-cat");
    if (btnMat && mat) {
      btnMat.addEventListener("click", async function () {
        var m = String(mat.value || "").trim();
        var t = tar ? parseFloat(tar.value) : NaN;
        if (!m) { alert("Escribe un material"); return; }
        if (!(t >= 0)) { alert("Indica $/g para guardarlo en el catálogo"); return; }
        try {
          await saveMaterialToCatalog(m, t);
          // refresh local map
          var map = tariffs();
          map[m] = t;
          var el = document.getElementById("catalog-tarifas");
          if (el) el.textContent = JSON.stringify(map);
          var dl = document.getElementById("dl-materiales");
          if (dl && ![].some.call(dl.options, function (o) { return o.value === m; })) {
            var opt = document.createElement("option");
            opt.value = m;
            dl.appendChild(opt);
          }
          onMaterialInput(mat);
          if (global.FajosLive && FajosLive.showToast) FajosLive.showToast("Material guardado en catálogo");
          else alert("Material guardado en catálogo");
        } catch (e) {
          alert("No se pudo guardar: " + e.message);
        }
      });
    }
    var btnMod = form.querySelector(".btn-save-mod-cat");
    if (btnMod && mod) {
      btnMod.addEventListener("click", async function () {
        var m = String(mod.value || "").trim();
        if (!m) { alert("Escribe un modelo"); return; }
        var matV = mat ? String(mat.value || "").trim() : "";
        var t = tar ? parseFloat(tar.value) : null;
        try {
          await saveModeloToCatalog(m, matV, t);
          var map = models();
          map[m] = { material: matV, tarifa: t };
          var el = document.getElementById("catalog-modelos");
          if (el) el.textContent = JSON.stringify(map);
          var dl = document.getElementById("dl-modelos");
          if (dl && ![].some.call(dl.options, function (o) { return o.value === m; })) {
            var opt = document.createElement("option");
            opt.value = m;
            dl.appendChild(opt);
          }
          onModeloInput(mod);
          if (global.FajosLive && FajosLive.showToast) FajosLive.showToast("Modelo guardado en catálogo");
          else alert("Modelo guardado en catálogo");
        } catch (e) {
          alert("No se pudo guardar: " + e.message);
        }
      });
    }
  }

  function boot() {
    document.querySelectorAll("form").forEach(wireForm);
    // re-wire when modals open
    document.querySelectorAll(".modal, [id^='modal-']").forEach(function (m) {
      m.addEventListener("click", function () {
        var f = m.querySelector("form");
        if (f) wireForm(f);
      }, true);
    });
  }

  global.CatalogAssist = {
    onMaterialInput: onMaterialInput,
    onModeloInput: onModeloInput,
    wireForm: wireForm,
    tariffs: tariffs,
    models: models,
  };
  // Compat con handlers inline del HTML
  global.onMaterialInput = onMaterialInput;
  global.onModeloInput = onModeloInput;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})(window);
