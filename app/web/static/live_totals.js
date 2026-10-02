/**
 * Totales en vivo. Semana cerrada: suma data-gm / data-total y NO borra celdas.
 */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function parseNum(txt) {
    if (txt == null || txt === "") return 0;
    const v = parseFloat(String(txt).replace(/[^0-9.,\-]/g, "").replace(",", "."));
    return isNaN(v) ? 0 : v;
  }

  function fmtG(n) {
    if (!n) return "";
    const x = Math.round(n * 10) / 10;
    return (x % 1 === 0) ? String(x) : x.toFixed(1);
  }

  window.FajosLive = {
    flashRow(el) {
      const tr = el && el.closest ? el.closest("tr") : null;
      if (!tr) return;
      tr.classList.remove("row-saved");
      void tr.offsetWidth;
      tr.classList.add("row-saved");
      setTimeout(() => tr.classList.remove("row-saved"), 700);
    },
    flashCell(inp) {
      if (!inp) return;
      inp.classList.remove("cell-ok");
      void inp.offsetWidth;
      inp.classList.add("cell-ok");
      setTimeout(() => inp.classList.remove("cell-ok"), 550);
    },
    pulseKpi(sel) {
      const el = document.querySelector(sel || "#kpi-live");
      if (!el) return;
      el.classList.remove("kpi-pulse");
      void el.offsetWidth;
      el.classList.add("kpi-pulse");
      setTimeout(() => el.classList.remove("kpi-pulse"), 400);
    },
    showToast(msg, err) {
      let el = $("#toast");
      if (!el) {
        el = document.createElement("div");
        el.id = "toast";
        el.className = "toast-web";
        document.body.appendChild(el);
      }
      el.hidden = false;
      el.textContent = msg;
      el.className = "toast-web" + (err ? " err" : " ok");
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      clearTimeout(window._toastT);
      window._toastT = setTimeout(() => { el.hidden = true; }, err ? 6000 : 2800);
    },

    /** Gramos de una fila: inputs, data-gm o data-total */
    rowGramos(tr) {
      const inputs = $all("input.cell-gm", tr);
      if (inputs.length) {
        let s = 0;
        inputs.forEach((inp) => {
          const v = parseNum(inp.value);
          if (v > 0) s += v;
        });
        return s;
      }
      const tot = tr.querySelector(".cell-total");
      let g = parseNum(tot && (tot.getAttribute("data-total") || tot.textContent));
      if (g > 0) return g;
      let s = 0;
      $all("td.cell-dia", tr).forEach((td) => {
        s += parseNum(td.getAttribute("data-gm") || td.textContent);
      });
      return s;
    },

    rowTarifa(tr) {
      let t = parseFloat(tr.dataset.tarifa || "0") || 0;
      if (t) return t;
      const tarTd = tr.querySelector("td.col-tar, [data-field='tarifa_gr']");
      if (tarTd) t = parseNum(tarTd.textContent);
      return t || 0;
    },

    recalcFromTable(tableSel, kpiSel) {
      const table = $(tableSel) || $("table.sortable") || $(".table-wrap table");
      const kpi = $(kpiSel) || $("#kpi-live");
      if (!table || !kpi) return;

      let lineas = 0, gramos = 0, efectivo = 0;
      $all("tbody tr", table).forEach((tr) => {
        if (tr.style.display === "none") return;
        if (!tr.querySelector("td") || tr.querySelector("td[colspan]")) return;
        lineas += 1;
        const g = this.rowGramos(tr);
        const tarifa = this.rowTarifa(tr);
        const e = g * tarifa;
        gramos += g;
        efectivo += e;

        const totCell = tr.querySelector(".cell-total");
        const efCell = tr.querySelector(".cell-efectivo");
        const hasInputs = !!tr.querySelector("input.cell-gm");
        // Siempre recalcular GR/$ desde días × tarifa (corrige $ stale con 0 g)
        if (totCell) {
          if (g > 0) {
            totCell.textContent = fmtG(g);
            totCell.setAttribute("data-total", String(g));
          } else if (hasInputs) {
            totCell.textContent = "";
            totCell.setAttribute("data-total", "0");
          }
        }
        if (efCell) {
          if (e > 0) {
            efCell.textContent = "$" + e.toFixed(2);
            efCell.setAttribute("data-efectivo", e.toFixed(2));
          } else if (hasInputs || g <= 0) {
            // 0 g → $ vacío (nunca dejar $150 huérfano)
            efCell.textContent = "";
            efCell.setAttribute("data-efectivo", "0");
          }
        }
      });

      // Fallback servidor solo si no hay filas visibles (tabla vacía / sin datos),
      // NO cuando un filtro oculta todo o cuando hay filas con 0 g
      const sg = parseNum(kpi.getAttribute("data-server-gramos"));
      const se = parseNum(kpi.getAttribute("data-server-efectivo"));
      const sl = parseNum(kpi.getAttribute("data-server-lineas"));
      const anyFilter =
        !!(document.getElementById("flt-texto") || {}).value ||
        !!(document.getElementById("flt-sin-firma-avance") || {}).checked ||
        !!(document.getElementById("flt-sin-firma-sin-avance") || {}).checked ||
        !!(document.getElementById("flt-sin-hoy") || {}).checked;
      if (!anyFilter && lineas <= 0 && gramos <= 0 && sg > 0) {
        gramos = sg;
        efectivo = se;
        if (sl > 0) lineas = sl;
      }

      kpi.innerHTML =
        "<span class='kpi-item'><b>" + lineas + "</b> líneas</span>" +
        "<span class='kpi-item'><b>" + (gramos ? fmtG(gramos) : "0") + "</b> g</span>" +
        "<span class='kpi-item money'><b>$" + efectivo.toFixed(2) + "</b></span>";
      // conservar data-server
      if (sg) kpi.setAttribute("data-server-gramos", String(sg));
      if (se) kpi.setAttribute("data-server-efectivo", String(se));
      if (sl) kpi.setAttribute("data-server-lineas", String(sl));
    },

    bindGramInputs(opts) {
      const {
        tableSel = "table.sortable",
        kpiSel = "#kpi-live",
        onSave,
      } = opts || {};
      const table = $(tableSel) || $(".table-wrap table");
      if (!table) {
        this.recalcFromTable(tableSel, kpiSel);
        return;
      }
      const inputs = $all("input.cell-gm", table);
      inputs.forEach((inp) => {
        inp.addEventListener("change", async () => {
          if (typeof onSave === "function") await onSave(inp);
          this.recalcFromTable(tableSel, kpiSel);
          this.flashCell(inp);
          this.flashRow(inp);
          this.pulseKpi(kpiSel);
        });
        inp.addEventListener("input", () => this.recalcFromTable(tableSel, kpiSel));
      });
      // Siempre recalcular al cargar (rellena GR/$ en semana cerrada)
      this.recalcFromTable(tableSel, kpiSel);
    },
  };

  // Auto-arranque: si hay tabla Plata, rellenar totales aunque nadie llame bind
  document.addEventListener("DOMContentLoaded", function () {
    if ($("#kpi-live") && ($("table.sortable") || $(".table-wrap table"))) {
      try {
        window.FajosLive.recalcFromTable("table.sortable", "#kpi-live");
      } catch (e) { /* ignore */ }
    }
  });
})();
