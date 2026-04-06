import { carrito, descuentoActivo, totalConDescuento } from "./core.js";

export function actualizarTotales() {

    // totalConDescuento() YA calcula todo dinámicamente
    const total = totalConDescuento();

    document.getElementById("total-general").textContent =
        total.toFixed(2);
}
