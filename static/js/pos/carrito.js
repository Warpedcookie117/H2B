// carrito.js — Lógica pura del carrito

import { aplicarPreciosGlobales } from "./precios.js";
import { actualizarTotales } from "./totales.js";
import { onCarritoActualizado } from "./core.js";

// Estado global del carrito (viene de core.js)
import { carrito } from "./core.js";


// ============================================================
// 1. Agregar producto
// ============================================================

export function agregarProducto(id, nombre, precios, stock_piso, stock_bodega) {
    if (!id || !precios?.men) return;

    const existente = carrito.find(p => p.id === id);

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
            stock_bodega: stock_bodega ?? 0
        });
    }

    aplicarPreciosGlobales();
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 2. Eliminar producto
// ============================================================

export function eliminarProducto(index) {
    carrito.splice(index, 1);
    aplicarPreciosGlobales();
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
    actualizarTotales();
    onCarritoActualizado();
}



// ============================================================
// 5. Limpiar carrito
// ============================================================

export function limpiarCarrito() {
    carrito.length = 0;
    aplicarPreciosGlobales();
    actualizarTotales();
    onCarritoActualizado();
}
