// ui.js — UI completa del POS (carrito, totales, pago, modales)

import {
    carrito,
    descuentoActivo,
    setDescuentoActivo,
    setOnCarritoActualizado,
    totalConDescuento
} from "./core.js";

import {
    cambiarCantidad,
    eliminarProducto,
    cambiarModoPrecio
} from "./carrito.js";

import {
    aplicarDescuento10,
    quitarDescuento10
} from "./precios.js";

import {
    validarStock,
    validarPago,
    procesarPago
} from "./pago.js";

import { actualizarTotales } from "./totales.js";


// ============================================================
// 1. Inicialización general
// ============================================================

export function initUI() {
    setOnCarritoActualizado(() => {
        renderCarritoUI();
        actualizarTotales();
    });

    renderCarritoUI();
    initBotonCobrar();
    initDescuentoUI();
    initModalPago();
    initModalResultado();
}


// ============================================================
// 2. Render del carrito
// ============================================================

function renderCarritoUI() {
    const cont = document.getElementById("carrito-lista");
    if (!cont) return;

    cont.innerHTML = "";

    carrito.forEach((item, index) => {
        const div = document.createElement("div");
        div.className = "pos-carrito-item";

        div.innerHTML = `
            <div class="pos-carrito-item-header">
                <span class="pos-carrito-item-nombre">${item.nombre}</span>
                <button class="pos-carrito-item-btn-eliminar" data-idx="${index}">✕</button>
            </div>

            <div class="pos-cantidad-controles">
                <button class="pos-cantidad-btn pos-cantidad-btn--menos" data-idx="${index}">−</button>
                <input
                    type="number" min="1"
                    class="pos-cantidad-input"
                    value="${item.cantidad}"
                    data-idx="${index}"
                >
                <button class="pos-cantidad-btn pos-cantidad-btn--mas" data-idx="${index}">+</button>
            </div>

            <div>${resolverBadge(item)}</div>

            <div class="pos-modo-botones">
                ${renderBotonesPrecio(item, index)}
            </div>

            <div class="pos-precio-aplicado">
                $<span>${item.precio_aplicado.toFixed(2)}</span>
            </div>
        `;

        cont.appendChild(div);
    });

    bindCarritoListeners();
}


// ============================================================
// 3. Badges de stock
// ============================================================

function resolverBadge(item) {
    if (item.cantidad <= item.stock_piso) {
        return `<span class="pos-stock-badge pos-stock-badge--piso">Se descontará de Piso</span>`;
    }
    if (item.cantidad <= item.stock_bodega) {
        return `<span class="pos-stock-badge pos-stock-badge--bodega">Se descontará de Bodega</span>`;
    }
    return `<span class="pos-stock-badge pos-stock-badge--sin-stock">No hay stock suficiente</span>`;
}


// ============================================================
// 4. Botones MEN / MAY / DOC / AUTO
// ============================================================

function renderBotonesPrecio(item, index) {
    const clasesModo = {
        MEN:  "pos-modo-btn pos-modo-btn--men",
        MAY:  "pos-modo-btn pos-modo-btn--may",
        DOC:  "pos-modo-btn pos-modo-btn--doc",
        AUTO: "pos-modo-btn pos-modo-btn--auto"
    };

    return ["MEN", "MAY", "DOC", "AUTO"].map(m => {
        if (m === "DOC" && (!item.precios.doc || item.precios.doc <= 0)) {
            return `<button class="pos-modo-btn pos-modo-btn--disabled" disabled>DOC</button>`;
        }

        const activo   = item.modo_precio === m;
        const resuelto = item.modo_resuelto === m;

        let clases = clasesModo[m];

        if (activo) clases += " pos-modo-btn--activo";
        else if (item.modo_precio === "AUTO" && resuelto) clases += " pos-modo-btn--activo";

        if (resuelto) clases += " pos-modo-btn--resuelto";

        return `<button class="${clases}" data-modo="${m}" data-idx="${index}">${m}</button>`;
    }).join("");
}


// ============================================================
// 5. Listeners del carrito
// ============================================================

function bindCarritoListeners() {
    document.querySelectorAll(".pos-carrito-item-btn-eliminar").forEach(btn => {
        btn.onclick = () => eliminarProducto(parseInt(btn.dataset.idx));
    });

    document.querySelectorAll(".pos-cantidad-btn--mas").forEach(btn => {
        btn.onclick = () => cambiarCantidad(parseInt(btn.dataset.idx), carrito[btn.dataset.idx].cantidad + 1);
    });

    document.querySelectorAll(".pos-cantidad-btn--menos").forEach(btn => {
        btn.onclick = () => cambiarCantidad(parseInt(btn.dataset.idx), carrito[btn.dataset.idx].cantidad - 1);
    });

    document.querySelectorAll(".pos-cantidad-input").forEach(input => {
        input.oninput = () => {
            const idx = parseInt(input.dataset.idx);
            const val = parseInt(input.value) || 1;
            cambiarCantidad(idx, val);
        };
    });

    document.querySelectorAll("[data-modo]").forEach(btn => {
        btn.onclick = () => cambiarModoPrecio(parseInt(btn.dataset.idx), btn.dataset.modo);
    });
}


// ============================================================
// 6. Botón COBRAR
// ============================================================

function initBotonCobrar() {
    const btn = document.getElementById("btn-cobrar");
    if (!btn) return;

    btn.onclick = () => {
        const error = validarStock();
        if (error) return mostrarAlertaUI(error, "error");

        // Abre el modal ya inicializado con el total correcto
        abrirModalPago();
    };
}


// ============================================================
// 7. Descuento 10%
// ============================================================

function initDescuentoUI() {
    const btn = document.getElementById("btn-descuento");
    if (!btn) return;

    btn.onclick = () => {
        if (!descuentoActivo) {
            aplicarDescuento10();
            setDescuentoActivo(true);
            btn.classList.add("pos-btn-descuento--activo");
            btn.textContent = "10% ON";
        } else {
            quitarDescuento10();
            setDescuentoActivo(false);
            btn.classList.remove("pos-btn-descuento--activo");
            btn.textContent = "10% OFF";
        }

        actualizarTotales();
        renderCarritoUI();
    };
}


// ============================================================
// 8. Modal de pago — con cálculo en vivo
// ============================================================

// Se declara aquí para que initBotonCobrar pueda llamarla
// después de que initModalPago la defina
let abrirModalPago = () => {};

function initModalPago() {
    const modal        = document.getElementById("modal-pago");
    const btnCerrar    = document.getElementById("cerrar-modal");
    const btnConfirmar = document.getElementById("confirmar-pago");
    const inputEfectivo = document.getElementById("pago-efectivo");
    const inputTarjeta  = document.getElementById("pago-tarjeta");
    const infoBox       = document.getElementById("pago-info");
    const totalDisplay  = document.getElementById("pago-total-display");

    // Calcula en vivo cuánto falta o cuánto es el cambio
    function actualizarInfoPago() {
        const efectivo   = parseFloat(inputEfectivo.value || 0);
        const tarjeta    = parseFloat(inputTarjeta.value  || 0);
        const total      = totalConDescuento();
        const diferencia = (efectivo + tarjeta) - total;

        if (efectivo + tarjeta === 0) {
            infoBox.textContent = "";
            infoBox.className   = "pos-pago-info";
            return;
        }

        if (diferencia < 0) {
            infoBox.textContent = `Faltan $${Math.abs(diferencia).toFixed(2)} por pagar`;
            infoBox.className   = "pos-pago-info pos-pago-info--falta";
        } else {
            infoBox.textContent = `Cambio: $${diferencia.toFixed(2)}`;
            infoBox.className   = "pos-pago-info pos-pago-info--cambio";
        }
    }

    inputEfectivo.addEventListener("input", actualizarInfoPago);
    inputTarjeta.addEventListener("input",  actualizarInfoPago);

    // Inicializa el modal con valores limpios cada vez que se abre
    abrirModalPago = () => {
        const total = totalConDescuento();
        totalDisplay.textContent = total.toFixed(2);
        inputEfectivo.value = "";
        inputTarjeta.value  = "";
        infoBox.textContent = "";
        infoBox.className   = "pos-pago-info";
        modal.classList.remove("pos-modal--hidden");
        inputEfectivo.focus();
        actualizarInfoPago();
    };

    // Cerrar sin procesar
    btnCerrar.onclick = () => modal.classList.add("pos-modal--hidden");

    // Confirmar y procesar la venta
    btnConfirmar.onclick = async () => {
        const efectivo = parseFloat(inputEfectivo.value || 0);
        const tarjeta  = parseFloat(inputTarjeta.value  || 0);

        const error = validarPago(efectivo, tarjeta);
        if (error) return mostrarAlertaUI(error, "error");

        const data = await procesarPago(efectivo, tarjeta);

        if (String(data?.status).toLowerCase() === "ok") {
            // Pasa todos los datos al modal de resultado
            document.dispatchEvent(new CustomEvent("pago-exito", {
                detail: {
                    total:            data.total_venta,
                    cambio:           data.cambio,
                    pagado_efectivo:  data.pagado_efectivo,
                    pagado_tarjeta:   data.pagado_tarjeta,
                    ticket_texto:     data.ticket_texto,
                    venta_id:         data.venta_id
                }
            }));

            modal.classList.add("pos-modal--hidden");
        } else {
            mostrarAlertaUI(data?.message || "Error al procesar la venta", "error");
        }
    };
}


// ============================================================
// 9. Modal de resultado
// ============================================================

function initModalResultado() {
    const modal       = document.getElementById("modal-resultado");
    const btnCerrar   = document.getElementById("cerrar-resultado");
    const boxImpresion = document.getElementById("resultado-impresion");

    // Venta procesada correctamente → llenar y mostrar modal
    document.addEventListener("pago-exito", (e) => {
        const { total, cambio, pagado_efectivo, pagado_tarjeta } = e.detail;

        document.getElementById("resultado-total-venta").textContent = total.toFixed(2);
        document.getElementById("resultado-recibido").textContent    = (pagado_efectivo + pagado_tarjeta).toFixed(2);
        document.getElementById("resultado-cambio").textContent      = cambio.toFixed(2);

        boxImpresion.textContent = "";
        boxImpresion.className   = "pos-resultado-impresion";

        modal.classList.remove("pos-modal--hidden");

        // La impresión se hace en el servidor (imprimir_silencioso)
        // Notificamos éxito directo para actualizar el mensaje en pantalla
        document.dispatchEvent(new CustomEvent("impresion-exito", {
            detail: { venta_id: e.detail.venta_id }
        }));
    });

    // Impresión exitosa
    document.addEventListener("impresion-exito", () => {
        boxImpresion.textContent = "✓ Ticket enviado correctamente.";
        boxImpresion.className   = "pos-resultado-impresion pos-resultado-impresion--ok";
    });

    // Impresión fallida — el ticket sigue disponible en el Dashboard
    document.addEventListener("impresion-fallo", (e) => {
        boxImpresion.textContent = `No se pudo imprimir. Puedes imprimirlo desde el Dashboard. Venta: ${e.detail.venta_id}`;
        boxImpresion.className   = "pos-resultado-impresion pos-resultado-impresion--error";
    });

    btnCerrar.onclick = () => modal.classList.add("pos-modal--hidden");
}


// ============================================================
// 10. Alertas UI
// ============================================================

export function mostrarAlertaUI(msg, tipo = "ok") {
    const box = document.getElementById("pos-alerta");
    if (!box) return;

    box.textContent = msg;
    box.className = "pos-alerta " + (tipo === "ok"
        ? "pos-alerta--ok"
        : "pos-alerta--error");

    box.classList.remove("pos-alerta--hidden");
    setTimeout(() => box.classList.add("pos-alerta--hidden"), 3000);
}