// impresion.js — Impresión via window.print() para impresora térmica con driver usbprint.sys

console.log("[POS:impresion] Módulo cargado");

export function initImpresion() {
    console.log("[POS:impresion] initImpresion — escuchando evento 'imprimir-ticket'");
    document.addEventListener("imprimir-ticket", async (e) => {
        console.log("[POS:impresion] imprimir-ticket recibido:", e.detail);
        try {
            await imprimirTicket(e.detail);
        } catch (err) {
            console.error("[POS:impresion] Error de impresión:", err);
            document.dispatchEvent(new CustomEvent("impresion-fallo", {
                detail: {
                    venta_id: e.detail.venta_id,
                    motivo: err.message || "No se pudo abrir la ventana de impresión."
                }
            }));
        }
    });
}

async function imprimirTicket({ ticket_texto, venta_id }) {
    console.log(`[POS:impresion] imprimirTicket → venta_id=${venta_id} texto_len=${ticket_texto?.length}`);

    if (!ticket_texto) {
        throw new Error("No se recibió el texto del ticket.");
    }

    const textoEscapado = ticket_texto
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    const html = `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <title>Ticket #${venta_id}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Courier New', Courier, monospace;
      font-size: 10pt;
      background: white;
      color: black;
    }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      font-family: inherit;
      font-size: inherit;
      line-height: 1.5;
      padding: 2mm;
    }
    @media print {
      @page { size: 58mm auto; margin: 0mm 2mm; }
      body { width: 58mm; }
    }
  </style>
</head>
<body>
  <pre>${textoEscapado}</pre>
  <script>
    window.onload = function () {
      window.print();
      window.onafterprint = function () { window.close(); };
      setTimeout(function () { window.close(); }, 5000);
    };
  <\/script>
</body>
</html>`;

    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url  = URL.createObjectURL(blob);
    console.log(`[POS:impresion] abriendo ventana de impresión...`);
    const popup = window.open(url, "_blank", "width=300,height=500,toolbar=0,menubar=0");

    if (!popup) {
        URL.revokeObjectURL(url);
        console.error("[POS:impresion] VENTANA BLOQUEADA por el navegador");
        throw new Error(
            "El navegador bloqueó la ventana de impresión. " +
            "Permite popups para este sitio e intenta de nuevo."
        );
    }

    popup.addEventListener("unload", () => URL.revokeObjectURL(url));
    console.log("[POS:impresion] ventana de impresión abierta ✓");

    document.dispatchEvent(new CustomEvent("impresion-exito", {
        detail: { venta_id }
    }));
}
