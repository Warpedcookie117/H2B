import { carrito, descuentoActivo, setTotales } from "./core.js";

export function actualizarTotales() {

    let total = carrito.reduce((acc, item) => {
        return acc + (item.precio_aplicado * item.cantidad);
    }, 0);

    const totalConDesc = descuentoActivo ? total * 0.9 : total;

    setTotales(total, totalConDesc);

    document.getElementById("total-general").textContent =
        totalConDesc.toFixed(2);
}