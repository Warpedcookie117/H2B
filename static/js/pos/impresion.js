// impresion.js — Impresión híbrida WebUSB + WebSerial + fallback

// ============================================================
// 1. Inicialización
// ============================================================

export function initImpresion() {
    document.addEventListener("imprimir-ticket", async (e) => {
        try {
            await imprimirTicketHibrido(e.detail);
        } catch (err) {
            document.dispatchEvent(new CustomEvent("impresion-fallo", {
                detail: {
                    venta_id: e.detail.venta_id,
                    motivo: "No se pudo imprimir el ticket"
                }
            }));
        }
    });
}



// ============================================================
// 2. Generar ESC/POS
// ============================================================

function generarTicketESC({ total, cambio }) {
    const encoder = new TextEncoder();

    let texto = "";
    texto += "      MODELO\n";
    texto += "-----------------------------\n";
    texto += "        TICKET DE VENTA\n";
    texto += "-----------------------------\n";
    texto += `TOTAL:     $${total.toFixed(2)}\n`;
    texto += `CAMBIO:    $${cambio.toFixed(2)}\n`;
    texto += "-----------------------------\n";
    texto += "Gracias por su compra\n\n\n\n";

    return encoder.encode(texto);
}



// ============================================================
// 3. Impresión híbrida
// ============================================================

async function imprimirTicketHibrido(data) {
    const escpos = generarTicketESC(data);

    // 1) WebUSB
    try {
        await imprimirWebUSB(escpos);
        document.dispatchEvent(new CustomEvent("impresion-exito", {
            detail: { venta_id: data.venta_id }
        }));
        return;
    } catch (err) {
        console.warn("WebUSB falló:", err);
    }

    // 2) WebSerial
    try {
        await imprimirWebSerial(escpos);
        document.dispatchEvent(new CustomEvent("impresion-exito", {
            detail: { venta_id: data.venta_id }
        }));
        return;
    } catch (err) {
        console.warn("WebSerial falló:", err);
    }

    // 3) Fallback final
    document.dispatchEvent(new CustomEvent("impresion-fallo", {
        detail: {
            venta_id: data.venta_id,
            motivo: "No se detectó ninguna impresora compatible"
        }
    }));
}



// ============================================================
// 4. Impresión por WebUSB
// ============================================================

async function imprimirWebUSB(escpos) {
    if (!("usb" in navigator)) throw new Error("WebUSB no soportado");

    const device = await navigator.usb.requestDevice({
        filters: [
            { vendorId: 0x0416 },
            { vendorId: 0x0483 },
            { vendorId: 0x1fc9 }
        ]
    });

    await device.open();
    if (device.configuration === null) {
        await device.selectConfiguration(1);
    }

    await device.claimInterface(0);
    await device.transferOut(1, escpos);
    await device.close();
}



// ============================================================
// 5. Impresión por WebSerial
// ============================================================

async function imprimirWebSerial(escpos) {
    if (!("serial" in navigator)) throw new Error("WebSerial no soportado");

    const port = await navigator.serial.requestPort();
    await port.open({ baudRate: 9600 });

    const writer = port.writable.getWriter();
    await writer.write(escpos);
    writer.releaseLock();

    await port.close();
}
