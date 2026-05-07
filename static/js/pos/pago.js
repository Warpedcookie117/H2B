// pago.js — Lógica pura del pago

import { carrito, totalConDescuento, descuentoActivo } from "./core.js";
import { getCookie } from "./core.js";
import { limpiarCarrito } from "./carrito.js";

console.log("[POS:pago] Módulo cargado");

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
    console.log(`[POS:pago] validarStock — ${carrito.length} items en carrito`);

    if (carrito.length === 0) {
        console.warn("[POS:pago] validarStock FALLÓ — carrito vacío");
        return "No hay productos en el carrito";
    }

    for (const item of carrito) {
        if (item.es_servicio || item.es_regalo) continue;
        const stockTotal = (item.stock_piso || 0) + (item.stock_bodega || 0);
        if (item.cantidad > stockTotal) {
            console.warn(`[POS:pago] validarStock FALLÓ — "${item.nombre}" necesita ${item.cantidad} pero solo hay ${stockTotal} (piso=${item.stock_piso} bodega=${item.stock_bodega})`);
            return `"${item.nombre}" no tiene stock suficiente (piso: ${item.stock_piso}, bodega: ${item.stock_bodega})`;
        }
    }

    console.log("[POS:pago] validarStock OK ✓");
    return null;
}


// ============================================================
// 2. Validación del pago
// ============================================================

export function validarPago(efectivo, tarjeta) {
    const total = totalConDescuento();
    const recibido = efectivo + tarjeta;
    console.log(`[POS:pago] validarPago → efectivo=${efectivo} tarjeta=${tarjeta} total=${total.toFixed(2)} recibido=${recibido.toFixed(2)}`);

    if (recibido < total) {
        console.warn(`[POS:pago] validarPago FALLÓ — faltan $${(total - recibido).toFixed(2)}`);
        return "Pago insuficiente";
    }

    console.log("[POS:pago] validarPago OK ✓");
    return null;
}


// ============================================================
// 3. Procesar venta (llamar backend)
// ============================================================

export async function procesarPago(efectivo, tarjeta) {
    console.log(`[POS:pago] procesarPago → efectivo=${efectivo} tarjeta=${tarjeta} descuento=${descuentoActivo}`);

    onPagoIniciado();

    const payload = {
        carrito: carrito.map(p => {
            if (p.es_servicio) return {
                es_servicio:     true,
                nombre_servicio: p.nombre,
                cantidad:        1,
                precio_aplicado: Number(p.precio_aplicado) || 0,
            };
            if (p.es_regalo) return {
                es_regalo:      true,
                producto_id:    p.id,
                promo_id:       p.promo_id ?? null,
                promo_nombre:   p.promo_nombre,
                cantidad:       Number(p.cantidad) || 1,
                precio_aplicado: 0,
            };
            return {
                producto_id:     p.id,
                cantidad:        Number(p.cantidad) || 1,
                precio_aplicado: Number(p.precio_aplicado) || Number(p.precios?.men) || 0,
            };
        }),
        pagado_efectivo: Number(efectivo) || 0,
        pagado_tarjeta: Number(tarjeta) || 0,
        descuento_10: Boolean(descuentoActivo)
    };

    console.log("[POS:pago] payload a enviar:", payload);

    const csrftoken = getCookie("csrftoken");

    try {
        console.log("[POS:pago] enviando POST a /ventas/procesar-venta/...");
        const resp = await fetch("/ventas/procesar-venta/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrftoken
            },
            body: JSON.stringify(payload)
        });

        console.log(`[POS:pago] respuesta HTTP: ${resp.status} ${resp.statusText}`);
        const data = await resp.json();
        console.log("[POS:pago] respuesta JSON:", data);

        onPagoProcesado(data);

        if (data.status === "ok") {
            console.log(`[POS:pago] ✅ VENTA EXITOSA — venta_id=${data.venta_id} total=${data.total_venta} cambio=${data.cambio}`);
            limpiarCarrito();
            onPagoExito(data);
        } else {
            console.warn(`[POS:pago] ❌ VENTA RECHAZADA — ${data.message}`);
            onPagoError(data.message || "Error al procesar la venta");
        }

        return data;

    } catch (e) {
        console.error("[POS:pago] ERROR DE RED:", e);
        onPagoError("Error de conexión con el servidor");
        return { status: "error", message: "Error de conexión con el servidor" };
    }
}
