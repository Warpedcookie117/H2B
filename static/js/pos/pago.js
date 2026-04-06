// pago.js — Lógica pura del pago

import { carrito, totalConDescuento, descuentoActivo } from "./core.js";
import { getCookie } from "./core.js";
import { limpiarCarrito } from "./carrito.js";

// Callbacks que la UI registrará
export let onPagoError = () => {};
export let onPagoExito = () => {};
export let onPagoIniciado = () => {};
export let onPagoProcesado = () => {};

export function setPagoCallbacks({ error, exito, iniciado, procesado }) {
    if (error) onPagoError = error;
    if (exito) onPagoExito = exito;
    if (iniciado) onPagoIniciado = iniciado;
    if (procesado) onPagoProcesado = procesado;
}


// ============================================================
// 1. Validación de stock ANTES de cobrar
// ============================================================

export function validarStock() {
    if (carrito.length === 0) {
        return "No hay productos en el carrito";
    }

    for (const item of carrito) {
        if (item.cantidad <= item.stock_piso) continue;
        if (item.cantidad <= item.stock_bodega) continue;

        return `"${item.nombre}" no tiene stock suficiente`;
    }

    return null; // OK
}


// ============================================================
// 2. Validación del pago
// ============================================================

export function validarPago(efectivo, tarjeta) {
    const total = totalConDescuento();   // ← FIX: antes era la función sin ejecutar

    if (efectivo + tarjeta < total) {
        return "Pago insuficiente";
    }

    return null; // OK
}


// ============================================================
// 3. Procesar venta (llamar backend)
// ============================================================

export async function procesarPago(efectivo, tarjeta) {

    onPagoIniciado();

    // Payload EXACTO que espera el backend
    const payload = {
        carrito: carrito.map(p => ({
            producto_id: p.id,
            cantidad: Number(p.cantidad) || 1,
            precio_aplicado: Number(p.precio_aplicado) || Number(p.precios?.men) || 0
        })),
        pagado_efectivo: Number(efectivo) || 0,
        pagado_tarjeta: Number(tarjeta) || 0,
        descuento_10: Boolean(descuentoActivo)
    };

    const csrftoken = getCookie("csrftoken");

    try {
        const resp = await fetch("/ventas/procesar-venta/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrftoken
            },
            body: JSON.stringify(payload)
        });

        const data = await resp.json();

        // Callback opcional
        onPagoProcesado(data);

        // Lógica interna
        if (data.status === "ok") {
            limpiarCarrito();
            onPagoExito(data);
        } else {
            onPagoError(data.message || "Error al procesar la venta");
        }

        // 🔥 FIX CRÍTICO: devolver data para ui.js
        return data;

    } catch (e) {
        onPagoError("Error de conexión con el servidor");

        // También devolver algo para que ui.js no reciba undefined
        return { status: "error", message: "Error de conexión con el servidor" };
    }
}
