// stock.js — Stock en tiempo real via WebSocket + polling de respaldo

import { carrito } from "./core.js";

console.log("[POS:stock] Módulo cargado");

const URL_STOCK = "/ventas/stock-productos/";
const FALLBACK_MS = 5 * 60_000; // polling cada 5 min solo como respaldo

// ============================================================
// Aplicar un cambio de stock a la card y al carrito
// ============================================================

function aplicarCambioStock(productoId, pisoNuevo, bodegaNuevo = null) {
    const id = parseInt(productoId);
    const card = document.querySelector(`.producto-item[data-id="${id}"]`);

    if (card) {
        if (pisoNuevo <= 0) {
            console.log(`[POS:stock] producto id=${id} sin stock en piso → removido`);
            card.remove();
        } else {
            card.dataset.stockPiso = pisoNuevo;
            if (bodegaNuevo !== null) card.dataset.stockBodega = bodegaNuevo;
            console.log(`[POS:stock] producto id=${id} piso=${pisoNuevo}${bodegaNuevo !== null ? ` bodega=${bodegaNuevo}` : ""}`);
        }
    }

    const itemCarrito = carrito.find(i => i.id === id);
    if (itemCarrito) {
        itemCarrito.stock_piso = pisoNuevo;
        if (bodegaNuevo !== null) itemCarrito.stock_bodega = bodegaNuevo;
    }
}

// ============================================================
// WebSocket — se conecta al grupo del piso de la sucursal
// ============================================================

function conectarWS(pisoId) {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const url   = `${proto}//${location.host}/ws/inventario/${pisoId}/`;
    console.log(`[POS:stock] conectando WS → ${url}`);

    const ws = new WebSocket(url);

    ws.onopen = () => {
        console.log("[POS:stock] WS conectado ✓ — sincronizando stock real...");
        refrescarStock();
    };

    ws.onmessage = (e) => {
        const { producto_id, cantidad_actual } = JSON.parse(e.data);
        console.log(`[POS:stock] WS → producto_id=${producto_id} cantidad=${cantidad_actual}`);
        aplicarCambioStock(producto_id, cantidad_actual);
    };

    ws.onclose = () => {
        console.warn("[POS:stock] WS cerrado — reconectando en 5 s...");
        setTimeout(() => conectarWS(pisoId), 5000);
    };

    ws.onerror = (err) => console.error("[POS:stock] WS error:", err);
}

// ============================================================
// Polling de respaldo (cubre bodega y mensajes perdidos)
// ============================================================

async function refrescarStock() {
    console.log("[POS:stock] polling de respaldo...");
    try {
        const resp = await fetch(URL_STOCK);
        if (!resp.ok) { console.warn(`[POS:stock] polling status ${resp.status}`); return; }
        const data = await resp.json();
        let n = 0;
        document.querySelectorAll(".producto-item[data-id]").forEach(card => {
            const id = parseInt(card.dataset.id);
            if (!data[id]) return;
            aplicarCambioStock(id, data[id].piso, data[id].bodega);
            n++;
        });
        console.log(`[POS:stock] polling — ${n} productos actualizados`);
    } catch (e) {
        console.warn("[POS:stock] polling error:", e);
    }
}

// ============================================================
// Init
// ============================================================

export function initStock() {
    console.log("[POS:stock] initStock");

    // window.sucursal_id = ubicacion_pos.id (definido en pos.html)
    const pisoId = window.sucursal_id;
    if (pisoId) {
        conectarWS(pisoId);
    } else {
        console.warn("[POS:stock] sin pisoId — solo polling");
    }

    // Polling como respaldo para bodega y desconexiones prolongadas
    setInterval(refrescarStock, FALLBACK_MS);

    // Refrescar inmediatamente tras una venta (el WS puede tardar ms)
    document.addEventListener("pago-exito", () => {
        console.log("[POS:stock] pago-exito → refrescando stock");
        refrescarStock();
    });
}
