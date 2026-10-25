// carrito.js — Lógica pura del carrito

import { aplicarPreciosGlobales } from "./precios.js";
import { aplicarOfertas } from "./ofertas.js";
import { actualizarTotales } from "./totales.js";
import { onCarritoActualizado, setLastAddedId, piezasItem } from "./core.js";

// Estado global del carrito (viene de core.js)
import { carrito } from "./core.js";

console.log("[POS:carrito] Módulo cargado");


// ============================================================
// 1. Agregar producto
// ============================================================

export function agregarProducto(id, nombre, precios, stock_piso, stock_bodega, subcategoria_id = null, cat_padre_id = null, atributos = {}) {
    console.log(`[POS:carrito] agregarProducto → id=${id} nombre="${nombre}" precios=`, precios, `stock_piso=${stock_piso} stock_bodega=${stock_bodega}`);

    if (!id || !precios?.men) {
        console.warn("[POS:carrito] agregarProducto RECHAZADO — id o precio menudeo inválido", { id, precios });
        return;
    }

    // Escanear otra vez suma una PIEZA: no se suma al renglón de la caja.
    const existente = carrito.find(p => p.id === id && !p.es_regalo && !p.presentacion);

    if (existente) {
        existente.cantidad++;
        console.log(`[POS:carrito] producto existente, nueva cantidad: ${existente.cantidad}`);
    } else {
        setLastAddedId(id);
        carrito.push({
            id,
            nombre,
            cantidad: 1,
            modo_precio: "AUTO",
            precios,
            precio_aplicado: precios.men,
            modo_resuelto: "MEN",
            stock_piso: stock_piso ?? 0,
            stock_bodega: stock_bodega ?? 0,
            subcategoria_id,
            cat_padre_id,
            atributos,
        });
        console.log(`[POS:carrito] producto nuevo agregado. Total items en carrito: ${carrito.length}`);
    }

    // Diagnóstico: mide cada eslabón de la cadena que corre al agregar, para
    // ver cuál traba (sospecha: renderizar el carrito dispara el observador de
    // Tailwind-CDN sobre las 3400 cards).
    window.__posPerf?.marca(`agregar al carrito id=${id}`);
    const _t = (label, fn) => {
        const t0 = performance.now();
        fn();
        const dt = performance.now() - t0;
        if (dt > 30) console.warn(`[POS:perf] ⏱️ [agregar] ${label} tardó ${dt.toFixed(0)}ms`);
    };

    _t("aplicarPreciosGlobales", aplicarPreciosGlobales);
    _t("aplicarOfertas",        aplicarOfertas);
    _t("actualizarTotales",     actualizarTotales);
    _t("onCarritoActualizado (render carrito)", onCarritoActualizado);
    _t("evento pos:producto-agregado (promos)", () => {
        document.dispatchEvent(new CustomEvent("pos:producto-agregado", {
            detail: { subcategoria_id, cat_padre_id }
        }));
    });
}



// ============================================================
// 2. Eliminar producto
// ============================================================

export function eliminarProducto(index) {
    const item = carrito[index];
    console.log(`[POS:carrito] eliminarProducto → idx=${index} item="${item?.nombre}" es_regalo=${item?.es_regalo}`);

    if (item?.es_regalo && item.promo_id != null && item.parent_product_id != null) {
        const padre = carrito.find(p => !p.es_regalo && !p.es_servicio && p.id === item.parent_product_id);
        if (padre) {
            if (!padre.promos_pendientes) padre.promos_pendientes = [];
            const pp = padre.promos_pendientes.find(p => p.id === item.promo_id);
            if (pp) {
                pp.cantidad += item.cantidad;
            } else {
                padre.promos_pendientes.push({ id: item.promo_id, nombre: item.promo_nombre, cantidad: item.cantidad });
            }
            console.log(`[POS:carrito] regalo eliminado → pendiente devuelto al padre "${padre.nombre}"`);
        }
    } else if (item && !item.es_regalo && !item.es_servicio) {
        const regalosEliminados = carrito.filter((r, i) => i !== index && r.es_regalo && r.parent_product_id === item.id);
        if (regalosEliminados.length) {
            console.log(`[POS:carrito] eliminando ${regalosEliminados.length} regalo(s) vinculado(s) a "${item.nombre}"`);
        }
        for (let i = carrito.length - 1; i >= 0; i--) {
            if (i !== index && carrito[i].es_regalo && carrito[i].parent_product_id === item.id) {
                carrito.splice(i, 1);
            }
        }
    }

    carrito.splice(index, 1);
    console.log(`[POS:carrito] carrito tras eliminar: ${carrito.length} items`);
    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 3. Cambiar cantidad
// ============================================================

export function cambiarCantidad(index, nuevaCantidad) {
    if (!carrito[index]) {
        console.warn(`[POS:carrito] cambiarCantidad → idx=${index} NO EXISTE`);
        return;
    }

    const anterior = carrito[index].cantidad;
    carrito[index].cantidad = Math.max(1, nuevaCantidad);
    console.log(`[POS:carrito] cambiarCantidad → "${carrito[index].nombre}" idx=${index}: ${anterior} → ${carrito[index].cantidad}`);

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 4. Cambiar modo de precio (MEN / MAY / DOC / AUTO)
// ============================================================

export function cambiarModoPrecio(index, modo) {
    if (!carrito[index]) {
        console.warn(`[POS:carrito] cambiarModoPrecio → idx=${index} NO EXISTE`);
        return;
    }

    // MEN/MAY/DOC/AUTO en un renglón de caja lo regresa a piezas.
    if (carrito[index].presentacion) {
        elegirPresentacion(index, null, modo);
        return;
    }

    const anterior = carrito[index].modo_precio;
    carrito[index].modo_precio = modo;
    console.log(`[POS:carrito] cambiarModoPrecio → "${carrito[index].nombre}" idx=${index}: ${anterior} → ${modo}`);

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 4b. Precio por cantidad (Media docena, Decena, Caja)
// ============================================================

// Pasa el renglón a una presentación (presentacionId) o lo regresa a piezas
// (null, con modoPieza). La cantidad se conserva: 3 piezas → 3 cajas. Si ya
// hay otro renglón del mismo producto vendido igual, se juntan.
export function elegirPresentacion(index, presentacionId, modoPieza = "AUTO") {
    const item = carrito[index];
    if (!item || item.es_regalo || item.es_servicio) return;

    const pres = presentacionId == null
        ? null
        : (item.precios?.pres || []).find(p => p.id === presentacionId);
    if (presentacionId != null && !pres) {
        console.warn(`[POS:carrito] elegirPresentacion → presentación ${presentacionId} no existe en "${item.nombre}"`);
        return;
    }

    const destino = carrito.findIndex((p, i) =>
        i !== index && p.id === item.id && !p.es_regalo && !p.es_servicio &&
        (p.presentacion?.id ?? null) === (pres?.id ?? null)
    );

    if (destino >= 0) {
        carrito[destino].cantidad += item.cantidad;
        if (!pres) carrito[destino].modo_precio = modoPieza;
        carrito.splice(index, 1);
        console.log(`[POS:carrito] elegirPresentacion → "${item.nombre}" juntado con el renglón ${destino}`);
    } else {
        item.presentacion      = pres ? { ...pres } : null;
        item.modo_precio       = pres ? "PRES" : modoPieza;
        item.oferta_activa     = null;
        item.precio_sin_oferta = null;
        if (pres) item.promos_pendientes = [];   // la caja no lleva regalo
        console.log(`[POS:carrito] elegirPresentacion → "${item.nombre}" ahora ${pres ? pres.nombre : "por pieza"}`);
    }

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}

// Precios por cantidad de un producto cambiaron (websocket o cuenta
// pendiente vieja): los renglones toman el precio nuevo, y si una
// presentación ya no existe ese renglón vuelve a piezas (3 cajas de 24 =
// 72 piezas) para no perder lo que se iba a vender. Regresa los nombres
// de las que ya no existen, para avisarle a la cajera.
export function actualizarPresentaciones(id, lista, { recalcular = true } = {}) {
    const quitadas = [];
    for (const item of carrito) {
        if (item.id !== id || item.es_regalo || item.es_servicio) continue;
        if (item.precios) item.precios.pres = lista;
        if (!item.presentacion) continue;
        const nueva = lista.find(p => p.id === item.presentacion.id);
        if (nueva) {
            item.presentacion = { ...nueva };
        } else {
            quitadas.push(`${item.nombre} (${item.presentacion.nombre.toLowerCase()})`);
            item.cantidad     = piezasItem(item);
            item.presentacion = null;
            item.modo_precio  = "AUTO";
        }
    }
    if (recalcular) {
        aplicarPreciosGlobales();
        aplicarOfertas();
        actualizarTotales();
        onCarritoActualizado();
    }
    return quitadas;
}


// ============================================================
// 5. Agregar servicio (precio libre, sin inventario)
// ============================================================

export function agregarServicio(nombre, precio) {
    console.log(`[POS:carrito] agregarServicio → nombre="${nombre}" precio=${precio}`);
    carrito.push({
        id:             `srv_${Date.now()}`,
        es_servicio:    true,
        nombre:         nombre,
        cantidad:       1,
        precio_aplicado: precio,
        stock_piso:     Infinity,
        stock_bodega:   Infinity,
    });
    console.log(`[POS:carrito] servicio agregado. Total items: ${carrito.length}`);

    actualizarTotales();
    onCarritoActualizado();
}


// ============================================================
// 6. Agregar regalo
// ============================================================

export function agregarRegalo(id, nombre, promo_nombre, promo_id = null, parent_product_id = null) {
    console.log(`[POS:carrito] agregarRegalo → id=${id} nombre="${nombre}" promo="${promo_nombre}" promo_id=${promo_id} parent=${parent_product_id}`);

    const yaExiste = carrito.find(p =>
        p.id === id && p.es_regalo &&
        p.promo_id === promo_id &&
        p.parent_product_id === parent_product_id
    );
    if (yaExiste) {
        yaExiste.cantidad++;
        console.log(`[POS:carrito] regalo existente, nueva cantidad: ${yaExiste.cantidad}`);
        actualizarTotales();
        onCarritoActualizado();
        return;
    }

    carrito.push({
        id,
        es_regalo: true,
        promo_nombre,
        promo_id,
        parent_product_id,
        nombre,
        cantidad: 1,
        precio_aplicado: 0,
        stock_piso: Infinity,
        stock_bodega: Infinity,
    });
    console.log(`[POS:carrito] regalo nuevo agregado. Total items: ${carrito.length}`);

    actualizarTotales();
    onCarritoActualizado();
}


// ============================================================
// 7. Cobro rápido (producto sin registro en sistema)
// ============================================================

export function agregarCobroRapido(precio) {
    console.log(`[POS:carrito] agregarCobroRapido → precio=${precio}`);
    carrito.push({
        id:              `cr_${Date.now()}`,
        es_cobro_rapido: true,
        es_servicio:     true,   // reutiliza la ruta de servicio en el backend
        nombre:          "Prod. sin registro",
        cantidad:        1,
        precio_aplicado: precio,
        stock_piso:      Infinity,
        stock_bodega:    Infinity,
    });
    console.log(`[POS:carrito] cobro rápido agregado. Total items: ${carrito.length}`);
    actualizarTotales();
    onCarritoActualizado();
}


export function limpiarCarrito() {
    console.log(`[POS:carrito] limpiarCarrito — limpiando ${carrito.length} items`);
    carrito.length = 0;
    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
    document.dispatchEvent(new CustomEvent("pos:carrito-limpiado"));
    console.log("[POS:carrito] carrito limpiado ✓");
}


// ============================================================
// 8. Cuentas pendientes — snapshot y restauración del carrito
// ============================================================

// Copia serializable del carrito actual, para guardarla como cuenta
// pendiente (localStorage) sin conservar referencias vivas.
export function obtenerSnapshotCarrito() {
    return JSON.parse(JSON.stringify(carrito));
}

// Reemplaza el carrito activo por `items` (típicamente una cuenta
// pendiente restaurada) y vuelve a correr la misma cadena que agregar/
// eliminar productos, para que precios, ofertas, totales y el render
// queden consistentes.
export function cargarCarrito(items) {
    console.log(`[POS:carrito] cargarCarrito — cargando ${items.length} items`);
    carrito.length = 0;
    for (const item of items) carrito.push(item);

    // Los precios por cantidad pudieron cambiar desde que se guardó la
    // cuenta: se toman los de la card de hoy.
    const quitadas = [];
    for (const id of new Set(carrito.filter(i => i.presentacion).map(i => i.id))) {
        const card = document.querySelector(`.producto-item[data-id="${id}"]`);
        quitadas.push(...actualizarPresentaciones(id, leerPresentaciones(card), { recalcular: false }));
    }
    if (quitadas.length) {
        document.dispatchEvent(new CustomEvent("pos:presentaciones-quitadas", { detail: { quitadas } }));
    }

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}


/** Precios por cantidad de una card del POS (data-presentaciones), [] si no tiene. */
export function leerPresentaciones(card) {
    if (!card?.dataset.presentaciones) return [];
    try {
        const lista = JSON.parse(card.dataset.presentaciones);
        return Array.isArray(lista) ? lista : [];
    } catch {
        return [];
    }
}
