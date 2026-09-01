/**
 * Totales en vivo + toast + confirmación día pasado.
 * Principios: KPI visibles siempre, actualizar tras cada edición sin recargar toda la página.
 */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

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
      // restart animation
      el.style.animation = "none";
      void el.offsetWidth;
      el.style.animation = "";
      clearTimeout(window._toastT);
      window._toastT = setTimeout(() => { el.hidden = true; }, err ? 6000 : 2800);
    },

    /** Suma gramos/efectivo de inputs.cell-gm y filas data-tarifa */
    recalcFromTable(tableSel, kpiSel) {
      const table = $(tableSel);
      const kpi = $(kpiSel);
      if (!table || !kpi) return;
      let lineas = 0, gramos = 0, efectivo = 0;
      $all("tbody tr", table).forEach((tr) => {
        if (tr.style.display === "none") return;
        if (!tr.querySelector("input.cell-gm") && !tr.querySelector("td")) return;
        const cells = $all("input.cell-gm", tr);
        if (!cells.length && !tr.dataset.prodId) {
          // static total cell
        }
        lineas += 1;
        let rowGr = 0;
        cells.forEach((inp) => {
          const v = parseFloat(inp.value);
          if (!isNaN(v)) rowGr += v;
        });
        // if no inputs, try data attributes or total column
        if (!cells.length) {
          const tds = $all("td", tr);
          // skip
        }
        gramos += rowGr;
        let tarifa = parseFloat(tr.dataset.tarifa || cells[0]?.dataset.tarifa || "0") || 0;
        if (!tarifa) {
          const tarCell = tr.querySelector("[data-tarifa]");
          if (tarCell) tarifa = parseFloat(tarCell.dataset.tarifa || tarCell.value || "0") || 0;
        }
        // try column $/Gr text
        if (!tarifa) {
          const tds = $all("td", tr);
          if (tds.length > 5) {
            const t = parseFloat((tds[5].textContent || "").replace(/[^0-9.]/g, ""));
            if (!isNaN(t)) tarifa = t;
          }
        }
        efectivo += rowGr * tarifa;
        // update total cell if last numeric display
        const totCell = tr.querySelector(".cell-total");
        if (totCell) totCell.textContent = rowGr ? rowGr.toFixed(2).replace(/\.00$/, "") : "";
        const efCell = tr.querySelector(".cell-efectivo");
        if (efCell) efCell.textContent = (rowGr * tarifa) ? ("$" + (rowGr * tarifa).toFixed(2)) : "";
      });
      kpi.innerHTML =
        "<span class='kpi-item'><b>" + lineas + "</b> líneas</span>" +
        "<span class='kpi-item'><b>" + (gramos ? gramos.toFixed(1) : "0") + "</b> g</span>" +
        "<span class='kpi-item money'><b>$" + efectivo.toFixed(2) + "</b></span>";
    },

    bindGramInputs(opts) {
      const {
        tableSel = "table",
        kpiSel = "#kpi-live",
        onSave,
      } = opts || {};
      $all(tableSel + " input.cell-gm").forEach((inp) => {
        inp.addEventListener("change", async () => {
          if (typeof onSave === "function") {
            await onSave(inp);
          }
          this.recalcFromTable(tableSel, kpiSel);
          this.flashCell(inp);
          this.flashRow(inp);
          this.pulseKpi(kpiSel);
        });
        inp.addEventListener("input", () => {
          // feedback inmediato al teclear
          this.recalcFromTable(tableSel, kpiSel);
        });
      });
      this.recalcFromTable(tableSel, kpiSel);
    },
  };
})();
