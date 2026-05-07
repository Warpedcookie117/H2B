// stock.js — Refresca el stock de los productos en el POS sin recargar la página

import { carrito } from "./core.js";

console.log("[POS:stock] Módulo cargado");

const URL_STOCK = "/ventas/stock-productos/";
const INTERVALO_MS = 60_000; // cada 60 segundos

// ============================================================
// Actualizar data-attributes de las cards y el carrito
// ============================================================

async function refrescarStock() {
    console.log("[POS:stock] refrescarStock — iniciando fetch...");
    try {
        const resp = await fetch(URL_STOCK);
        if (!resp.ok) {
            console.warn(`[POS:stock] respuesta no OK: ${resp.status}`);
            return;
        }
        const data = await resp.json();
        console.log(`[POS:stock] datos recibidos para ${Object.keys(data).length} productos`);

        let removidos = 0;
        let actualizados = 0;

        // 1) Actualizar cada card del grid
        document.querySelectorAll(".producto-item[data-id]").forEach(card => {
            const id = parseInt(card.dataset.id);
            if (!data[id]) return;

            const { piso, bodega } = data[id];

            if (piso <= 0) {
                console.log(`[POS:stock] producto id=${id} sin stock en piso → removido del grid`);
                card.remove();
                removidos++;
                return;
            }

            card.dataset.stockPiso   = piso;
            card.dataset.stockBodega = bodega;
            actualizados++;
        });

        // 2) Actualizar items ya en el carrito
        carrito.forEach(item => {
            if (!data[item.id]) return;
            const anterior = { piso: item.stock_piso, bodega: item.stock_bodega };
            item.stock_piso   = data[item.id].piso;
            item.stock_bodega = data[item.id].bodega;
            if (anterior.piso !== item.stock_piso || anterior.bodega !== item.stock_bodega) {
                console.log(`[POS:stock] carrito "${item.nombre}": piso ${anterior.piso}→${item.stock_piso} bodega ${anterior.bodega}→${item.stock_bodega}`);
            }
        });

        console.log(`[POS:stock] refrescarStock completo — actualizados=${actualizados} removidos=${removidos}`);

    } catch (e) {
        console.warn("[POS:stock] Error al refrescar stock:", e);
    }
}

// ============================================================
// Inicialización
// ============================================================

export function initStock() {
    console.log(`[POS:stock] initStock — intervalo=${INTERVALO_MS}ms`);

    document.addEventListener("pago-exito", () => {
        console.log("[POS:stock] pago-exito detectado → refrescando stock");
        refrescarStock();
    });

    setInterval(refrescarStock, INTERVALO_MS);
}
