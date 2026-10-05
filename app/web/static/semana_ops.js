/**
 * Cerrar / reabrir semana y duplicar (todas las áreas o solo una).
 */
(function (global) {
  function toast(msg, err) {
    if (window.FajosLive && FajosLive.showToast) return FajosLive.showToast(msg, err);
    if (err) alert(msg);
  }

  async function cerrarSemana(semanaId) {
    if (!semanaId) return;
    if (!confirm("¿Cerrar esta semana?\n\nNo se podrá capturar ni editar hasta reabrirla.\nAplica a Plata, Pita y Taller (es la misma semana).")) return;
    const fd = new FormData();
    fd.set("usuario", "web");
    const res = await fetch("/api/semanas/" + semanaId + "/cerrar", { method: "POST", body: fd });
    if (res.ok) {
      toast("Semana cerrada");
      location.reload();
    } else {
      let msg = "No se pudo cerrar";
      try {
        const j = await res.json();
        msg = j.detail || j.message || j.user_message || msg;
      } catch (e) {}
      toast(msg, true);
      alert(msg);
    }
  }

  async function reabrirSemana(semanaId) {
    if (!semanaId) return;
    if (!confirm("¿Reabrir la semana?\n\nVolverá a permitir captura y edición en las tres áreas.")) return;
    const res = await fetch("/api/semanas/" + semanaId + "/reabrir", { method: "POST", body: new FormData() });
    if (res.ok) {
      toast("Semana reabierta");
      location.reload();
    } else {
      toast("No se pudo reabrir", true);
    }
  }

  async function duplicarSemana(semanaId, areaActual) {
    if (!semanaId) return;

    if (confirm(
      "¿Duplicar las TRES áreas (Plata + Pita + Taller) a la semana siguiente?\n\n" +
      "Aceptar = las tres\nCancelar = elegir otra opción"
    )) {
      return doDuplicar(semanaId, "plt,pit,tll");
    }

    if (areaActual) {
      const labels = { plt: "solo Plata", pit: "solo Pita", tll: "solo Taller" };
      const label = labels[areaActual] || areaActual;
      if (confirm("¿Duplicar " + label + " solamente?")) {
        return doDuplicar(semanaId, areaActual);
      }
    }

    const raw = prompt(
      "Áreas a duplicar (plt, pit, tll) separadas por coma:\nEjemplo: plt,pit,tll",
      "plt,pit,tll"
    );
    if (!raw) return;
    const areas = raw.split(",").map(function (s) { return s.trim().toLowerCase(); })
      .filter(function (s) { return s === "plt" || s === "pit" || s === "tll"; });
    if (!areas.length) {
      alert("Ninguna área válida.");
      return;
    }
    return doDuplicar(semanaId, areas.join(","));
  }

  async function doDuplicar(semanaId, areas, force) {
    const body = new FormData();
    body.set("areas", areas);
    if (force) body.set("force", "1");
    const res = await fetch("/api/insights/duplicar/" + semanaId, { method: "POST", body: body });
    let data = {};
    try { data = await res.json(); } catch (e) {}
    if (!res.ok) {
      alert((data && (data.detail || data.message || data.user_message)) || "No se pudo duplicar");
      return;
    }
    if (data.ya_duplicada) {
      alert(
        (data.mensaje || "Esta semana ya estaba duplicada.") +
        "\n\nDestino: " + (data.destino_codigo || data.destino_id) +
        "\nNo se crearon líneas nuevas (omitidas: " + (data.total_skipped || 0) + ")."
      );
      if (data.destino_id) {
        location.href = location.pathname + "?semana_id=" + data.destino_id;
      }
      return;
    }
    alert(
      (data.mensaje || "Duplicado") +
      "\n→ semana " + (data.destino_codigo || data.destino_id) +
      "\nPlata: +" + ((data.plt && data.plt.created) || 0) +
        " (omitidas " + ((data.plt && data.plt.skipped) || 0) + ")" +
      "\nPita: +" + ((data.pit && data.pit.created) || 0) +
        " (omitidas " + ((data.pit && data.pit.skipped) || 0) + ")" +
      "\nTaller: +" + ((data.tll && data.tll.created) || 0) +
        " (omitidas " + ((data.tll && data.tll.skipped) || 0) + ")"
    );
    if (data.destino_id && (data.total_created || 0) > 0) {
      location.href = location.pathname + "?semana_id=" + data.destino_id;
    } else if (data.destino_id) {
      location.href = location.pathname + "?semana_id=" + data.destino_id;
    } else {
      location.reload();
    }
  }

  global.FajosSemanaOps = { cerrarSemana: cerrarSemana, reabrirSemana: reabrirSemana, duplicarSemana: duplicarSemana };
  global.cerrarSemana = function (id) { return cerrarSemana(id || global.SEMANA_ID); };
  global.reabrirSemana = function (id) { return reabrirSemana(id || global.SEMANA_ID); };
  global.duplicarSemana = function (id, area) {
    return duplicarSemana(id || global.SEMANA_ID, area || global.AREA_ACTUAL || null);
  };
})(window);
