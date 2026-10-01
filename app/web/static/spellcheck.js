/**
 * Activa spellcheck del navegador/SO en campos de texto libres
 * y ofrece sugerencias (API) al escribir en notas / nombres largos.
 */
(function () {
  function isTextual(el) {
    if (!el || el.disabled || el.readOnly) return false;
    const tag = (el.tagName || "").toLowerCase();
    if (tag === "textarea") return true;
    if (tag !== "input") return false;
    const t = (el.type || "text").toLowerCase();
    if (["text", "search", "email", ""].indexOf(t) < 0) return false;
    // no números ni fechas
    if (el.inputMode === "decimal" || el.inputMode === "numeric") return false;
    if (el.classList.contains("cell-gm") || el.classList.contains("sueldo-base-inp")) return false;
    return true;
  }

  function enableSpellcheck(root) {
    const scope = root || document;
    scope.querySelectorAll("input, textarea").forEach(function (el) {
      if (!isTextual(el)) return;
      el.setAttribute("spellcheck", "true");
      if (!el.getAttribute("lang")) el.setAttribute("lang", "es");
      // autocapitalize ayuda en móviles; no fuerza ortografía
      if (!el.getAttribute("autocapitalize")) el.setAttribute("autocapitalize", "sentences");
    });
  }

  /** Datalist de sugerencias al blur/pausa en campos con data-spell="1" */
  function bindSuggest() {
    document.querySelectorAll("input[data-spell='1'], textarea[data-spell='1']").forEach(function (el) {
      if (el._spellBound) return;
      el._spellBound = true;
      let timer = null;
      const listId = "spell-dl-" + Math.random().toString(36).slice(2, 8);
      let dl = document.createElement("datalist");
      dl.id = listId;
      document.body.appendChild(dl);
      el.setAttribute("list", listId);

      function refresh() {
        const q = (el.value || "").trim();
        // última palabra
        const parts = q.split(/\s+/);
        const word = parts[parts.length - 1] || "";
        if (word.length < 3) {
          dl.innerHTML = "";
          return;
        }
        fetch("/api/spell/suggest?q=" + encodeURIComponent(word) + "&limit=6")
          .then(function (r) { return r.json(); })
          .then(function (data) {
            dl.innerHTML = "";
            (data.suggestions || []).forEach(function (s) {
              const opt = document.createElement("option");
              opt.value = parts.length > 1 ? parts.slice(0, -1).join(" ") + " " + s : s;
              opt.label = s;
              dl.appendChild(opt);
            });
          })
          .catch(function () { /* silencio */ });
      }
      el.addEventListener("input", function () {
        clearTimeout(timer);
        timer = setTimeout(refresh, 400);
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    enableSpellcheck(document);
    bindSuggest();
  });
  // por si se abren modales después
  document.addEventListener("focusin", function (ev) {
    if (isTextual(ev.target)) {
      ev.target.setAttribute("spellcheck", "true");
      if (!ev.target.getAttribute("lang")) ev.target.setAttribute("lang", "es");
    }
  });
  window.FajosSpell = { enableSpellcheck: enableSpellcheck, bindSuggest: bindSuggest };
})();
