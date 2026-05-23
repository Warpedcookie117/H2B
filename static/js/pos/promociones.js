// promociones.js — Detección y aplicación de promociones en el POS

import { carrito } from "./core.js";
import { agregarRegalo } from "./carrito.js";
import { mostrarAlertaUI } from "./ui.js";

console.log("[POS:promociones] Módulo cargado");

const promosVistasGlobal = new Set();

let modalQueue   = [];
let modalOcupado = false;


// ============================================================
// Init
// ============================================================

export function initPromociones() {
    console.log(`[POS:promociones] initPromociones — promociones disponibles: ${(window.PROMOCIONES || []).length}`);

    document.addEventListener("pos:producto-agregado", (e) => {
        const { subcategoria_id, cat_padre_id } = e.detail;
        console.log(`[POS:promociones] pos:producto-agregado → subcat=${subcategoria_id} catPadre=${cat_padre_id}`);
        checkPromocionesCategoria(subcategoria_id, cat_padre_id);
    });

    document.addEventListener("pos:total-actualizado", (e) => {
        console.log(`[POS:promociones] pos:total-actualizado → total=$${e.detail.total.toFixed(2)}`);
        checkPromocionMonto(e.detail.total);
        checkPromocionMontoCat();
    });

    document.addEventListener("pos:carrito-limpiado", () => {
        console.log("[POS:promociones] pos:carrito-limpiado → reseteando promos");
        promosVistasGlobal.clear();
        modalQueue   = [];
        modalOcupado = false;
        _cerrarModal();
    });
}


// ============================================================
// Categoría
// ============================================================

// Comparación case-insensitive — los atributos pueden guardarse con
// inconsistencias de capitalización (Kool vs KOOL) y la promo debe ser
// permisiva: si el dueño marcó "marca=KOOL" en el filtro y el producto
// está guardado como "Kool", igual debe disparar.
function _attrMatch(productoAttrs, nombre, valor) {
    if (!productoAttrs) return false;
    const valorAttr = productoAttrs[nombre]
        ?? productoAttrs[nombre?.toLowerCase()]
        ?? Object.entries(productoAttrs).find(([k]) => k.toLowerCase() === nombre.toLowerCase())?.[1];
    if (!valorAttr) return false;
    return String(valorAttr).toLowerCase() === String(valor).toLowerCase();
}

function _productoPasaFiltros(item, filtros) {
    if (!filtros?.length) return true;
    const attrs = item.atributos || {};
    return filtros.every(f => _attrMatch(attrs, f.nombre, f.valor));
}

function checkPromocionesCategoria(subcategoria_id, cat_padre_id) {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "categoria" &&
        (p.categoria_disparadora_id == subcategoria_id ||
         (cat_padre_id && p.categoria_disparadora_id == cat_padre_id))
    );
    if (!promos.length) return;

    console.log(`[POS:promociones] checkPromocionesCategoria → ${promos.length} promo(s) de categoría candidatas`);

    let itemIdx = -1;
    for (let i = carrito.length - 1; i >= 0; i--) {
        const it = carrito[i];
        if (!it.es_regalo && !it.es_servicio &&
            (it.subcategoria_id == subcategoria_id || it.cat_padre_id == cat_padre_id)) {
            itemIdx = i;
            break;
        }
    }
    if (itemIdx < 0) {
        console.log("[POS:promociones] no se encontró item disparador en carrito");
        return;
    }
    const itemDisparador = carrito[itemIdx];

    console.log(`[POS:promociones] itemIdx disparador: ${itemIdx} (producto ${itemDisparador.id})`);
    promos.forEach(promo => {
        if (!_productoPasaFiltros(itemDisparador, promo.filtros_disparador)) {
            console.log(`[POS:promociones] promo "${promo.nombre}" descartada — no pasa filtros del disparador`);
            return;
        }
        console.log(`[POS:promociones] encolar promo: "${promo.nombre}" (${promo.tipo_resultado})`);
        encolarPromo(promo, itemIdx, 0);
    });
}


// ============================================================
// Monto por categoría
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
        console.log(`[POS:promociones] checkPromocionMontoCat "${promo.nombre}": subtotal=$${subtotalCat.toFixed(2)} mínimo=$${promo.monto_minimo}`);
        if (parseFloat(promo.monto_minimo) <= subtotalCat) {
            console.log(`[POS:promociones] ✓ promo monto_categoria ACTIVADA: "${promo.nombre}"`);
            promosVistasGlobal.add(promo.id);
            encolarPromo(promo, -1, 0);
        }
    }
}


// ============================================================
// Monto
// ============================================================

function checkPromocionMonto(total) {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "monto" &&
        !promosVistasGlobal.has(p.id) &&
        parseFloat(p.monto_minimo) <= total
    );

    promos.forEach(promo => {
        console.log(`[POS:promociones] ✓ promo monto ACTIVADA: "${promo.nombre}" (mínimo=$${promo.monto_minimo} total=$${total.toFixed(2)})`);
        promosVistasGlobal.add(promo.id);
        encolarPromo(promo, -1, 0);
    });
}


// ============================================================
// Cola de modales
// ============================================================

function encolarPromo(promo, itemIdx, pendingCount) {
    console.log(`[POS:promociones] encolarPromo: "${promo.nombre}" queue.length=${modalQueue.length} ocupado=${modalOcupado}`);
    modalQueue.push({ promo, itemIdx, pendingCount });
    if (!modalOcupado) procesarSiguiente();
}

async function procesarSiguiente() {
    if (!modalQueue.length) {
        console.log("[POS:promociones] cola vacía — modalOcupado=false");
        modalOcupado = false;
        return;
    }
    modalOcupado = true;
    const { promo, itemIdx, pendingCount } = modalQueue.shift();
    console.log(`[POS:promociones] procesando promo "${promo.nombre}" tipo_resultado=${promo.tipo_resultado} itemIdx=${itemIdx} pendingCount=${pendingCount}`);
    await procesarPromo(promo, itemIdx, pendingCount);
}

async function procesarPromo(promo, itemIdx, pendingCount) {
    if (promo.tipo_resultado === "regalo_fijo") {
        await autoAgregarRegalo(promo, itemIdx);
        procesarSiguiente();
    } else {
        await mostrarModalRegalo(promo, itemIdx, pendingCount);
    }
}


// ============================================================
// Regalo fijo — auto-agregar
// ============================================================

async function autoAgregarRegalo(promo, itemIdx = -1) {
    console.log(`[POS:promociones] autoAgregarRegalo → promo="${promo.nombre}" itemIdx=${itemIdx}`);
    try {
        const triggerId = (itemIdx >= 0 && carrito[itemIdx]) ? carrito[itemIdx].id : null;
        const url = triggerId
            ? `/ventas/promociones/productos-regalo/${promo.id}/?trigger_producto_id=${triggerId}`
            : `/ventas/promociones/productos-regalo/${promo.id}/`;
        const r    = await fetch(url);
        const data = await r.json();
        console.log(`[POS:promociones] productos regalo recibidos: ${data.productos.length}`);
        if (data.productos.length) {
            const p = data.productos[0];
            const parentId = (itemIdx >= 0 && carrito[itemIdx]) ? carrito[itemIdx].id : null;
            console.log(`[POS:promociones] auto-agregando regalo "${p.nombre}" parent=${parentId}`);
            agregarRegalo(p.id, p.nombre, promo.nombre, promo.id, parentId);
            mostrarAlertaUI(`🎁 ¡${p.nombre} de regalo con tu compra!`, "promo");
        }
    } catch (e) {
        console.warn("[POS:promociones] autoAgregarRegalo ERROR:", e);
    }
}


// ============================================================
// Regalo variante — modal
// ============================================================

async function mostrarModalRegalo(promo, itemIdx, pendingCount) {
    console.log(`[POS:promociones] mostrarModalRegalo → promo="${promo.nombre}" itemIdx=${itemIdx} pendingCount=${pendingCount}`);
    const modal     = document.getElementById("modal-regalo");
    const titulo    = document.getElementById("regalo-promo-nombre");
    const opciones  = document.getElementById("regalo-opciones");
    const buscar    = document.getElementById("regalo-buscar");
    const infoEl    = document.getElementById("regalo-pendientes-info");
    if (!modal) {
        console.warn("[POS:promociones] modal-regalo NO ENCONTRADO en DOM");
        return;
    }

    titulo.textContent      = promo.nombre;
    opciones.innerHTML      = `<p style="color:#6b7280;font-size:.875rem;font-weight:600;">Cargando opciones…</p>`;
    if (buscar) buscar.value = "";

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
    console.log("[POS:promociones] modal-regalo abierto ✓");

    try {
        const triggerId = (itemIdx >= 0 && carrito[itemIdx]) ? carrito[itemIdx].id : null;
        const url = triggerId
            ? `/ventas/promociones/productos-regalo/${promo.id}/?trigger_producto_id=${triggerId}`
            : `/ventas/promociones/productos-regalo/${promo.id}/`;
        const r    = await fetch(url);
        const data = await r.json();
        console.log(`[POS:promociones] opciones de regalo: ${data.productos.length}`);

        if (!data.productos.length) {
            opciones.innerHTML = `<p style="color:#ef4444;font-weight:700;font-size:.875rem;">Sin productos disponibles para este regalo.</p>`;
            return;
        }

        _renderOpciones(data.productos, promo, itemIdx, pendingCount);

        if (buscar) {
            buscar.oninput = () => _filtrarOpciones(buscar.value);
            setTimeout(() => buscar.focus(), 60);
        }
    } catch (e) {
        console.error("[POS:promociones] error cargando opciones regalo:", e);
        opciones.innerHTML = `<p style="color:#ef4444;font-weight:700;font-size:.875rem;">Error al cargar las opciones.</p>`;
    }
}

function _normalizar(t) {
    return t.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
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
            console.log(`[POS:promociones] regalo seleccionado: "${p.nombre}" parentId=${parentId}`);
            agregarRegalo(p.id, p.nombre, promo.nombre, promo.id, parentId);

            const pc = parseInt(modal?.dataset.pendingCount ?? "0");
            if (pc > 0) _decrementarPendiente(itemIdx, promo.id);

            _cerrarModal();
            mostrarAlertaUI(`🎁 ¡${p.nombre} agregado de regalo!`, "promo");
            procesarSiguiente();
        };

        opciones.appendChild(btn);
    });
}

function _decrementarPendiente(itemIdx, promoId) {
    if (itemIdx < 0 || !carrito[itemIdx]?.promos_pendientes) return;
    const pp = carrito[itemIdx].promos_pendientes.find(p => p.id === promoId);
    if (!pp) return;
    pp.cantidad--;
    console.log(`[POS:promociones] pendiente decrementado: promo=${promoId} restante=${pp.cantidad}`);
    if (pp.cantidad <= 0) {
        carrito[itemIdx].promos_pendientes = carrito[itemIdx].promos_pendientes.filter(p => p.id !== promoId);
    }
    document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
}

function _cerrarModal() {
    const modal = document.getElementById("modal-regalo");
    if (modal) {
        modal.style.display = "none";
        console.log("[POS:promociones] modal-regalo cerrado");
    }
}

window.omitirRegalo = function () {
    const modal = document.getElementById("modal-regalo");
    if (!modal) return;

    const itemIdx     = parseInt(modal.dataset.itemIdx     ?? "-1");
    const promoId     = parseInt(modal.dataset.promoId     ?? "0");
    const promoNombre = modal.dataset.promoNombre || "";
    const pendingCount = parseInt(modal.dataset.pendingCount ?? "0");

    console.log(`[POS:promociones] omitirRegalo → itemIdx=${itemIdx} promoId=${promoId} pendingCount=${pendingCount}`);

    if (pendingCount === 0) {
        if (itemIdx >= 0 && carrito[itemIdx] && promoId) {
            if (!carrito[itemIdx].promos_pendientes) carrito[itemIdx].promos_pendientes = [];
            const existing = carrito[itemIdx].promos_pendientes.find(pp => pp.id === promoId);
            if (existing) {
                existing.cantidad++;
                console.log(`[POS:promociones] pendiente incrementado: "${promoNombre}" → ${existing.cantidad}`);
            } else {
                carrito[itemIdx].promos_pendientes.push({ id: promoId, nombre: promoNombre, cantidad: 1 });
                console.log(`[POS:promociones] nuevo pendiente registrado: "${promoNombre}"`);
            }
            document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
        }
    }

    _cerrarModal();
    procesarSiguiente();
};

window.cerrarModalRegalo = window.omitirRegalo;

window.abrirRegaloManual = function (promoId, promoNombre, itemIdx) {
    console.log(`[POS:promociones] abrirRegaloManual → promoId=${promoId} nombre="${promoNombre}" itemIdx=${itemIdx}`);
    const promo = window.PROMOCIONES?.find(p => p.id === promoId);
    if (!promo) {
        console.warn(`[POS:promociones] promo id=${promoId} NO encontrada en window.PROMOCIONES`);
        return;
    }

    const pp           = carrito[itemIdx]?.promos_pendientes?.find(p => p.id === promoId);
    const pendingCount = pp?.cantidad || 0;
    console.log(`[POS:promociones] abrirRegaloManual pendingCount=${pendingCount}`);

    encolarPromo(promo, itemIdx, pendingCount);
};
