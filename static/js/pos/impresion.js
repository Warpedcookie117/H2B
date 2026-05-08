// impresion.js — Agente POS local (localhost:12345)
// print_server.py corre en la compu del cajero y hace el trabajo real.

const AGENT = "http://127.0.0.1:12345";

export function initImpresion() {
    window._posTestPrint        = testPrint;
    window._posListarImpresoras = listarImpresoras;
    window._posAgentStatus      = agentStatus;
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

async function listarImpresoras() {
    try {
        const r = await fetch(`${AGENT}/printers`, { signal: AbortSignal.timeout(2000) });
        const d = await r.json();
        return d.printers || [];
    } catch {
        return null;
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
            body: JSON.stringify({ texto, printer }),
        });
        const d = await r.json();
        alert(d.ok ? "Ticket enviado a: " + printer : "Error: " + (d.error || "desconocido"));
    } catch {
        alert("Agente POS no disponible.\nAsegurate de que pos_agent.exe este corriendo.");
    }
}
