/**
 * Avisos visibles ante fallos + envío a consola Dev.
 */
(function (global) {
  "use strict";

  function toast(msg, isErr) {
    try {
      if (global.FajosLive && typeof FajosLive.showToast === "function") {
        FajosLive.showToast(msg, !!isErr);
        return;
      }
    } catch (e) {}
    var el = document.getElementById("toast");
    if (!el) {
      el = document.createElement("div");
      el.id = "toast";
      el.className = "toast-web";
      document.body.appendChild(el);
    }
    el.hidden = false;
    el.textContent = msg;
    el.className = "toast-web" + (isErr ? " err" : " ok");
    clearTimeout(global._toastT);
    global._toastT = setTimeout(function () { el.hidden = true; }, isErr ? 6000 : 2800);
  }

  function postClientLog(level, message, detail) {
    try {
      var payload = JSON.stringify({
        level: level || "error",
        message: String(message || "").slice(0, 1500),
        detail: detail ? String(detail).slice(0, 3000) : null,
        path: location.pathname + location.search,
        url: location.href,
      });
      if (navigator.sendBeacon) {
        navigator.sendBeacon("/api/dev/client-log", new Blob([payload], { type: "application/json" }));
      } else {
        fetch("/api/dev/client-log", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: payload,
          keepalive: true,
        }).catch(function () {});
      }
    } catch (e) {}
  }

  global.addEventListener("error", function (ev) {
    var msg = (ev && ev.message) || "Error de script";
    var detail = [ev.filename, ev.lineno, ev.colno].filter(Boolean).join(":");
    if (ev.error && ev.error.stack) detail += "\n" + ev.error.stack;
    toast("Error: " + msg, true);
    postClientLog("error", msg, detail);
  });

  global.addEventListener("unhandledrejection", function (ev) {
    var reason = ev && ev.reason;
    var msg = (reason && (reason.message || String(reason))) || "Promesa rechazada";
    var detail = reason && reason.stack ? reason.stack : String(reason);
    toast("Error: " + msg, true);
    postClientLog("error", msg, detail);
  });

  // Envuelve fetch para avisar en fallos de red / 5xx (no interfiere con 4xx manejados por cada botón)
  var _fetch = global.fetch;
  if (typeof _fetch === "function") {
    global.fetch = function () {
      var args = arguments;
      return _fetch.apply(global, args).then(function (res) {
        if (res && res.status >= 500) {
          var url = "";
          try { url = (args[0] && args[0].url) || String(args[0] || ""); } catch (e) {}
          toast("Error del servidor (" + res.status + ")", true);
          postClientLog("error", "HTTP " + res.status + " " + url, null);
        }
        return res;
      }).catch(function (err) {
        toast("Sin conexión o fallo de red", true);
        postClientLog("error", "fetch failed: " + (err && err.message ? err.message : err), null);
        throw err;
      });
    };
  }

  // Click en botones: si el handler lanza, ya lo captura error global;
  // refuerzo para botones disabled silenciosos
  document.addEventListener("click", function (ev) {
    var btn = ev.target && ev.target.closest ? ev.target.closest("button, a.btn") : null;
    if (!btn) return;
    if (btn.disabled || btn.getAttribute("aria-disabled") === "true") {
      var why = btn.getAttribute("title") || "Acción no disponible ahora";
      // solo si parece un control de acción principal
      if (btn.classList.contains("btn")) {
        toast(why, true);
      }
    }
  }, true);

  global.FajosErrors = { toast: toast, log: postClientLog };
})(window);
