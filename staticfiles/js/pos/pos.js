import { initBuscador, initDragDrop, initEscaneo } from "./buscador_productos.js";
import { initPago } from "./pago.js";
import { descuentoActivo, setDescuentoActivo } from "./core.js";
import { aplicarDescuento10, quitarDescuento10 } from "./precios.js";
import { actualizarTotales } from "./totales.js";
import { renderCarrito } from "./carrito.js";

function initDescuento() {
    const btn = document.getElementById("btn-descuento");

    if (!btn) return;

    // Estado inicial: OFF (rojo)
    btn.classList.add("bg-red-600", "hover:bg-red-700", "text-white");
    btn.textContent = "10% OFF";

    btn.addEventListener("click", () => {

        if (!descuentoActivo) {
            // ACTIVAR DESCUENTO
            aplicarDescuento10();
            setDescuentoActivo(true);

            btn.classList.remove("bg-red-600", "hover:bg-red-700");
            btn.classList.add("bg-green-600", "hover:bg-green-700");
            btn.textContent = "10% ON";

        } else {
            // DESACTIVAR DESCUENTO
            quitarDescuento10();
            setDescuentoActivo(false);

            btn.classList.remove("bg-green-600", "hover:bg-green-700");
            btn.classList.add("bg-red-600", "hover:bg-red-700");
            btn.textContent = "10% OFF";
        }

        actualizarTotales();
        renderCarrito();
    });
}

document.addEventListener("DOMContentLoaded", () => {
    initBuscador();
    initDragDrop();
    initEscaneo();
    initPago();
    initDescuento();   // 🔥 Aquí se activa el botón 10% ON/OFF
});