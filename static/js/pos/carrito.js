// carrito.js — Lógica pura del carrito

import { aplicarPreciosGlobales } from "./precios.js";
import { aplicarOfertas } from "./ofertas.js";
import { actualizarTotales } from "./totales.js";
import { onCarritoActualizado } from "./core.js";

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

    const existente = carrito.find(p => p.id === id && !p.es_regalo);

    if (existente) {
        existente.cantidad++;
        console.log(`[POS:carrito] producto existente, nueva cantidad: ${existente.cantidad}`);
    } else {
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

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();

    document.dispatchEvent(new CustomEvent("pos:producto-agregado", {
        detail: { subcategoria_id, cat_padre_id }
    }));
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

    const anterior = carrito[index].modo_precio;
    carrito[index].modo_precio = modo;
    console.log(`[POS:carrito] cambiarModoPrecio → "${carrito[index].nombre}" idx=${index}: ${anterior} → ${modo}`);

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
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
