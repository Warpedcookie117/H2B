// pago.js

import { carrito, totalConDescuento, descuentoActivo } from "./core.js";
import { getCookie } from "./core.js";
import { renderCarrito } from "./carrito.js";
import { actualizarTotales } from "./totales.js";

export function initPago() {
    const btnCobrar = document.getElementById("btn-cobrar");
    const modalPago = document.getElementById("modal-pago");
    const inputPagoEfectivo = document.getElementById("pago-efectivo");
    const inputPagoTarjeta = document.getElementById("pago-tarjeta");
    const btnConfirmarPago = document.getElementById("confirmar-pago");
    const btnCerrarModal = document.getElementById("cerrar-modal");

    // Contenedor de errores
    const errorBox = document.createElement("div");
    errorBox.id = "error-stock";
    errorBox.className = "text-red-600 font-bold text-sm mb-2 hidden";
    btnCobrar.parentNode.insertBefore(errorBox, btnCobrar);

    btnCobrar.addEventListener("click", () => {

        if (carrito.length === 0) {
            mostrarError("No hay productos en el carrito");
            return;
        }

        // Validación de stock
        for (const item of carrito) {
            if (item.cantidad <= item.stock_piso) continue;
            if (item.cantidad <= item.stock_bodega) continue;

            mostrarError(`"${item.nombre}" no tiene stock suficiente`);
            return;
        }

        ocultarError();
        modalPago.classList.remove("hidden");

        inputPagoEfectivo.value = totalConDescuento.toFixed(2);
        inputPagoTarjeta.value = "0.00";
    });

    btnCerrarModal.addEventListener("click", () => {
        modalPago.classList.add("hidden");
    });

    btnConfirmarPago.addEventListener("click", () => {
        const efectivo = parseFloat(inputPagoEfectivo.value || 0);
        const tarjeta = parseFloat(inputPagoTarjeta.value || 0);

        if (efectivo + tarjeta < totalConDescuento) {
            mostrarError("Pago insuficiente");
            return;
        }

        ocultarError();
        enviarVenta(efectivo, tarjeta, modalPago);
    });
}

function mostrarError(msg) {
    const box = document.getElementById("error-stock");
    box.textContent = msg;
    box.classList.remove("hidden");
}

function ocultarError() {
    const box = document.getElementById("error-stock");
    box.classList.add("hidden");
}

function enviarVenta(efectivo, tarjeta, modalPago) {

    const payload = {
        carrito: carrito.map(p => ({
            producto_id: p.id,
            cantidad: p.cantidad,
            precio_aplicado: p.precio_aplicado
        })),
        pagado_efectivo: efectivo,
        pagado_tarjeta: tarjeta,
        ubicacion_id: sucursal_id,
        descuento_10: descuentoActivo
    };

    const csrftoken = getCookie("csrftoken");

    fetch("/ventas/procesar-venta/", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {

        if (data.status === "ok") {

            mostrarAlerta("Venta realizada con éxito ✔️", "ok");

            carrito.length = 0;
            renderCarrito();
            actualizarTotales();
            modalPago.classList.add("hidden");

        } else {
            mostrarAlerta("Error: " + data.message, "error");
        }
    })
    .catch(() => {
        mostrarAlerta("Error de conexión con el servidor", "error");
    });
}

function mostrarAlerta(mensaje, tipo = "ok") {
    const box = document.getElementById("pos-alerta");

    box.textContent = mensaje;

    if (tipo === "ok") {
        box.className = "p-3 rounded-lg font-bold text-center mb-3 bg-green-600 text-white";
    } else {
        box.className = "p-3 rounded-lg font-bold text-center mb-3 bg-red-600 text-white";
    }

    box.classList.remove("hidden");

    setTimeout(() => {
        box.classList.add("hidden");
    }, 3000);
}