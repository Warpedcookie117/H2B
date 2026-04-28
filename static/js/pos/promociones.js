// promociones.js — Detección y aplicación de promociones en el POS

import { carrito } from "./core.js";
import { agregarRegalo } from "./carrito.js";
import { mostrarAlertaUI } from "./ui.js";

// Promos de monto: solo una vez por sesión
const promosVistasGlobal = new Set();

// Cola para mostrar modales uno a la vez
// Cada entrada: { promo, itemIdx, pendingCount }
let modalQueue   = [];
let modalOcupado = false;


// ============================================================
// Init
// ============================================================

export function initPromociones() {
    document.addEventListener("pos:producto-agregado", (e) => {
        const { subcategoria_id, cat_padre_id } = e.detail;
        checkPromocionesCategoria(subcategoria_id, cat_padre_id);
    });

    document.addEventListener("pos:total-actualizado", (e) => {
        checkPromocionMonto(e.detail.total);
        checkPromocionMontoCat();
    });

    document.addEventListener("pos:carrito-limpiado", () => {
        promosVistasGlobal.clear();
        modalQueue   = [];
        modalOcupado = false;
        _cerrarModal();
    });
}


// ============================================================
// Categoría — dispara SIEMPRE que se agrega un producto match
// ============================================================

function checkPromocionesCategoria(subcategoria_id, cat_padre_id) {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "categoria" &&
        (p.categoria_disparadora_id == subcategoria_id ||
         (cat_padre_id && p.categoria_disparadora_id == cat_padre_id))
    );
    if (!promos.length) return;

    // Índice del ítem recién agregado/incrementado
    let itemIdx = -1;
    for (let i = carrito.length - 1; i >= 0; i--) {
        const it = carrito[i];
        if (!it.es_regalo && !it.es_servicio &&
            (it.subcategoria_id == subcategoria_id || it.cat_padre_id == cat_padre_id)) {
            itemIdx = i;
            break;
        }
    }

    // pendingCount = 0 → trigger fresco, no viene del badge
    promos.forEach(promo => encolarPromo(promo, itemIdx, 0));
}


// ============================================================
// Monto por categoría — solo una vez por sesión
// ============================================================

function checkPromocionMontoCat() {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "monto_categoria" &&
        !promosVistasGlobal.has(p.id)
    );
    if (!promos.length) return;

    for (const promo of promos) {
        const catId = promo.categoria_disparadora_id;
        let subtotalCat = 0;
        for (const item of carrito) {
            if (item.es_regalo || item.es_servicio) continue;
            if (item.subcategoria_id == catId || item.cat_padre_id == catId) {
                subtotalCat += (Number(item.precio_aplicado) || 0) * (item.cantidad || 1);
            }
        }
        if (parseFloat(promo.monto_minimo) <= subtotalCat) {
            promosVistasGlobal.add(promo.id);
            encolarPromo(promo, -1, 0);
        }
    }
}


// ============================================================
// Monto — solo una vez por sesión
// ============================================================

function checkPromocionMonto(total) {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "monto" &&
        !promosVistasGlobal.has(p.id) &&
        parseFloat(p.monto_minimo) <= total
    );

    promos.forEach(promo => {
        promosVistasGlobal.add(promo.id);
        encolarPromo(promo, -1, 0);
    });
}


// ============================================================
// Cola de modales
// ============================================================

function encolarPromo(promo, itemIdx, pendingCount) {
    modalQueue.push({ promo, itemIdx, pendingCount });
    if (!modalOcupado) procesarSiguiente();
}

async function procesarSiguiente() {
    if (!modalQueue.length) {
        modalOcupado = false;
        return;
    }
    modalOcupado = true;
    const { promo, itemIdx, pendingCount } = modalQueue.shift();
    await procesarPromo(promo, itemIdx, pendingCount);
}

async function procesarPromo(promo, itemIdx, pendingCount) {
    if (promo.tipo_resultado === "regalo_fijo") {
        await autoAgregarRegalo(promo, itemIdx);
        procesarSiguiente();
    } else {
        await mostrarModalRegalo(promo, itemIdx, pendingCount);
        // procesarSiguiente() se llama desde selección o desde omitirRegalo
    }
}


// ============================================================
// Regalo fijo — auto-agregar
// ============================================================

async function autoAgregarRegalo(promo, itemIdx = -1) {
    try {
        const r    = await fetch(`/ventas/promociones/productos-regalo/${promo.id}/`);
        const data = await r.json();
        if (data.productos.length) {
            const p = data.productos[0];
            const parentId = (itemIdx >= 0 && carrito[itemIdx]) ? carrito[itemIdx].id : null;
            agregarRegalo(p.id, p.nombre, promo.nombre, promo.id, parentId);
            mostrarAlertaUI(`🎁 ¡${p.nombre} de regalo con tu compra!`, "promo");
        }
    } catch {
        // silencioso
    }
}


// ============================================================
// Regalo variante — modal con atributos, buscador y contador
// ============================================================

async function mostrarModalRegalo(promo, itemIdx, pendingCount) {
    const modal     = document.getElementById("modal-regalo");
    const titulo    = document.getElementById("regalo-promo-nombre");
    const opciones  = document.getElementById("regalo-opciones");
    const buscar    = document.getElementById("regalo-buscar");
    const infoEl    = document.getElementById("regalo-pendientes-info");
    if (!modal) return;

    titulo.textContent      = promo.nombre;
    opciones.innerHTML      = `<p style="color:#6b7280;font-size:.875rem;font-weight:600;">Cargando opciones…</p>`;
    if (buscar) buscar.value = "";

    // Contador de pendientes (solo cuando viene del badge)
    if (infoEl) {
        if (pendingCount > 0) {
            infoEl.textContent = `${pendingCount} regalo${pendingCount > 1 ? "s" : ""} pendiente${pendingCount > 1 ? "s" : ""} por asignar`;
            infoEl.style.display = "";
        } else {
            infoEl.style.display = "none";
        }
    }

    modal.dataset.promoId      = promo.id;
    modal.dataset.promoNombre  = promo.nombre;
    modal.dataset.itemIdx      = itemIdx;
    modal.dataset.pendingCount = pendingCount;
    modal.style.display        = "flex";

    try {
        const r    = await fetch(`/ventas/promociones/productos-regalo/${promo.id}/`);
        const data = await r.json();

        if (!data.productos.length) {
            opciones.innerHTML = `<p style="color:#ef4444;font-weight:700;font-size:.875rem;">Sin productos disponibles para este regalo.</p>`;
            return;
        }

        _renderOpciones(data.productos, promo, itemIdx, pendingCount);

        if (buscar) {
            buscar.oninput = () => _filtrarOpciones(buscar.value);
            setTimeout(() => buscar.focus(), 60);
        }
    } catch {
        opciones.innerHTML = `<p style="color:#ef4444;font-weight:700;font-size:.875rem;">Error al cargar las opciones.</p>`;
    }
}

function _normalizar(t) {
    return t.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function _filtrarOpciones(texto) {
    const txt = _normalizar(texto);
    document.querySelectorAll(".regalo-opcion-btn").forEach(btn => {
        const label = _normalizar(btn.dataset.label || "");
        btn.style.display = label.includes(txt) ? "" : "none";
    });
}

function _renderOpciones(productos, promo, itemIdx, pendingCount) {
    const modal   = document.getElementById("modal-regalo");
    const opciones = document.getElementById("regalo-opciones");
    opciones.innerHTML = "";

    productos.forEach(p => {
        const attrEntries = Object.entries(p.atributos || {});
        const attrHtml    = attrEntries.map(([k, v]) =>
            `<span style="background:#EDE7FF;border:1px solid #111;padding:0 4px;border-radius:2px;">${k}: <strong>${v}</strong></span>`
        ).join("&nbsp;");

        const stockTxt = p.stock != null ? `Stock: ${p.stock}` : "";
        const label    = [p.nombre, ...Object.values(p.atributos || {})].join(" ");

        const btn = document.createElement("button");
        btn.className     = "regalo-opcion-btn";
        btn.dataset.label = label;
        btn.style.cssText = [
            "width:100%", "border:3px solid black", "background:#00F5D4",
            "font-weight:900", "padding:.6rem 1rem", "box-shadow:3px 3px 0 0 black",
            "cursor:pointer", "text-align:left",
            "transition:transform .1s,box-shadow .1s",
            "display:flex", "flex-direction:column", "gap:.2rem",
        ].join(";");

        btn.innerHTML = `
            <span style="font-size:.9rem;text-transform:uppercase;letter-spacing:.04em;">${p.nombre}</span>
            ${attrHtml ? `<span style="font-size:.78rem;font-weight:600;color:#1e293b;text-transform:none;display:flex;flex-wrap:wrap;gap:.3rem;">${attrHtml}</span>` : ""}
            ${stockTxt ? `<span style="font-size:.72rem;font-weight:500;color:#4b5563;text-transform:none;">${stockTxt}</span>` : ""}
        `;

        btn.onmouseover = () => { btn.style.transform = "translate(-1px,-1px)"; btn.style.boxShadow = "5px 5px 0 0 black"; };
        btn.onmouseout  = () => { btn.style.transform = ""; btn.style.boxShadow = "3px 3px 0 0 black"; };

        btn.onclick = () => {
            const parentId = (itemIdx >= 0 && carrito[itemIdx]) ? carrito[itemIdx].id : null;
            agregarRegalo(p.id, p.nombre, promo.nombre, promo.id, parentId);

            // Si el modal vino del badge (pendingCount > 0), descontar uno del pendiente
            const pc = parseInt(modal?.dataset.pendingCount ?? "0");
            if (pc > 0) _decrementarPendiente(itemIdx, promo.id);

            _cerrarModal();
            mostrarAlertaUI(`🎁 ¡${p.nombre} agregado de regalo!`, "promo");
            procesarSiguiente();
        };

        opciones.appendChild(btn);
    });
}

// Decrementa la cantidad de un regalo pendiente; lo elimina si llega a 0
function _decrementarPendiente(itemIdx, promoId) {
    if (itemIdx < 0 || !carrito[itemIdx]?.promos_pendientes) return;
    const pp = carrito[itemIdx].promos_pendientes.find(p => p.id === promoId);
    if (!pp) return;
    pp.cantidad--;
    if (pp.cantidad <= 0) {
        carrito[itemIdx].promos_pendientes = carrito[itemIdx].promos_pendientes.filter(p => p.id !== promoId);
    }
    document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
}


// ============================================================
// Cerrar modal (interno)
// ============================================================

function _cerrarModal() {
    const modal = document.getElementById("modal-regalo");
    if (modal) modal.style.display = "none";
}


// ============================================================
// "Sin regalo" — marca promo pendiente en el ítem del carrito
// ============================================================

window.omitirRegalo = function () {
    const modal = document.getElementById("modal-regalo");
    if (!modal) return;

    const itemIdx     = parseInt(modal.dataset.itemIdx     ?? "-1");
    const promoId     = parseInt(modal.dataset.promoId     ?? "0");
    const promoNombre = modal.dataset.promoNombre || "";
    const pendingCount = parseInt(modal.dataset.pendingCount ?? "0");

    if (pendingCount === 0) {
        // Trigger fresco: el cajero omite → registrar como pendiente
        if (itemIdx >= 0 && carrito[itemIdx] && promoId) {
            if (!carrito[itemIdx].promos_pendientes) carrito[itemIdx].promos_pendientes = [];
            const existing = carrito[itemIdx].promos_pendientes.find(pp => pp.id === promoId);
            if (existing) {
                existing.cantidad++;
            } else {
                carrito[itemIdx].promos_pendientes.push({ id: promoId, nombre: promoNombre, cantidad: 1 });
            }
            document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
        }
    }
    // Si vino del badge (pendingCount > 0) y omite de nuevo → no cambiar la cantidad,
    // el regalo sigue pendiente tal como estaba.

    _cerrarModal();
    procesarSiguiente();
};

// Click fuera también omite
window.cerrarModalRegalo = window.omitirRegalo;


// ============================================================
// Apertura manual desde badge del carrito
// ============================================================

window.abrirRegaloManual = function (promoId, promoNombre, itemIdx) {
    const promo = window.PROMOCIONES?.find(p => p.id === promoId);
    if (!promo) return;

    const pp           = carrito[itemIdx]?.promos_pendientes?.find(p => p.id === promoId);
    const pendingCount = pp?.cantidad || 0;

    encolarPromo(promo, itemIdx, pendingCount);
};
