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

    // Redibuja el carrito cuando promociones.js actualiza promos_pendientes
    document.addEventListener("pos:redraw-carrito", () => renderCarritoUI());

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

    const scrollTop = cont.scrollTop;
    cont.innerHTML = "";

    carrito.forEach((item, index) => {
        const div = document.createElement("div");
        div.className = "pos-carrito-item";

        if (item.es_regalo) {
            div.innerHTML = `
                <div class="pos-carrito-item-header">
                    <span class="pos-carrito-item-nombre">🎁 ${item.nombre}</span>
                    <button class="pos-carrito-item-btn-eliminar" data-idx="${index}">✕</button>
                </div>
                <div class="pos-cantidad-controles">
                    <button class="pos-cantidad-btn pos-cantidad-btn--menos pos-regalo-menos" data-idx="${index}">−</button>
                    <span style="min-width:2rem;text-align:center;font-weight:900;font-size:.9rem;">x${item.cantidad}</span>
                </div>
                <div>
                    <span class="pos-stock-badge" style="background:#00F5D4;color:black;font-size:.65rem;">REGALO · ${item.promo_nombre}</span>
                </div>
                <div class="pos-precio-aplicado" style="color:#16a34a;">
                    $<span>0.00</span>
                </div>
            `;
        } else if (item.es_servicio) {
            div.innerHTML = `
                <div class="pos-carrito-item-header">
                    <span class="pos-carrito-item-nombre">🔧 ${item.nombre}</span>
                    <button class="pos-carrito-item-btn-eliminar" data-idx="${index}">✕</button>
                </div>
                <div>
                    <span class="pos-stock-badge" style="background:#8338EC;color:white;">Servicio</span>
                </div>
                <div class="pos-precio-aplicado">
                    $<span>${item.precio_aplicado.toFixed(2)}</span>
                </div>
            `;
        } else {
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
                ${item.oferta_activa ? `<div>${renderOfertaBadge(item)}</div>` : ''}

                <div class="pos-modo-botones">
                    ${renderBotonesPrecio(item, index)}
                </div>

                <div class="pos-precio-aplicado">
                    $<span>${item.precio_aplicado.toFixed(2)}</span>
                </div>
            `;

            // Badge por cada regalo pendiente (cuando el cajero clickó "Sin regalo")
            if (item.promos_pendientes?.length) {
                item.promos_pendientes.forEach(pp => {
                    const btnRegalo = document.createElement("button");
                    btnRegalo.className = "pos-btn-regalo-pendiente";
                    const cant = pp.cantidad > 1 ? ` x${pp.cantidad}` : "";
                    btnRegalo.textContent = `🎁${cant} sin regalo — ${pp.nombre} (agregar)`;
                    btnRegalo.onclick = () => window.abrirRegaloManual(pp.id, pp.nombre, index);
                    div.appendChild(btnRegalo);
                });
            }
        }

        cont.appendChild(div);
    });

    bindCarritoListeners();
    cont.scrollTop = scrollTop;
}


// ============================================================
// 3. Badges de stock y oferta
// ============================================================

function renderOfertaBadge(item) {
    if (!item.oferta_activa) return '';
    const o = item.oferta_activa;
    let detalle = '';
    switch (o.tipo) {
        case 'porcentaje': detalle = `${o.valor}% off`; break;
        case 'fijo':       detalle = `$${o.valor} menos`; break;
        case '2x1':        detalle = '2×1'; break;
        case 'nxprecio':   detalle = `${o.cantidad_n} × $${o.valor}`; break;
    }
    return `<span class="pos-stock-badge" style="background:#FF006E;color:#fff;font-size:.65rem;">🏷️ ${o.nombre}${detalle ? ' · ' + detalle : ''}</span>`;
}

function resolverBadge(item) {
    if (item.cantidad <= item.stock_piso) {
        return `<span class="pos-stock-badge pos-stock-badge--piso">Se descontará de Piso</span>`;
    }
    if (item.cantidad <= item.stock_bodega) {
        return `<span class="pos-stock-badge pos-stock-badge--bodega">Se descontará de Bodega</span>`;
    }
    if (item.cantidad <= (item.stock_piso || 0) + (item.stock_bodega || 0)) {
        return `<span class="pos-stock-badge pos-stock-badge--split">Alcanza entre ambas — bodega primero</span>`;
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
// 5. Helpers de cascade y pendientes
// ============================================================

// Promos de categoría que aplican a este ítem
function _promosDeItem(item) {
    if (!window.PROMOCIONES?.length) return [];
    return window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "categoria" &&
        (p.categoria_disparadora_id == item.subcategoria_id ||
         (item.cat_padre_id && p.categoria_disparadora_id == item.cat_padre_id))
    );
}

// Añade `cantidad` al badge de pendientes del ítem (sin abrir modal)
function _addPendienteItem(item, cantidad = 1) {
    const promos = _promosDeItem(item);
    if (!promos.length) return;
    if (!item.promos_pendientes) item.promos_pendientes = [];
    promos.forEach(promo => {
        const pp = item.promos_pendientes.find(p => p.id === promo.id);
        if (pp) pp.cantidad += cantidad;
        else item.promos_pendientes.push({ id: promo.id, nombre: promo.nombre, cantidad });
    });
    document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
}

// Cuando se quita 1 del regalo → añade 1 al badge del disparador
function _addPendienteDesdeRegalo(regaloItem) {
    if (!regaloItem.promo_id || !window.PROMOCIONES?.length) return;
    const promo = window.PROMOCIONES.find(p => p.id === regaloItem.promo_id);
    if (!promo?.categoria_disparadora_id) return;
    const catId = promo.categoria_disparadora_id;
    const trig  = carrito.find(i =>
        !i.es_regalo && !i.es_servicio &&
        (i.subcategoria_id == catId || i.cat_padre_id == catId)
    );
    if (!trig) return;
    if (!trig.promos_pendientes) trig.promos_pendientes = [];
    const pp = trig.promos_pendientes.find(p => p.id === promo.id);
    if (pp) pp.cantidad++;
    else trig.promos_pendientes.push({ id: promo.id, nombre: promo.nombre, cantidad: 1 });
    document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
}

// Quita delta del regalo en carrito Y del badge en el disparador.
// delta = Infinity → eliminar todo. itemIdx = -1 → no tocar el badge.
function cascadeRegalo(subcategoria_id, cat_padre_id, delta, itemIdx = -1) {
    if (!window.PROMOCIONES?.length) return;

    const promos = window.PROMOCIONES.filter(p =>
        p.tipo_condicion === "categoria" &&
        (p.categoria_disparadora_id == subcategoria_id ||
         (cat_padre_id && p.categoria_disparadora_id == cat_padre_id))
    );

    promos.forEach(promo => {
        // 1. Badge del disparador — ANTES del splice para no perder el índice
        if (itemIdx >= 0 && carrito[itemIdx]?.promos_pendientes) {
            const pp = carrito[itemIdx].promos_pendientes.find(p => p.id === promo.id);
            if (pp) {
                if (delta === Infinity) {
                    carrito[itemIdx].promos_pendientes =
                        carrito[itemIdx].promos_pendientes.filter(p => p.id !== promo.id);
                } else {
                    pp.cantidad = Math.max(0, pp.cantidad - delta);
                    if (pp.cantidad === 0)
                        carrito[itemIdx].promos_pendientes =
                            carrito[itemIdx].promos_pendientes.filter(p => p.id !== promo.id);
                }
            }
        }

        // 2. El ítem de regalo en carrito
        const ri = carrito.findIndex(r => r.es_regalo && r.promo_id === promo.id);
        if (ri === -1) return;
        const regalo = carrito[ri];
        if (delta === Infinity || regalo.cantidad <= delta) {
            eliminarProducto(ri);
        } else {
            cambiarCantidad(ri, regalo.cantidad - delta);
        }
    });

    document.dispatchEvent(new CustomEvent("pos:redraw-carrito"));
}


// ============================================================
// 6. Listeners del carrito
// ============================================================

function bindCarritoListeners() {
    // ✕ — eliminar ítem; si era disparador, borra también su regalo (badge ya no importa)
    document.querySelectorAll(".pos-carrito-item-btn-eliminar").forEach(btn => {
        btn.onclick = () => {
            const idx  = parseInt(btn.dataset.idx);
            const item = carrito[idx];
            if (!item) return;
            if (!item.es_regalo && !item.es_servicio) {
                const { subcategoria_id, cat_padre_id } = item;
                eliminarProducto(idx);
                cascadeRegalo(subcategoria_id, cat_padre_id, Infinity, -1);
            } else {
                eliminarProducto(idx);
            }
        };
    });

    // + — añade al badge de pendientes; el cajero abre 1 modal cuando quiera
    document.querySelectorAll(".pos-cantidad-btn--mas").forEach(btn => {
        btn.onclick = () => {
            const idx  = parseInt(btn.dataset.idx);
            const item = carrito[idx];
            if (!item || item.es_regalo || item.es_servicio) return;
            cambiarCantidad(idx, item.cantidad + 1);
            _addPendienteItem(item, 1);
        };
    });

    // − en disparador → cascade regalo y badge; en regalo → baja 1 y badge al disparador
    document.querySelectorAll(".pos-cantidad-btn--menos").forEach(btn => {
        btn.onclick = () => {
            const idx  = parseInt(btn.dataset.idx);
            const item = carrito[idx];
            if (!item) return;
            if (item.es_regalo) {
                _addPendienteDesdeRegalo(item);   // siempre, antes de tocar el carrito
                if (item.cantidad <= 1) {
                    eliminarProducto(idx);
                } else {
                    cambiarCantidad(idx, item.cantidad - 1);
                }
                return;
            }
            const prevQty = item.cantidad;
            cambiarCantidad(idx, prevQty - 1);
            const newQty  = carrito[idx]?.cantidad ?? prevQty;
            if (newQty < prevQty) cascadeRegalo(item.subcategoria_id, item.cat_padre_id, 1, idx);
        };
    });

    // Input numérico — cascade decrementos; incrementos al badge
    document.querySelectorAll(".pos-cantidad-input").forEach(input => {
        input.oninput = () => {
            const idx  = parseInt(input.dataset.idx);
            const item = carrito[idx];
            if (!item || item.es_regalo) return;
            const prevQty = item.cantidad;
            const newVal  = parseInt(input.value) || 1;
            cambiarCantidad(idx, newVal);
            const newQty = carrito[idx]?.cantidad ?? newVal;
            const decr   = prevQty - newQty;
            const incr   = newQty  - prevQty;
            if (decr > 0) cascadeRegalo(item.subcategoria_id, item.cat_padre_id, decr, idx);
            if (incr > 0) _addPendienteItem(item, incr);
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
        btnConfirmar.disabled     = false;
        btnConfirmar.textContent  = "Confirmar";
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

        btnConfirmar.disabled    = true;
        btnConfirmar.textContent = "Procesando...";

        const data = await procesarPago(efectivo, tarjeta);

        if (String(data?.status).toLowerCase() === "ok") {
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
            btnConfirmar.disabled    = false;
            btnConfirmar.textContent = "Confirmar";
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
    box.className = "pos-alerta " + (
        tipo === "ok"    ? "pos-alerta--ok"    :
        tipo === "promo" ? "pos-alerta--promo"  :
                           "pos-alerta--error"
    );

    box.classList.remove("pos-alerta--hidden");
    setTimeout(() => box.classList.add("pos-alerta--hidden"), 3000);
}