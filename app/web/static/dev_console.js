/**
 * Consola Dev de solo lectura (poll /api/dev/logs).
 */
(function () {
  "use strict";
  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }
  ready(function () {
    var pre = document.getElementById("dev-console");
    var status = document.getElementById("dev-log-status");
    if (!pre || !status) return;
    var lastId = 0;
    var auto = document.getElementById("dev-log-autoscroll");
    var pause = document.getElementById("dev-log-pause");
    var clearBtn = document.getElementById("dev-log-clear");

    function esc(s) {
      return String(s || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;");
    }
    function line(ev) {
      var cls = "log-" + (ev.level || "info");
      var src = ev.source || "";
      var path = ev.path ? " [" + ev.path + "]" : "";
      var extra = "";
      if (ev.detail) {
        extra = "\n  └ " + String(ev.detail).split("\n")[0].slice(0, 220);
      }
      return (
        '<div class="' + cls + '">' +
        esc(ev.ts) + " · " + esc((ev.level || "").toUpperCase()) + " · " + esc(src) + path +
        "\n  " + esc(ev.message) + esc(extra) +
        "</div>"
      );
    }
    function append(events) {
      if (!events || !events.length) return;
      pre.insertAdjacentHTML("beforeend", events.map(line).join(""));
      lastId = events[events.length - 1].id;
      if (auto && auto.checked) pre.scrollTop = pre.scrollHeight;
    }
    async function tick() {
      if (pause && pause.checked) {
        status.textContent = "pausado";
        return;
      }
      try {
        var res = await fetch("/api/dev/logs?after_id=" + lastId + "&limit=100");
        var data = await res.json();
        append(data.events || []);
        status.textContent = "en vivo · #" + lastId;
      } catch (e) {
        status.textContent = "sin conexión";
      }
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", async function () {
        try {
          await fetch("/api/dev/logs/clear", { method: "POST" });
        } catch (e) {}
        pre.innerHTML = "";
        lastId = 0;
        status.textContent = "limpiado";
      });
    }
    fetch("/api/dev/logs?after_id=0&limit=120")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        pre.innerHTML = "";
        append(data.events || []);
        status.textContent = "en vivo · #" + lastId;
      })
      .catch(function () {
        status.textContent = "sin conexión";
      });
    setInterval(tick, 2000);
  });
})();
