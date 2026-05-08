// impresion.js — Impresión de tickets via QZ Tray (silencioso)
// Fallback: link al ticket HTML del servidor para imprimir manualmente.

let _qzOk = false;

export function initImpresion() {
    _conectarQZ();
    window._posTestPrint        = testPrint;
    window._posListarImpresoras = listarImpresoras;
}

/**
 * Intenta imprimir el ticket via QZ Tray.
 * @returns {{ ok: boolean, noQZ?: boolean, noConfig?: boolean, error?: string }}
 */
export async function imprimirTicket(ticket_texto, venta_id) {
    const printer = localStorage.getItem("pos_impresora") || "";

    if (!printer) return { ok: false, noConfig: true };

    if (!_qzOk) await _conectarQZ();

    if (!_qzOk) return { ok: false, noQZ: true };

    try {
        await _printQZ(ticket_texto, printer);
        return { ok: true };
    } catch (e) {
        console.error("[QZ] Error al imprimir:", e);
        return { ok: false, error: e.message };
    }
}

async function testPrint() {
    const printer = localStorage.getItem("pos_impresora") || "";
    if (!printer) { alert("Primero guarda el nombre de la impresora."); return; }

    if (!_qzOk) await _conectarQZ();
    if (!_qzOk) {
        alert("QZ Tray no está corriendo.\nÁbrelo desde el menú inicio e intenta de nuevo.");
        return;
    }

    const sep  = "-".repeat(30);
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
        await _printQZ(texto, printer);
        alert("Ticket de prueba enviado a: " + printer);
    } catch (e) {
        alert("Error: " + e.message);
    }
}

async function listarImpresoras() {
    if (!_qzOk) await _conectarQZ();
    if (!_qzOk) { alert("QZ Tray no está corriendo."); return; }
    try {
        const lista = await qz.printers.find();
        alert("Impresoras disponibles:\n\n" + lista.join("\n") + "\n\nCopia el nombre exacto en el campo de configuración.");
    } catch (e) {
        alert("Error listando impresoras: " + e.message);
    }
}

async function _conectarQZ() {
    if (!window.qz) { console.warn("[QZ] qz-tray.js no cargado"); return; }
    if (_qzOk)      return;

    try {
        // Obtener certificado del servidor (identifica a este sitio ante QZ Tray)
        let cert = "";
        try {
            const r = await fetch("/ventas/qz-cert/");
            if (r.ok) cert = await r.text();
        } catch (_) {}

        if (cert.includes("BEGIN CERTIFICATE")) {
            // Modo firmado: QZ Tray recuerda "Always Allow" para siempre
            qz.security.setCertificatePromise(resolve => resolve(cert));
            qz.security.setSignaturePromise(toSign => new Promise((resolve, reject) => {
                const csrf = document.cookie.match(/csrftoken=([^;]+)/)?.[1] || "";
                fetch("/ventas/qz-sign/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
                    body: JSON.stringify({ message: toSign }),
                }).then(r => r.json()).then(d => resolve(d.signature)).catch(reject);
            }));
        } else {
            // Sin cert (fallback): pregunta cada vez
            qz.security.setCertificatePromise(resolve => resolve());
            qz.security.setSignaturePromise(() => resolve => resolve());
        }

        await qz.websocket.connect({ retries: 2, delay: 1 });
        _qzOk = true;
        console.log("[QZ] Conectado ✓", cert ? "(con certificado)" : "(sin certificado)");
    } catch (e) {
        console.warn("[QZ] No disponible:", e.message || e);
    }
}

async function _printQZ(texto, printer) {
    if (!_qzOk) throw new Error("QZ Tray no conectado");
    const cfg = qz.configs.create(printer);
    await qz.print(cfg, [{ type: "raw", format: "plain", data: texto + "\n\n\n\n" }]);
}
