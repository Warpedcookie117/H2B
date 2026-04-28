// carrito.js — Lógica pura del carrito

import { aplicarPreciosGlobales } from "./precios.js";
import { aplicarOfertas } from "./ofertas.js";
import { actualizarTotales } from "./totales.js";
import { onCarritoActualizado } from "./core.js";

// Estado global del carrito (viene de core.js)
import { carrito } from "./core.js";


// ============================================================
// 1. Agregar producto
// ============================================================

export function agregarProducto(id, nombre, precios, stock_piso, stock_bodega, subcategoria_id = null, cat_padre_id = null, atributos = {}) {
    if (!id || !precios?.men) return;

    const existente = carrito.find(p => p.id === id && !p.es_regalo);

    if (existente) {
        existente.cantidad++;
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

    if (item?.es_regalo && item.promo_id != null && item.parent_product_id != null) {
        // Regalo eliminado → devolver su cantidad como pendiente al producto padre
        const padre = carrito.find(p => !p.es_regalo && !p.es_servicio && p.id === item.parent_product_id);
        if (padre) {
            if (!padre.promos_pendientes) padre.promos_pendientes = [];
            const pp = padre.promos_pendientes.find(p => p.id === item.promo_id);
            if (pp) {
                pp.cantidad += item.cantidad;
            } else {
                padre.promos_pendientes.push({ id: item.promo_id, nombre: item.promo_nombre, cantidad: item.cantidad });
            }
        }
    } else if (item && !item.es_regalo && !item.es_servicio) {
        // Producto padre eliminado → quitar sus regalos vinculados del carrito
        for (let i = carrito.length - 1; i >= 0; i--) {
            if (i !== index && carrito[i].es_regalo && carrito[i].parent_product_id === item.id) {
                carrito.splice(i, 1);
            }
        }
    }

    carrito.splice(index, 1);
    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 3. Cambiar cantidad
// ============================================================

export function cambiarCantidad(index, nuevaCantidad) {
    if (!carrito[index]) return;

    carrito[index].cantidad = Math.max(1, nuevaCantidad);

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 4. Cambiar modo de precio (MEN / MAY / DOC / AUTO)
// ============================================================

export function cambiarModoPrecio(index, modo) {
    if (!carrito[index]) return;

    carrito[index].modo_precio = modo;

    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 5. Agregar servicio (precio libre, sin inventario)
// ============================================================

export function agregarServicio(nombre, precio) {
    carrito.push({
        id:             `srv_${Date.now()}`,
        es_servicio:    true,
        nombre:         nombre,
        cantidad:       1,
        precio_aplicado: precio,
        stock_piso:     Infinity,
        stock_bodega:   Infinity,
    });

    actualizarTotales();
    onCarritoActualizado();
}


// ============================================================
// 6. Limpiar carrito
// ============================================================

export function agregarRegalo(id, nombre, promo_nombre, promo_id = null, parent_product_id = null) {
    // Agrupar solo si son del mismo padre y misma promo
    const yaExiste = carrito.find(p =>
        p.id === id && p.es_regalo &&
        p.promo_id === promo_id &&
        p.parent_product_id === parent_product_id
    );
    if (yaExiste) {
        yaExiste.cantidad++;
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

    actualizarTotales();
    onCarritoActualizado();
}


export function limpiarCarrito() {
    carrito.length = 0;
    aplicarPreciosGlobales();
    aplicarOfertas();
    actualizarTotales();
    onCarritoActualizado();
    document.dispatchEvent(new CustomEvent("pos:carrito-limpiado"));
}
