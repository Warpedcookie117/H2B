import { carrito, descuentoPct, totalConDescuento, totalSinDescuento } from "./core.js";

console.log("[POS:totales] Módulo cargado");

export function actualizarTotales() {
    const total = totalConDescuento();
    console.log(`[POS:totales] actualizarTotales → total=$${total.toFixed(2)} (descuento=${descuentoPct}%) items=${carrito.length}`);

    document.getElementById("total-general").textContent = total.toFixed(2);

    // Para las promociones de monto mínimo no cuenta lo vendido por caja o
    // media docena (decisión de las dueñas: el regalo es para la compra normal).
    const sinDesc = totalSinDescuento();
    const enPaquete = carrito
        .filter(i => i.presentacion)
        .reduce((s, i) => s + i.precio_aplicado * i.cantidad, 0);
    const totalPromos = sinDesc > 0 ? total * (sinDesc - enPaquete) / sinDesc : 0;

    document.dispatchEvent(new CustomEvent("pos:total-actualizado", { detail: { total, totalPromos } }));
}
