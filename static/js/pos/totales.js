import { carrito, descuentoActivo, totalConDescuento } from "./core.js";

console.log("[POS:totales] Módulo cargado");

export function actualizarTotales() {
    const total = totalConDescuento();
    console.log(`[POS:totales] actualizarTotales → total=$${total.toFixed(2)} (descuento=${descuentoActivo}) items=${carrito.length}`);

    document.getElementById("total-general").textContent = total.toFixed(2);

    document.dispatchEvent(new CustomEvent("pos:total-actualizado", { detail: { total } }));
}
