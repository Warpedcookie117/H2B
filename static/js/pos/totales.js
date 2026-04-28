import { carrito, descuentoActivo, totalConDescuento } from "./core.js";

export function actualizarTotales() {
    const total = totalConDescuento();

    document.getElementById("total-general").textContent = total.toFixed(2);

    document.dispatchEvent(new CustomEvent("pos:total-actualizado", { detail: { total } }));
}
