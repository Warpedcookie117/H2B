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

    console.log("🔥 initUI ejecutado");

    setOnCarritoActualizado(() => {
        console.log("🛒 Carrito actualizado → render + totales");
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
        div.className = "carrito-item bg-gray-100 p-3 rounded-lg shadow flex flex-col gap-2";

        div.innerHTML = `
            <div class="flex justify-between items-center">
                <span class="font-semibold">${item.nombre}</span>
                <button class="btn-eliminar bg-red-600 text-white px-2 py-1 rounded text-xs font-bold"
                        data-idx="${index}">
                    X
                </button>
            </div>

            <div class="flex items-center gap-3">
                <button class="btn-menos px-3 py-1 bg-red-500 text-white rounded" data-idx="${index}">-</button>

                <input 
                    type="number"
                    min="1"
                    class="cantidad-input w-16 border rounded p-1 text-center"
                    value="${item.cantidad}"
                    data-idx="${index}"
                >

                <button class="btn-mas px-3 py-1 bg-green-500 text-white rounded" data-idx="${index}">+</button>
            </div>

            <div>${resolverBadge(item)}</div>

            <div class="flex gap-2">
                ${renderBotonesPrecio(item, index)}
            </div>

            <div class="text-right font-bold text-lg text-red-600">
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
        return `<span class="inline-block bg-green-600 text-white text-xs font-semibold px-2 py-1 rounded">Se descontará de Piso</span>`;
    }
    if (item.cantidad <= item.stock_bodega) {
        return `<span class="inline-block bg-yellow-500 text-white text-xs font-semibold px-2 py-1 rounded">Se descontará de Bodega Interna</span>`;
    }
    return `<span class="inline-block bg-red-600 text-white text-xs font-semibold px-2 py-1 rounded">No hay stock suficiente</span>`;
}



// ============================================================
// 4. Botones MEN/MAY/DOC/AUTO
// ============================================================

function renderBotonesPrecio(item, index) {
    const colores = {
        AUTO: "bg-blue-600 text-white",
        MEN: "bg-pink-300 text-black",
        MAY: "bg-green-500 text-white",
        DOC: "bg-purple-500 text-white"
    };

    return ["MEN", "MAY", "DOC", "AUTO"].map(m => {
        if (m === "DOC" && (!item.precios.doc || item.precios.doc <= 0)) {
            return `<button class="px-2 py-1 rounded text-xs font-bold bg-gray-400 opacity-50 cursor-not-allowed" disabled>DOC</button>`;
        }

        const activo = item.modo_precio === m;
        const resuelto = item.modo_resuelto === m;

        let clases = "px-2 py-1 rounded text-xs font-bold ";

        if (activo) clases += colores[m];
        else if (item.modo_precio === "AUTO" && resuelto) clases += colores[m];
        else clases += "bg-gray-300";

        if (resuelto) clases += " border-4 border-black";

        return `<button class="${clases}" data-modo="${m}" data-idx="${index}">${m}</button>`;
    }).join("");
}



// ============================================================
// 5. Listeners del carrito
// ============================================================

function bindCarritoListeners() {
    document.querySelectorAll(".btn-eliminar").forEach(btn => {
        btn.onclick = () => eliminarProducto(parseInt(btn.dataset.idx));
    });

    document.querySelectorAll(".btn-mas").forEach(btn => {
        btn.onclick = () => cambiarCantidad(parseInt(btn.dataset.idx), carrito[btn.dataset.idx].cantidad + 1);
    });

    document.querySelectorAll(".btn-menos").forEach(btn => {
        btn.onclick = () => cambiarCantidad(parseInt(btn.dataset.idx), carrito[btn.dataset.idx].cantidad - 1);
    });

    document.querySelectorAll(".cantidad-input").forEach(input => {
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
        console.log("🟦 Click en COBRAR");

        const error = validarStock();
        console.log("🟦 validarStock() →", error);

        if (error) return mostrarAlertaUI(error, "error");

        console.log("🟦 Abriendo modal-pago");
        document.getElementById("modal-pago").classList.remove("hidden");
    };
}



// ============================================================
// 7. Descuento 10%
// ============================================================

function initDescuentoUI() {
    const btn = document.getElementById("btn-descuento");
    if (!btn) return;

    btn.classList.add("bg-red-600", "text-white");
    btn.textContent = "10% OFF";

    btn.onclick = () => {
        console.log("🟧 Toggle descuento 10%");

        if (!descuentoActivo) {
            aplicarDescuento10();
            setDescuentoActivo(true);
            btn.classList.replace("bg-red-600", "bg-green-600");
            btn.textContent = "10% ON";
        } else {
            quitarDescuento10();
            setDescuentoActivo(false);
            btn.classList.replace("bg-green-600", "bg-red-600");
            btn.textContent = "10% OFF";
        }

        actualizarTotales();
        renderCarritoUI();
    };
}



// ============================================================
// 8. Modal de pago — DEBUG EXTREMO
// ============================================================

function initModalPago() {
    const modal = document.getElementById("modal-pago");
    const btnCerrar = document.getElementById("cerrar-modal");
    const btnConfirmar = document.getElementById("confirmar-pago");

    const inputEfectivo = document.getElementById("pago-efectivo");
    const inputTarjeta = document.getElementById("pago-tarjeta");

    btnCerrar.onclick = () => {
        console.log("❌ Cerrar modal-pago manual");
        modal.classList.add("hidden");
    };

    btnConfirmar.onclick = async () => {
        console.log("🔥 Click en CONFIRMAR PAGO");

        const efectivo = parseFloat(inputEfectivo.value || 0);
        const tarjeta = parseFloat(inputTarjeta.value || 0);

        console.log("💵 efectivo:", efectivo);
        console.log("💳 tarjeta:", tarjeta);

        const error = validarPago(efectivo, tarjeta);
        console.log("🟥 validarPago() →", error);

        if (error) return mostrarAlertaUI(error, "error");

        console.log("📡 Enviando a procesarPago...");
        const data = await procesarPago(efectivo, tarjeta);

        console.log("📦 DATA RECIBIDA:", data);
        console.log("📦 STATUS:", data?.status);

        if (String(data?.status).toLowerCase() === "ok") {
            console.log("🟩 STATUS OK → procesando UI");

            const total = data.total;
            const cambio = data.cambio;


            console.log("🟩 total:", total);
            console.log("🟩 cambio:", cambio);

            console.log("🟩 Disparando evento pago-exito");
            document.dispatchEvent(new CustomEvent("pago-exito", {
                detail: {
                    total,
                    cambio,
                    ticket_texto: data.ticket_texto,
                    venta_id: data.venta_id
                }
            }));

            console.log("🟩 Cerrando modal-pago");
            modal.classList.add("hidden");

        } else {
            console.log("🟥 STATUS NO ES OK → NO se cierra modal, NO se abre resultado");
        }
    };
}



// ============================================================
// 9. Modal de resultado — DEBUG EXTREMO
// ============================================================

function initModalResultado() {
    const modal = document.getElementById("modal-resultado");
    const btnCerrar = document.getElementById("cerrar-resultado");
    const boxImpresion = document.getElementById("resultado-impresion");

    // ============================================================
    // Evento principal: pago exitoso
    // ============================================================
    document.addEventListener("pago-exito", (e) => {
        console.log("🔥 EVENTO pago-exito RECIBIDO");
        console.log("📨 detail:", e.detail);

        const total = e.detail.total;
        const cambio = e.detail.cambio;

        console.log("🟩 total recibido:", total);
        console.log("🟩 cambio recibido:", cambio);

        // Mostrar totales en el modal
        document.getElementById("resultado-total").textContent = total.toFixed(2);
        document.getElementById("resultado-cambio").textContent = cambio.toFixed(2);

        // Limpiar mensaje previo de impresión
        boxImpresion.textContent = "";
        boxImpresion.className = "text-center mt-4 text-sm";

        // Abrir modal
        console.log("🟩 Abriendo modal-resultado");
        modal.classList.remove("hidden");

        // Disparar impresión
        console.log("🖨️ Disparando imprimir-ticket");
        document.dispatchEvent(new CustomEvent("imprimir-ticket", {
            detail: {
                total,
                cambio,
                venta_id: e.detail.venta_id,
                ticket_texto: e.detail.ticket_texto
            }
        }));
    });

    // ============================================================
    // Evento: impresión exitosa
    // ============================================================
    document.addEventListener("impresion-exito", (e) => {
        console.log("🟩 Impresión exitosa");

        boxImpresion.textContent = "Ticket enviado a imprimir correctamente.";
        boxImpresion.className = "text-green-600 font-semibold text-center mt-4";
    });

    // ============================================================
    // Evento: impresión fallida
    // ============================================================
    document.addEventListener("impresion-fallo", (e) => {
        console.log("🟥 Impresión fallida:", e.detail);

        boxImpresion.textContent =
            `No se pudo imprimir el ticket. Puedes imprimirlo desde el Dashboard de Sucursal.
             ID de venta: ${e.detail.venta_id}`;

        boxImpresion.className = "text-yellow-600 font-semibold text-center mt-4";
    });

    // ============================================================
    // Botón cerrar modal
    // ============================================================
    btnCerrar.onclick = () => {
        console.log("❌ Cerrar modal-resultado");
        modal.classList.add("hidden");
    };
}



// ============================================================
// 10. Alertas UI
// ============================================================

export function mostrarAlertaUI(msg, tipo = "ok") {
    const box = document.getElementById("pos-alerta");
    if (!box) return;

    console.log("⚠️ ALERTA:", msg);

    box.textContent = msg;

    if (tipo === "ok") {
        box.className = "p-3 rounded-lg font-bold text-center mb-3 bg-green-600 text-white";
    } else {
        box.className = "p-3 rounded-lg font-bold text-center mb-3 bg-red-600 text-white";
    }

    box.classList.remove("hidden");

    setTimeout(() => box.classList.add("hidden"), 3000);
}
