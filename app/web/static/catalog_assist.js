/**
 * Catálogos como asistencia (no candado):
 * - datalist sugiere materiales/modelos de BD
 * - predicción: catálogo → historial material+modelo → historial material
 * - el usuario puede cambiar el precio en el mismo campo (marca userEdited)
 * - valor libre se guarda igual; opcional añadir al catálogo
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
      if (el.parentNode) el.parentNode.appendChild(hint);
    }
    hint.textContent = text || "";
    hint.className = "cat-hint" + (kind ? " cat-hint--" + kind : "");
    hint.hidden = !text;
  }

  function formOf(el) {
    return el.form || el.closest("form") || el.closest(".modal") || document;
  }

  function tarifaField(form) {
    return form.querySelector
      ? form.querySelector('[name="tarifa_gr"]')
      : (form.elements && form.elements.namedItem("tarifa_gr"));
  }

  function materialField(form) {
    return form.querySelector
      ? form.querySelector('[name="material"]')
      : (form.elements && form.elements.namedItem("material"));
  }

  function modeloField(form) {
    return form.querySelector
      ? form.querySelector('[name="modelo"]')
      : (form.elements && form.elements.namedItem("modelo"));
  }

  function applyTarifa(t, price, force) {
    if (!t || price == null || price === "") return;
    var empty = String(t.value || "").trim() === "";
    if (force || empty || t.dataset.userEdited !== "1") {
      t.value = price;
      t.dataset.predicted = "1";
    }
  }

  var _suggestTimer = null;
  function suggestFromServer(form, matEl) {
    var mat = materialField(form);
    var mod = modeloField(form);
    var t = tarifaField(form);
    var material = mat ? String(mat.value || "").trim() : "";
    var modelo = mod ? String(mod.value || "").trim() : "";
    if (!material) {
      setHint(matEl || mat, "", "");
      return;
    }
    clearTimeout(_suggestTimer);
    _suggestTimer = setTimeout(function () {
      var url = "/api/catalogos/sugerir-tarifa?material=" + encodeURIComponent(material) +
        (modelo ? "&modelo=" + encodeURIComponent(modelo) : "");
      fetch(url, { credentials: "same-origin" })
        .then(function (r) { return r.json(); })
        .then(function (d) {
          if (!d || !d.ok || d.tarifa_gr == null) {
            // fallback local catalog map
            var map = tariffs();
            var k = findKey(map, material);
            if (k != null && map[k] != null && map[k] !== "") {
              applyTarifa(t, map[k], false);
              setHint(matEl || mat, "Catálogo · $" + map[k] + "/g (editable)", "ok");
            } else {
              setHint(matEl || mat, "Sin precio predicho · escribe $/g manualmente", "warn");
            }
            return;
          }
          applyTarifa(t, d.tarifa_gr, false);
          var src = d.fuente || "prediccion";
          var msg = (d.detalle || ("Sugerido $" + d.tarifa_gr + "/g")) + " · " + src;
          if (t && t.dataset.userEdited === "1" && String(t.value) !== String(d.tarifa_gr)) {
            msg += " (tú pusiste $" + t.value + ")";
          }
          setHint(matEl || mat, msg + " — editable", src === "catalogo" ? "ok" : "info");
        })
        .catch(function () {
          var map = tariffs();
          var k = findKey(map, material);
          if (k != null) applyTarifa(t, map[k], false);
        });
    }, 220);
  }

  function onMaterialInput(el) {
    if (!el) return;
    var form = formOf(el);
    var key = String(el.value || "").trim();
    if (!key) {
      setHint(el, "", "");
      el.dataset.fromCatalog = "0";
      return;
    }
    var map = tariffs();
    var k = findKey(map, key);
    el.dataset.fromCatalog = k ? "1" : "0";
    suggestFromServer(form, el);
  }

  function onModeloInput(el) {
    if (!el) return;
    var form = formOf(el);
    var mat = materialField(form);
    if (mat && String(mat.value || "").trim()) {
      suggestFromServer(form, mat);
    }
  }

  function markUserEditedTarifa(el) {
    if (!el) return;
    el.dataset.userEdited = "1";
    el.dataset.predicted = "0";
  }

  function bindForm(root) {
    root = root || document;
    root.querySelectorAll('[name="material"]').forEach(function (el) {
      if (el.dataset.catBound) return;
      el.dataset.catBound = "1";
      el.addEventListener("input", function () { onMaterialInput(el); });
      el.addEventListener("change", function () { onMaterialInput(el); });
    });
    root.querySelectorAll('[name="modelo"]').forEach(function (el) {
      if (el.dataset.catBound) return;
      el.dataset.catBound = "1";
      el.addEventListener("input", function () { onModeloInput(el); });
      el.addEventListener("change", function () { onModeloInput(el); });
    });
    root.querySelectorAll('[name="tarifa_gr"]').forEach(function (el) {
      if (el.dataset.catBound) return;
      el.dataset.catBound = "1";
      el.addEventListener("input", function () { markUserEditedTarifa(el); });
      el.addEventListener("change", function () { markUserEditedTarifa(el); });
    });
  }

  function init() {
    bindForm(document);
    // Observer for dynamically added rows/modals
    try {
      var obs = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          m.addedNodes && m.addedNodes.forEach(function (n) {
            if (n.nodeType === 1) bindForm(n);
          });
        });
      });
      obs.observe(document.body, { childList: true, subtree: true });
    } catch (e) {}
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  global.FajosCatalogAssist = {
    bind: bindForm,
    suggest: suggestFromServer,
    onMaterial: onMaterialInput,
  };
})(window);
