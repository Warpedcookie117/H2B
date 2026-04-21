// barra_progreso.js
export function iniciarBarraProgreso(fetchPromise) {
    const container = document.getElementById("barra-progreso-container");
    const fill      = document.getElementById("barra-fill");
    const msg       = document.getElementById("barra-mensaje");

    // Panel de debug tipo terminal
    let debugEl = document.getElementById("barra-debug");
    if (!debugEl) {
        debugEl = document.createElement("div");
        debugEl.id = "barra-debug";
        debugEl.style.cssText = [
            "font-family:monospace",
            "font-size:0.7rem",
            "background:#0d1117",
            "color:#3fb950",
            "padding:0.75rem 1rem",
            "margin-top:0.5rem",
            "max-height:180px",
            "overflow-y:auto",
            "border:2px solid #30363d",
            "white-space:pre-wrap",
            "word-break:break-all",
        ].join(";");
        container.appendChild(debugEl);
    }
    debugEl.textContent = "";

    function log(line, color) {
        const ts = new Date().toISOString().slice(11, 19);
        const span = document.createElement("span");
        span.style.color = color || "#3fb950";
        span.textContent = `[${ts}] ${line}\n`;
        debugEl.appendChild(span);
        debugEl.scrollTop = debugEl.scrollHeight;
    }

    container.style.display = "block";
    container.scrollIntoView({ behavior: "smooth", block: "center" });

    const startTime = Date.now();
    log("POST /inventario/nuevo_producto/ — iniciando...");

    const pasos = [
        { pct: 15, txt: "Validando campos del formulario..." },
        { pct: 35, txt: "Guardando atributos..." },
        { pct: 55, txt: "Verificando duplicados en base de datos..." },
        { pct: 72, txt: "Procesando imagen con CLIP (puede tardar)..." },
        { pct: 88, txt: "Registrando producto en el sistema..." },
    ];

    let i = 0;
    let terminado = false;

    const intervalo = setInterval(() => {
        if (terminado || i >= pasos.length) { clearInterval(intervalo); return; }
        fill.style.width = pasos[i].pct + "%";
        msg.textContent  = pasos[i].txt;
        log(`→ ${pasos[i].txt}`);
        i++;
    }, 700);

    fetchPromise
        .then(async (resp) => {
            clearInterval(intervalo);
            terminado = true;
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            log(`HTTP ${resp.status} recibido en ${elapsed}s`, resp.ok ? "#3fb950" : "#f85149");

            if (!resp.ok) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";

                let body = "";
                try { body = await resp.text(); } catch { body = "(sin cuerpo)"; }

                if (resp.status === 500) {
                    msg.textContent = "Error interno del servidor (500).";
                    log("Posibles causas: error en DB, Cloudinary, CLIP inference, o excepción no controlada.", "#f85149");
                    if (body) log(`Detalle: ${body.slice(0, 400)}`, "#e3b341");
                } else if (resp.status === 502 || resp.status === 504) {
                    msg.textContent = `Gateway timeout (${resp.status}) — el servidor tardó demasiado.`;
                    log(`Worker timeout o servidor caído. Aumentar --timeout en gunicorn.`, "#f85149");
                } else if (resp.status === 400) {
                    msg.textContent = `Bad Request (400) — dominio no en ALLOWED_HOSTS o CSRF inválido.`;
                    log(`Verificar ALLOWED_HOSTS y CSRF_TRUSTED_ORIGINS en settings.py`, "#f85149");
                } else if (resp.status === 403) {
                    msg.textContent = "Sin permiso (403). Verifica que estás autenticado.";
                    log("CSRF token inválido o sesión expirada.", "#f85149");
                } else {
                    msg.textContent = `Error HTTP ${resp.status}.`;
                    log(`Body: ${body.slice(0, 200)}`, "#e3b341");
                }
                return;
            }

            let data;
            try {
                data = await resp.json();
            } catch (parseErr) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";
                msg.textContent = "El servidor respondió algo que no es JSON válido.";
                log(`Parse error: ${parseErr.message}`, "#f85149");
                return;
            }

            log(`success=${data.success}${data.errors ? " | errors=" + JSON.stringify(data.errors) : ""}`);

            if (data.success) {
                fill.style.width = "100%";
                fill.style.backgroundColor = "#06D6A0";
                msg.textContent = "Producto registrado correctamente.";
                log(`Redirigiendo → ${data.redirect}`);
                setTimeout(() => { window.location.href = data.redirect; }, 1200);
            } else {
                const errText = Array.isArray(data.errors)
                    ? data.errors.join(" | ")
                    : (data.errors || "Error de validación sin detalle.");
                fill.style.width = "100%";
                fill.style.backgroundColor = "#FF006E";
                msg.textContent = "Error: " + errText;
                log(`Validación fallida: ${errText}`, "#f85149");
            }
        })
        .catch((err) => {
            clearInterval(intervalo);
            terminado = true;
            const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);

            fill.style.width = "100%";
            fill.style.backgroundColor = "#FF006E";

            if (elapsed > 25) {
                msg.textContent = `Timeout (${elapsed}s) — el worker fue interrumpido por el servidor.`;
                log(`WORKER KILLED tras ${elapsed}s. Causa probable: CLIP inference lenta en CPU, OOM, o gunicorn --timeout insuficiente.`, "#f85149");
            } else {
                msg.textContent = "Sin respuesta del servidor. Revisa tu conexión a internet.";
                log(`Fetch error tras ${elapsed}s: ${err.name} — ${err.message}`, "#f85149");
            }
        });
}
