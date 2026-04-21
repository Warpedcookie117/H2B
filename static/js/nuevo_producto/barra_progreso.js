// barra_progreso.js
export function iniciarBarraProgreso(fetchPromise) {
    const container = document.getElementById("barra-progreso-container");
    const fill      = document.getElementById("barra-fill");
    const msg       = document.getElementById("barra-mensaje");

    // Panel de actividad
    let logPanel = document.getElementById("barra-log-panel");
    if (!logPanel) {
        logPanel = document.createElement("div");
        logPanel.id = "barra-log-panel";
        logPanel.style.cssText = [
            "margin-top:0.75rem",
            "border:3px solid black",
            "background:#fff",
            "max-height:160px",
            "overflow-y:auto",
            "box-shadow:4px 4px 0 0 black",
        ].join(";");
        container.appendChild(logPanel);
    }
    logPanel.innerHTML = "";

    function log(icono, texto, tipo) {
        const row = document.createElement("div");
        const colores = { ok: "#06D6A0", error: "#FF006E", info: "#fff", warn: "#FFBE0B" };
        row.style.cssText = [
            `background:${colores[tipo] || "#fff"}`,
            "border-bottom:2px solid black",
            "padding:0.35rem 0.75rem",
            "display:flex",
            "align-items:center",
            "gap:0.5rem",
            "font-size:0.78rem",
            "font-weight:700",
            "color:black",
        ].join(";");
        row.innerHTML = `<span style="font-size:1rem;flex-shrink:0">${icono}</span><span>${texto}</span>`;
        logPanel.appendChild(row);
        logPanel.scrollTop = logPanel.scrollHeight;
    }

    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth", block: "center" });

    const startTime = Date.now();
    log("🚀", "Enviando información del producto...", "info");

    const pasos = [
        { pct: 15, txt: "Revisando que todo esté completo...",     icono: "🔍" },
        { pct: 35, txt: "Guardando características del producto...", icono: "💾" },
        { pct: 55, txt: "Verificando que no exista un duplicado...", icono: "🕵️" },
        { pct: 72, txt: "Analizando la imagen...",                  icono: "🖼️" },
        { pct: 88, txt: "Registrando en el sistema...",             icono: "📦" },
    ];

    let i = 0;
    let terminado = false;

    const intervalo = setInterval(() => {
        if (terminado || i >= pasos.length) { clearInterval(intervalo); return; }
        fill.style.width = pasos[i].pct + "%";
        msg.textContent  = pasos[i].txt;
        log(pasos[i].icono, pasos[i].txt, "info");
        i++;
    }, 700);

    fetchPromise
        .then(async (resp) => {
            clearInterval(intervalo);
            terminado = true;
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            if (!resp.ok) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";

                let body = "";
                try { body = await resp.text(); } catch { /**/ }

                if (resp.status === 500) {
                    msg.textContent = "Algo falló en el servidor. Intenta de nuevo.";
                    log("❌", "El servidor encontró un error interno.", "error");
                    if (body) log("🔎", body.slice(0, 300), "warn");
                } else if (resp.status === 502 || resp.status === 504) {
                    msg.textContent = "El servidor tardó demasiado. Intenta de nuevo.";
                    log("⏱️", `Sin respuesta tras ${elapsed}s. El servidor puede estar ocupado.`, "error");
                } else if (resp.status === 400) {
                    msg.textContent = "Solicitud rechazada. Recarga la página e intenta de nuevo.";
                    log("🚫", "La sesión puede haber expirado.", "warn");
                } else if (resp.status === 403) {
                    msg.textContent = "Sin permiso. Vuelve a iniciar sesión.";
                    log("🔒", "Acceso denegado.", "error");
                } else {
                    msg.textContent = `Error inesperado. Intenta de nuevo.`;
                    log("⚠️", `Código de respuesta: ${resp.status}`, "warn");
                }
                return;
            }

            let data;
            try {
                data = await resp.json();
            } catch {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";
                msg.textContent = "Respuesta inesperada del servidor. Intenta de nuevo.";
                log("⚠️", "No se pudo leer la respuesta.", "warn");
                return;
            }

            if (data.success) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#06D6A0";
                msg.textContent = "¡Producto registrado correctamente!";
                log("✅", `Listo en ${elapsed}s. Redirigiendo...`, "ok");
                setTimeout(() => { window.location.href = data.redirect; }, 1200);
            } else {
                const errText = Array.isArray(data.errors)
                    ? data.errors.join(" — ")
                    : (data.errors || "Error al guardar el producto.");
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";
                msg.textContent = errText;
                log("❌", errText, "error");
            }
        })
        .catch((_err) => {
            clearInterval(intervalo);
            terminado = true;
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
            fill.style.width = "100%";
            fill.style.backgroundColor = "#FF006E";

            if (elapsed > 25) {
                msg.textContent = "El servidor tardó demasiado. Intenta de nuevo en unos segundos.";
                log("⏱️", `Sin respuesta tras ${elapsed}s. El servidor puede estar muy ocupado.`, "error");
            } else {
                msg.textContent = "Sin conexión. Revisa tu internet e intenta de nuevo.";
                log("📡", "No se pudo conectar con el servidor.", "error");
            }
        });
}
