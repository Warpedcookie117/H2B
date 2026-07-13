// stock.js — Stock en tiempo real via WebSocket + polling de respaldo

import { carrito } from "./core.js";
import { cargarImagenCard, refrescarGrid } from "./paginacion.js";

console.log("[POS:stock] Módulo cargado");

const URL_STOCK = "/ventas/stock-productos/";
const URL_CARD  = "/ventas/pos/producto-card/"; // + <id>/
const FALLBACK_MS = 5 * 60_000; // polling cada 5 min solo como respaldo

// IDs con un fetch de card en curso, para no insertar duplicados
const cardsEnVuelo = new Set();

// ============================================================
// Insertar en vivo una card que aún no existe en el POS
// (producto nuevo, trasladado a piso, o restock de algo agotado)
// ============================================================

async function insertarCardNueva(productoId) {
    const id = parseInt(productoId);
    if (document.querySelector(`.producto-item[data-id="${id}"]`)) return; // ya existe
    if (cardsEnVuelo.has(id)) return; // ya se está pidiendo

    cardsEnVuelo.add(id);
    try {
        const resp = await fetch(`${URL_CARD}${id}/`);
        if (resp.status !== 200) return; // 204 = no va en piso / inactivo

        const html = (await resp.text()).trim();
        if (!html) return;

        // Revalidar tras el await por si otro mensaje ya la creó
        if (document.querySelector(`.producto-item[data-id="${id}"]`)) return;

        const lista = document.getElementById("lista-productos");
        if (!lista) return;

        const tmp = document.createElement("template");
        tmp.innerHTML = html;
        const card = tmp.content.firstElementChild;
        if (!card) return;

        lista.appendChild(card);
        cargarImagenCard(card); // carga la imagen de inmediato
        refrescarGrid();        // recalcula paginación
        console.log(`[POS:stock] card NUEVA insertada id=${id}`);
    } catch (e) {
        console.warn(`[POS:stock] error insertando card nueva id=${id}:`, e);
    } finally {
        cardsEnVuelo.delete(id);
    }
}

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
            refrescarGrid();
        } else {
            card.dataset.stockPiso = pisoNuevo;
            if (bodegaNuevo !== null) card.dataset.stockBodega = bodegaNuevo;

            // Etiqueta visible "X disponibles en piso"
            const label = card.querySelector("[data-stock-label]");
            if (label) label.textContent = `${pisoNuevo} disponibles en piso`;

            console.log(`[POS:stock] producto id=${id} piso=${pisoNuevo}${bodegaNuevo !== null ? ` bodega=${bodegaNuevo}` : ""}`);
        }
    } else if (pisoNuevo > 0) {
        // No hay card y ahora hay stock en piso → producto nuevo / trasladado / restock
        insertarCardNueva(id);
    }

    const itemCarrito = carrito.find(i => i.id === id);
    if (itemCarrito) {
        itemCarrito.stock_piso = pisoNuevo;
        if (bodegaNuevo !== null) itemCarrito.stock_bodega = bodegaNuevo;
    }
}

// ============================================================
// Aplicar cambios del detalle del producto a la card
// (el buscador y el carrito leen estos data-attributes al agregar)
// ============================================================

function aplicarCambioProducto(d) {
    const id = parseInt(d.producto_id);
    const card = document.querySelector(`.producto-item[data-id="${id}"]`);

    // Producto desactivado → quitarlo del POS (igual que si se agotara)
    if (d.activo === false) {
        if (card) {
            card.remove();
            refrescarGrid();
            console.log(`[POS:stock] producto id=${id} desactivado → removido del POS`);
        }
        return;
    }

    if (!card) return;

    // dataset — lo que lee el buscador (nombre/código) y el carrito (precios/atributos)
    if (d.nombre !== undefined)          card.dataset.nombre = d.nombre;
    card.dataset.codigo = d.codigo_barras || "";
    if (d.precio_menudeo !== undefined)  card.dataset.men = d.precio_menudeo;
    if (d.precio_mayoreo !== undefined)  card.dataset.may = d.precio_mayoreo;
    card.dataset.doc = d.precio_docena || "";
    if (d.categoria_id != null)          card.dataset.subcategoria = d.categoria_id;
    if (d.categoria_padre_id != null)    card.dataset.catPadre = d.categoria_padre_id;
    if (d.atributos_json !== undefined)  card.dataset.atributos = d.atributos_json;

    // Texto visible
    const nombreEl = card.querySelector(".pos-producto-nombre");
    if (nombreEl && d.nombre !== undefined) nombreEl.textContent = d.nombre;

    const menEl = card.querySelector(".pos-producto-precio");
    if (menEl && d.precio_menudeo !== undefined)
        menEl.innerHTML = `$${d.precio_menudeo} <span class="pos-producto-sub">(MEN)</span>`;

    const mayEl = card.querySelector(".pos-producto-precio-may");
    if (mayEl && d.precio_mayoreo !== undefined)
        mayEl.innerHTML = `$${d.precio_mayoreo} <span class="pos-producto-sub">(MAY)</span>`;

    // Foto (puede venir vacía si no hay imagen)
    if (d.foto_url) {
        const img = card.querySelector(".pos-producto-img img");
        if (img) { img.src = d.foto_url; img.dataset.src = d.foto_url; }
    }

    console.log(`[POS:stock] card id=${id} actualizada vía WS (detalle)`);
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
        const msg = JSON.parse(e.data);

        // Cambio en el detalle del producto (nombre, precios, código, foto)
        if (msg.tipo === "producto_update") {
            console.log(`[POS:stock] WS producto_update → id=${msg.producto_id}`);
            aplicarCambioProducto(msg);
            return;
        }

        // Cambio de stock (default / mensajes legacy sin tipo)
        console.log(`[POS:stock] WS stock → producto_id=${msg.producto_id} cantidad=${msg.cantidad_actual}`);
        aplicarCambioStock(msg.producto_id, msg.cantidad_actual);
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
