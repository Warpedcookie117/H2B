// impresion.js — Agente POS local (localhost:12345)
// print_server.py corre en la compu del cajero y hace el trabajo real.

const AGENT = "http://127.0.0.1:12345";

export function initImpresion() {
    window._posTestPrint        = testPrint;
    window._posTestEtiqueta     = testPrintEtiqueta;
    window._posListarImpresoras = listarImpresoras;
    window._posAgentStatus      = agentStatus;
    window._posPrinterInfo      = printerInfo;
}

export async function imprimirTicket(ticket_texto, _venta_id) {
    const printer = localStorage.getItem("pos_impresora") || "";
    if (!printer) return { ok: false, noConfig: true };

    try {
        const r = await fetch(`${AGENT}/print`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto: ticket_texto, printer }),
        });
        const d = await r.json();
        return d.ok ? { ok: true } : { ok: false, error: d.error };
    } catch {
        return { ok: false, noAgent: true };
    }
}

export async function agentStatus() {
    try {
        const r = await fetch(`${AGENT}/status`, { signal: AbortSignal.timeout(1500) });
        const d = await r.json();
        return { online: true, printer: d.printer };
    } catch {
        return { online: false };
    }
}

async function printerInfo(name) {
    if (!name) return null;
    try {
        const r = await fetch(`${AGENT}/printer-info?name=${encodeURIComponent(name)}`,
                              { signal: AbortSignal.timeout(2000) });
        return await r.json();
    } catch {
        return null;
    }
}

async function listarImpresoras() {
    try {
        const r = await fetch(`${AGENT}/printers`, { signal: AbortSignal.timeout(2000) });
        const d = await r.json();
        return d.printers || [];
    } catch {
        return null;
    }
}

function _formatearDiag(printer, d) {
    if (!d || !d.diag) return "Enviado a: " + printer + "\n(sin info adicional)";

    const ps   = d.diag.printer || {};
    const jobs = d.diag.jobs || [];

    let estado = "?";
    let veredicto = "";
    if (!ps.exists) {
        estado = "✗ NO instalada en Windows";
        veredicto = "Verifica que el nombre coincida EXACTAMENTE con el que aparece en\n'Impresoras y escaneres' de Windows.";
    } else if (!ps.online) {
        estado = "✗ " + (ps.status_text || "Offline");
        veredicto = "La impresora aparece pero NO esta lista.\nPosibles causas:\n  • Apagada o sin energia\n  • Cable USB / bluetooth desconectado\n  • Driver incorrecto (ej: usar driver POS-58 en un modelo distinto)";
    } else {
        estado = "✓ " + (ps.status_text || "Lista");
    }

    let lineasJobs = "Cola: " + jobs.length + " job(s) pendiente(s)";
    if (jobs.length > 0) {
        lineasJobs += "\n" + jobs.map(j =>
            "  • #" + j.id + " " + j.document + " [" + (j.status_flags || []).join(", ") + "]"
        ).join("\n");
        if (ps.online) {
            veredicto = (veredicto ? veredicto + "\n\n" : "")
                + "El job NO se ejecuto y sigue en cola.\nLa impresora esta 'lista' segun Windows pero no responde —\nrevisa el driver (probablemente sea el modelo incorrecto).";
        }
    }

    return [
        "Impresora: " + printer,
        "Estado:    " + estado,
        lineasJobs,
        "",
        veredicto || "Si la etiqueta NO salio fisicamente, revisa papel/driver.",
    ].join("\n");
}

async function testPrintEtiqueta() {
    const printer = localStorage.getItem("pos_impresora_etiquetas") || "";
    if (!printer) { alert("Primero guarda el nombre de la impresora de etiquetas."); return; }

    // Canvas a 30×15 mm @ 203 DPI (240×120 px) — tamaño 'chica'
    const W = 240, H = 120;
    const canvas = document.createElement("canvas");
    canvas.width  = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);
    ctx.strokeStyle = "#000000";
    ctx.lineWidth = 2;
    ctx.strokeRect(2, 2, W - 4, H - 4);
    ctx.fillStyle = "#000000";
    ctx.textAlign = "center";
    ctx.font = "bold 18px monospace";
    ctx.fillText("TEST ETIQUETA", W / 2, 26);
    ctx.font = "11px monospace";
    ctx.fillText(printer, W / 2, 50);
    ctx.fillText(new Date().toLocaleString("es-MX"), W / 2, 72);
    ctx.font = "10px monospace";
    ctx.fillText("30 x 15 mm — funciona!", W / 2, 96);

    const base64 = canvas.toDataURL("image/png").split(",")[1];

    try {
        const r = await fetch(`${AGENT}/print-label`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ imagen_base64: base64, printer, diag: true }),
        });
        const d = await r.json();
        if (!d.ok) { alert("Error: " + (d.error || "desconocido")); return; }
        alert("DIAGNOSTICO ETIQUETA\n\n" + _formatearDiag(printer, d));
    } catch {
        alert("Agente POS no disponible.\nAsegurate de que pos_agent.exe este corriendo.");
    }
}

async function testPrint() {
    const printer = localStorage.getItem("pos_impresora") || "";
    if (!printer) { alert("Primero guarda el nombre de la impresora."); return; }

    const sep   = "-".repeat(30);
    const texto = [
        "COMERCIALIZADORA MODELO",
        "   TEST DE IMPRESION   ",
        sep,
        "Impresora: " + printer,
        new Date().toLocaleString("es-MX"),
        sep,
        "Si ves esto, funciona! :)",
    ].join("\n");

    try {
        const r = await fetch(`${AGENT}/print`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ texto, printer, diag: true }),
        });
        const d = await r.json();
        if (!d.ok) { alert("Error: " + (d.error || "desconocido")); return; }
        alert("DIAGNOSTICO TICKET\n\n" + _formatearDiag(printer, d));
    } catch {
        alert("Agente POS no disponible.\nAsegurate de que pos_agent.exe este corriendo.");
    }
}
