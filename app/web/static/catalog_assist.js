/**
 * Catálogos como asistencia (no candado):
 * - datalist sugiere materiales/modelos de BD
 * - predicción: catálogo → historial material+modelo → historial material
 * - el usuario puede cambiar el precio en el mismo campo (marca userEdited)
 * - valor libre se guarda igual; botones ＋ Material/Modelo al catálogo
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

  function toast(msg, err) {
    if (global.FajosLive && FajosLive.showToast) {
      FajosLive.showToast(msg, !!err);
      return;
    }
    if (typeof global.showToast === "function") {
      global.showToast(msg, !!err);
      return;
    }
    var el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast-web";
      document.body.appendChild(el);
    }
    el.hidden = false;
    el.textContent = msg;
    el.className = "toast-web" + (err ? " err" : " ok");
    clearTimeout(global._toastT);
    global._toastT = setTimeout(function () { el.hidden = true; }, err ? 5000 : 2800);
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
            var map = tariffs();
            var k = findKey(map, material);
            if (k != null && map[k] != null && map[k] !== "") {
              applyTarifa(t, map[k], false);
              setHint(matEl || mat, "Catálogo · $" + map[k] + "/g (editable)", "ok");
            } else {
              setHint(matEl || mat, "No está en catálogo · escribe $/g o usa «＋ Material al catálogo»", "warn");
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
          else setHint(matEl || mat, "No se pudo consultar el catálogo", "warn");
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
    if (!k) {
      setHint(el, "No está en catálogo · puedes usarlo libre o pulsar «＋ Material al catálogo»", "warn");
    }
    suggestFromServer(form, el);
  }

  function onModeloInput(el) {
    if (!el) return;
    var form = formOf(el);
    var key = String(el.value || "").trim();
    if (!key) {
      setHint(el, "", "");
      el.dataset.fromCatalog = "0";
      return;
    }
    var map = models();
    // models map can be { "FLORES": {...} } or { "FLORES": "PLT" }
    var k = findKey(map, key);
    // also match by scanning values if map is array-like object of names
    if (!k) {
      for (var mk of Object.keys(map)) {
        if (String(mk).toLowerCase() === key.toLowerCase()) {
          k = mk;
          break;
        }
        var v = map[mk];
        if (v && typeof v === "object" && String(v.modelo || "").toLowerCase() === key.toLowerCase()) {
          k = mk;
          break;
        }
      }
    }
    el.dataset.fromCatalog = k ? "1" : "0";
    if (k) {
      setHint(el, "Modelo en catálogo", "ok");
    } else {
      setHint(el, "No está en catálogo · puedes usarlo libre o pulsar «＋ Modelo al catálogo»", "warn");
    }
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

  /** Guarda el modelo del input cercano al botón en /api/catalogos/modelo */
  function saveModeloFromButton(btn) {
    var form = formOf(btn);
    var modEl = modeloField(form);
    var modelo = modEl ? String(modEl.value || "").trim() : "";
    if (!modelo) {
      toast("Escribe un modelo antes de añadirlo al catálogo", true);
      if (modEl) {
        setHint(modEl, "Escribe el nombre del modelo", "warn");
        modEl.focus();
      }
      return;
    }
    var matEl = materialField(form);
    var tarEl = tarifaField(form);
    var material = matEl ? String(matEl.value || "").trim() : "";
    var tarifa = tarEl ? String(tarEl.value || "").trim() : "";
    var fd = new FormData();
    fd.append("modelo", modelo);
    fd.append("tipo", "PLT");
    if (material) fd.append("material_default", material);
    if (tarifa !== "" && !isNaN(parseFloat(tarifa))) fd.append("tarifa_default", tarifa);

    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = "Guardando…";
    fetch("/api/catalogos/modelo", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (d) {
          return { okHttp: r.ok, d: d };
        });
      })
      .then(function (res) {
        var d = res.d || {};
        if (!res.okHttp || d.ok === false) {
          var err = d.error || d.detail || d.message || "No se pudo guardar el modelo";
          toast(err, true);
          setHint(modEl, err, "warn");
          return;
        }
        toast("Modelo «" + modelo.toUpperCase() + "» guardado en catálogo");
        setHint(modEl, "Guardado en catálogo", "ok");
        if (modEl) modEl.dataset.fromCatalog = "1";
        // refrescar mapa local de modelos si existe el script JSON
        try {
          var el = document.getElementById("catalog-modelos");
          if (el) {
            var map = models();
            map[modelo.toUpperCase()] = {
              modelo: modelo.toUpperCase(),
              tipo: "PLT",
              material_default: material || null,
              tarifa_default: tarifa ? parseFloat(tarifa) : null,
            };
            el.textContent = JSON.stringify(map);
          }
          // añadir a datalist si existe
          var dl = document.getElementById("dl-modelos");
          if (dl) {
            var exists = false;
            dl.querySelectorAll("option").forEach(function (o) {
              if (String(o.value).toUpperCase() === modelo.toUpperCase()) exists = true;
            });
            if (!exists) {
              var opt = document.createElement("option");
              opt.value = modelo.toUpperCase();
              dl.appendChild(opt);
            }
          }
        } catch (e) { /* ignore */ }
      })
      .catch(function (e) {
        toast("Error de red al guardar modelo", true);
        setHint(modEl, "Error de red", "warn");
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = prev;
      });
  }

  /** Guarda material + tarifa en catálogo */
  function saveMaterialFromButton(btn) {
    var form = formOf(btn);
    var matEl = materialField(form);
    var material = matEl ? String(matEl.value || "").trim() : "";
    if (!material) {
      toast("Escribe un material antes de añadirlo al catálogo", true);
      if (matEl) {
        setHint(matEl, "Escribe el material (ej. AG3)", "warn");
        matEl.focus();
      }
      return;
    }
    var tarEl = tarifaField(form);
    var tarifa = tarEl ? String(tarEl.value || "").trim() : "";
    if (tarifa === "" || isNaN(parseFloat(tarifa))) {
      toast("Indica un precio $/g para guardarlo en el catálogo", true);
      if (tarEl) tarEl.focus();
      return;
    }
    var fd = new FormData();
    fd.append("material", material);
    fd.append("tarifa_por_gramo", tarifa);
    fd.append("activo", "1");

    btn.disabled = true;
    var prev = btn.textContent;
    btn.textContent = "Guardando…";
    fetch("/api/catalogos/material", { method: "POST", body: fd, credentials: "same-origin" })
      .then(function (r) {
        return r.json().then(function (d) {
          return { okHttp: r.ok, d: d };
        });
      })
      .then(function (res) {
        var d = res.d || {};
        if (!res.okHttp || d.ok === false) {
          var err = d.error || d.detail || d.message || "No se pudo guardar el material";
          toast(err, true);
          setHint(matEl, err, "warn");
          return;
        }
        toast("Material «" + material.toUpperCase() + "» a $" + tarifa + "/g en catálogo");
        setHint(matEl, "Catálogo · $" + tarifa + "/g", "ok");
        if (matEl) matEl.dataset.fromCatalog = "1";
        try {
          var el = document.getElementById("catalog-tarifas");
          if (el) {
            var map = tariffs();
            map[material.toUpperCase()] = parseFloat(tarifa);
            el.textContent = JSON.stringify(map);
          }
          var dl = document.getElementById("dl-materiales");
          if (dl) {
            var exists = false;
            dl.querySelectorAll("option").forEach(function (o) {
              if (String(o.value).toUpperCase() === material.toUpperCase()) exists = true;
            });
            if (!exists) {
              var opt = document.createElement("option");
              opt.value = material.toUpperCase();
              dl.appendChild(opt);
            }
          }
        } catch (e) { /* ignore */ }
      })
      .catch(function () {
        toast("Error de red al guardar material", true);
      })
      .finally(function () {
        btn.disabled = false;
        btn.textContent = prev;
      });
  }

  function bindSaveButtons(root) {
    root = root || document;
    root.querySelectorAll(".btn-save-mod-cat").forEach(function (btn) {
      if (btn.dataset.catSaveBound) return;
      btn.dataset.catSaveBound = "1";
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        saveModeloFromButton(btn);
      });
    });
    root.querySelectorAll(".btn-save-mat-cat").forEach(function (btn) {
      if (btn.dataset.catSaveBound) return;
      btn.dataset.catSaveBound = "1";
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        saveMaterialFromButton(btn);
      });
    });
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
    bindSaveButtons(root);
  }

  function init() {
    bindForm(document);
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

  var api = {
    bind: bindForm,
    suggest: suggestFromServer,
    onMaterial: onMaterialInput,
    onMaterialInput: onMaterialInput,
    onModeloInput: onModeloInput,
    markTarifaEdited: markUserEditedTarifa,
    saveModelo: saveModeloFromButton,
    saveMaterial: saveMaterialFromButton,
  };
  // Alias que usa la plantilla produccion.html
  global.FajosCatalogAssist = api;
  global.CatalogAssist = api;
})(window);
