/**
 * Totales en vivo + toast + confirmación día pasado.
 * Principios: KPI visibles siempre; en semana cerrada (sin inputs) lee celdas estáticas.
 */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function parseNum(txt) {
    if (txt == null || txt === "") return 0;
    const v = parseFloat(String(txt).replace(/[^0-9.,\-]/g, "").replace(",", "."));
    return isNaN(v) ? 0 : v;
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

    /**
     * Suma gramos/efectivo.
     * - Con inputs.cell-gm: recalcula y actualiza celdas de total.
     * - Sin inputs (semana cerrada / solo lectura): lee .cell-total y .cell-efectivo
     *   y NO los sobrescribe (evita poner 0 al abrir semanas cerradas).
     */
    recalcFromTable(tableSel, kpiSel) {
      const table = $(tableSel);
      const kpi = $(kpiSel);
      if (!table || !kpi) return;

      const anyInput = !!table.querySelector("input.cell-gm");
      let lineas = 0, gramos = 0, efectivo = 0;

      $all("tbody tr", table).forEach((tr) => {
        if (tr.style.display === "none") return;
        if (!tr.querySelector("td")) return;
        // fila vacía de mensaje
        if (tr.querySelector("td[colspan]")) return;

        const cells = $all("input.cell-gm", tr);
        lineas += 1;

        if (cells.length) {
          let rowGr = 0;
          cells.forEach((inp) => {
            const v = parseFloat(String(inp.value || "").replace(",", "."));
            if (!isNaN(v) && v > 0) rowGr += v;
          });
          let tarifa = parseFloat(tr.dataset.tarifa || "0") || 0;
          if (!tarifa) {
            const tarCell = tr.querySelector("[data-tarifa]");
            if (tarCell) tarifa = parseFloat(tarCell.dataset.tarifa || tarCell.value || "0") || 0;
          }
          if (!tarifa) {
            const tds = $all("td", tr);
            // col $/G suele ser índice 6 (sel, ⋯, nom, ubic, folio, mod, mat, tar)
            for (let i = 0; i < tds.length; i++) {
              const t = parseFloat((tds[i].textContent || "").replace(/[^0-9.]/g, ""));
              if (!isNaN(t) && t >= 1 && t <= 500 && tds[i].className.indexOf("cell") < 0) {
                // prefer cell near material: try data
              }
            }
            const tarTd = tr.querySelector("td.col-tar, [data-field='tarifa_gr']");
            if (tarTd) tarifa = parseNum(tarTd.textContent);
            else if (tds.length > 6) tarifa = parseNum(tds[6].textContent);
          }
          gramos += rowGr;
          efectivo += rowGr * (tarifa || 0);
          const totCell = tr.querySelector(".cell-total");
          if (totCell) totCell.textContent = rowGr ? String(Math.round(rowGr * 10) / 10) : "";
          const efCell = tr.querySelector(".cell-efectivo");
          if (efCell) efCell.textContent = rowGr * tarifa ? ("$" + (rowGr * tarifa).toFixed(2)) : "";
        } else {
          // Solo lectura: respetar totales del servidor
          const totCell = tr.querySelector(".cell-total");
          const efCell = tr.querySelector(".cell-efectivo");
          const g = parseNum(totCell && totCell.textContent);
          const e = parseNum(efCell && efCell.textContent);
          gramos += g;
          efectivo += e;
        }
      });

      kpi.innerHTML =
        "<span class='kpi-item'><b>" + lineas + "</b> líneas</span>" +
        "<span class='kpi-item'><b>" + (gramos ? (Math.round(gramos * 10) / 10) : "0") + "</b> g</span>" +
        "<span class='kpi-item money'><b>$" + efectivo.toFixed(2) + "</b></span>";
    },

    bindGramInputs(opts) {
      const {
        tableSel = "table",
        kpiSel = "#kpi-live",
        onSave,
      } = opts || {};
      const inputs = $all(tableSel + " input.cell-gm");
      if (!inputs.length) {
        // Semana cerrada / sin captura: solo consolidar KPI desde celdas estáticas
        this.recalcFromTable(tableSel, kpiSel);
        return;
      }
      inputs.forEach((inp) => {
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
          this.recalcFromTable(tableSel, kpiSel);
        });
      });
      this.recalcFromTable(tableSel, kpiSel);
    },
  };
})();
