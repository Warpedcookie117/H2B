// stock.js — Refresca el stock de los productos en el POS sin recargar la página

import { carrito } from "./core.js";

const URL_STOCK = "/ventas/stock-productos/";
const INTERVALO_MS = 60_000; // cada 60 segundos

// ============================================================
// Actualizar data-attributes de las cards y el carrito
// ============================================================

async function refrescarStock() {
    try {
        const resp = await fetch(URL_STOCK);
        if (!resp.ok) return;
        const data = await resp.json();

        // 1) Actualizar cada card del grid
        document.querySelectorAll(".producto-item[data-id]").forEach(card => {
            const id = parseInt(card.dataset.id);
            if (!data[id]) return;

            const { piso, bodega } = data[id];

            // Sin stock en piso → quitar del POS
            if (piso <= 0) {
                card.remove();
                return;
            }

            card.dataset.stockPiso   = piso;
            card.dataset.stockBodega = bodega;
        });

        // 2) Actualizar items ya en el carrito
        carrito.forEach(item => {
            if (!data[item.id]) return;
            item.stock_piso   = data[item.id].piso;
            item.stock_bodega = data[item.id].bodega;
        });

    } catch (e) {
        console.warn("[stock] Error al refrescar stock:", e);
    }
}

// ============================================================
// Inicialización
// ============================================================

export function initStock() {
    // Refrescar al volver de una venta exitosa
    document.addEventListener("pago-exito", () => {
        refrescarStock();
    });

    // Refrescar periódicamente
    setInterval(refrescarStock, INTERVALO_MS);
}
