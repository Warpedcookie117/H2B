// ui.js — UI completa del POS (carrito, totales, pago, modales)

console.log("[POS:ui] Módulo cargado");

import {
    carrito,
    descuentoPct,
    setDescuentoPct,
    setOnCarritoActualizado,
    totalConDescuento,
    lastAddedId,
    clearLastAddedId,
} from "./core.js";

import {
    cambiarCantidad,
    eliminarProducto,
    cambiarModoPrecio,
    agregarServicio,
    agregarCobroRapido,
} from "./carrito.js";

import {
    validarStock,
    validarPago,
    procesarPago
} from "./pago.js";

import { actualizarTotales } from "./totales.js";
import { imprimirTicket } from "./impresion.js";


// ============================================================
// 1. Inicialización general
// ============================================================

export function initUI() {
    console.log("[POS:ui] initUI");

    // Rastrear foco para saber siempre dónde está el cursor
    document.addEventListener("focusin", (e) => {
        const el = e.target;
        const desc = el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}${el.className ? "." + el.className.split(" ")[0] : ""}`;
        console.log(`[POS:ui] 🎯 FOCO → ${desc}`);
    });

    setOnCarritoActualizado(() => {
        console.log("[POS:ui] onCarritoActualizado → renderCarritoUI + actualizarTotales");
        renderCarritoUI();
        actualizarTotales();
    });

    // Redibuja el carrito cuando promociones.js actualiza promos_pendientes
    document.addEventListener("pos:redraw-carrito", () => {
        console.log("[POS:ui] pos:redraw-carrito → renderCarritoUI");
        renderCarritoUI();
    });

    renderCarritoUI();
    initBotonCobrar();
    initDescuentoUI();
    initModalPago();
    initModalResultado();
    initModalServicio();
    initModalCobroRapido();
    console.log("[POS:ui] initUI completo ✓");
}

function initModalServicio() {
    console.log("[POS:ui] initModalServicio");
    function abrirModalServicio() {
        console.log("[POS:ui] abrirModalServicio");
        document.getElementById("srv-nombre").value = "";
        document.getElementById("srv-precio").value = "";
        document.getElementById("srv-error").style.display = "none";
        const m = document.getElementById("modal-servicio");
        if (m) { m.style.display = "flex"; setTimeout(() => document.getElementById("srv-nombre").focus(), 50); }
    }

    window.abrirModalServicio = abrirModalServicio;

    window.cerrarModalServicio = function () {
        console.log("[POS:ui] cerrarModalServicio");
        const m = document.getElementById("modal-servicio");
        if (m) m.style.display = "none";
        document.getElementById("scan-input")?.focus();
    };

    window.confirmarServicio = function () {
        console.log("[POS:ui] confirmarServicio");
        const nombre = document.getElementById("srv-nombre").value.trim() || "Servicio";
        const precio = parseFloat(document.getElementById("srv-precio").value);
        const err = document.getElementById("srv-error");
        if (!precio || precio <= 0) {
            err.textContent = "Escribe un precio mayor a $0";
            err.style.display = "block";
            return;
        }
        err.style.display = "none";
        agregarServicio(nombre, precio);
        window.cerrarModalServicio();
    };

    document.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
        if (e.key === "s" || e.key === "S") { e.preventDefault(); abrirModalServicio(); }
    });

    document.getElementById("srv-precio")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") window.confirmarServicio();
    });

    document.getElementById("modal-servicio")?.addEventListener("click", function (e) {
        if (e.target === this) window.cerrarModalServicio();
    });

    document.getElementById("modal-regalo")?.addEventListener("click", function (e) {
        if (e.target === this) window.cerrarModalRegalo?.();
    });
}


// ============================================================
// 2. Render del carrito
// ============================================================

function renderCarritoUI() {
    const cont = document.getElementById("carrito-lista");
    if (!cont) return;
    console.log(`[POS:ui] renderCarritoUI — ${carrito.length} items`);

    cont.innerHTML = "";

    const highlightId = lastAddedId;
    clearLastAddedId();

    for (let index = carrito.length - 1; index >= 0; index--) {
        const item = carrito[index];
        const div = document.createElement("div");
        div.className = "pos-carrito-item";
        if (item.id === highlightId) div.classList.add("pos-carrito-item--nuevo");

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
        } else if (item.es_cobro_rapido) {
            div.innerHTML = `
                <div class="pos-carrito-item-header">
                    <span class="pos-carrito-item-nombre">⚡ ${item.nombre}</span>
                    <button class="pos-carrito-item-btn-eliminar" data-idx="${index}">✕</button>
                </div>
                <div>
                    <span class="pos-stock-badge" style="background:#FB5607;color:white;">Sin registro</span>
                </div>
                <div class="pos-precio-aplicado">
                    $<span>${item.precio_aplicado.toFixed(2)}</span>
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
    }

    bindCarritoListeners();
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
    console.log("[POS:ui] bindCarritoListeners");
    // ✕ — eliminar ítem; si era disparador, borra también su regalo (badge ya no importa)
    document.querySelectorAll(".pos-carrito-item-btn-eliminar").forEach(btn => {
        btn.onclick = () => {
            const idx  = parseInt(btn.dataset.idx);
            const item = carrito[idx];
            console.log(`[POS:ui] ✕ eliminar → idx=${idx} item="${item?.nombre}"`);
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
            console.log(`[POS:ui] + más → idx=${idx} item="${item?.nombre}" cantidad actual=${item?.cantidad}`);
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
            console.log(`[POS:ui] − menos → idx=${idx} item="${item?.nombre}" cantidad actual=${item?.cantidad} es_regalo=${item?.es_regalo}`);
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
    console.log("[POS:ui] initBotonCobrar");
    const btn = document.getElementById("btn-cobrar");
    if (!btn) { console.warn("[POS:ui] btn-cobrar NO encontrado"); return; }

    btn.onclick = () => {
        console.log("[POS:ui] click COBRAR");
        const error = validarStock();
        if (error) return mostrarAlertaUI(error, "error");

        // Abre el modal ya inicializado con el total correcto
        abrirModalPago();
    };
}


// ============================================================
// 7. Descuento (desplegable: 10% / 15%, mutuamente excluyentes)
// ============================================================

function initDescuentoUI() {
    console.log("[POS:ui] initDescuentoUI");
    const trigger  = document.getElementById("btn-descuento-trigger");
    const dropdown = document.getElementById("pos-descuento-dropdown");
    if (!trigger || !dropdown) return;

    const opciones = Array.from(dropdown.querySelectorAll(".pos-descuento-opcion"));

    // Refleja el % activo en el trigger y resalta la opción elegida
    function pintarEstado() {
        const activo = descuentoPct > 0;
        trigger.classList.toggle("pos-btn-descuento--activo", activo);
        trigger.textContent = activo ? `${descuentoPct}% ON` : "¿Descuento?";
        opciones.forEach(op => {
            op.classList.toggle(
                "pos-descuento-opcion--activo",
                parseInt(op.dataset.pct, 10) === descuentoPct
            );
        });
    }

    const abrir  = () => { dropdown.removeAttribute("hidden"); trigger.setAttribute("aria-expanded", "true"); };
    const cerrar = () => { dropdown.setAttribute("hidden", ""); trigger.setAttribute("aria-expanded", "false"); };

    trigger.addEventListener("click", (e) => {
        e.stopPropagation();
        if (dropdown.hasAttribute("hidden")) abrir();
        else cerrar();
    });

    // Selección: si presionas el mismo % activo → se apaga (ambos quedan libres);
    // si presionas otro → ese queda activo y el anterior se apaga.
    opciones.forEach(op => {
        op.addEventListener("click", (e) => {
            e.stopPropagation();
            const pct = parseInt(op.dataset.pct, 10);
            setDescuentoPct(descuentoPct === pct ? 0 : pct);
            pintarEstado();
            actualizarTotales();
            renderCarritoUI();
        });
    });

    // Cerrar al hacer click afuera o con Escape (igual que el menú "¿Estresao?")
    document.addEventListener("click", (e) => {
        if (!dropdown.contains(e.target) && e.target !== trigger) cerrar();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") cerrar();
    });

    pintarEstado();
}


// ============================================================
// 8. Modal de pago — con cálculo en vivo
// ============================================================

// Se declara aquí para que initBotonCobrar pueda llamarla
// después de que initModalPago la defina
let abrirModalPago = () => {};

function initModalPago() {
    console.log("[POS:ui] initModalPago");
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

    // Enter en cualquier campo del modal → confirmar pago
    [inputEfectivo, inputTarjeta].forEach(inp => {
        inp.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); btnConfirmar.click(); }
        });
    });

    // Inicializa el modal con valores limpios cada vez que se abre
    abrirModalPago = () => {
        const total = totalConDescuento();
        console.log(`[POS:ui] abrirModalPago → total=$${total.toFixed(2)}`);
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
    btnCerrar.onclick = () => {
        console.log("[POS:ui] cerrar modal pago");
        modal.classList.add("pos-modal--hidden");
    };

    // Confirmar y procesar la venta
    btnConfirmar.onclick = async () => {
        const efectivo = parseFloat(inputEfectivo.value || 0);
        const tarjeta  = parseFloat(inputTarjeta.value  || 0);
        console.log(`[POS:ui] confirmar-pago → efectivo=${efectivo} tarjeta=${tarjeta}`);

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
                    venta_id:         data.venta_id,
                    url_html:         data.url_html,
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
    console.log("[POS:ui] initModalResultado");
    const modal        = document.getElementById("modal-resultado");
    const btnCerrar    = document.getElementById("cerrar-resultado");
    const boxImpresion = document.getElementById("resultado-impresion");

    document.addEventListener("pago-exito", async (e) => {
        const { total, cambio, pagado_efectivo, pagado_tarjeta, ticket_texto, venta_id, url_html } = e.detail;
        console.log(`[POS:ui] pago-exito → venta_id=${venta_id} total=${total} cambio=${cambio}`);

        document.getElementById("resultado-total-venta").textContent = total.toFixed(2);
        document.getElementById("resultado-recibido").textContent    = (pagado_efectivo + pagado_tarjeta).toFixed(2);
        document.getElementById("resultado-cambio").textContent      = cambio.toFixed(2);

        boxImpresion.textContent = "Enviando a impresora...";
        boxImpresion.className   = "pos-resultado-impresion";

        modal.classList.remove("pos-modal--hidden");

        const res = await imprimirTicket(ticket_texto, venta_id);

        if (res.ok) {
            boxImpresion.textContent = "✓ Ticket enviado a la impresora.";
            boxImpresion.className   = "pos-resultado-impresion pos-resultado-impresion--ok";
        } else if (res.noConfig) {
            boxImpresion.innerHTML = `⚙ Configura la impresora (botón <b>🖨 Config</b> arriba) para imprimir automáticamente.`;
            boxImpresion.className = "pos-resultado-impresion pos-resultado-impresion--warn";
        } else {
            const motivo = res.noAgent ? "Agente POS no disponible. Abre pos_agent.exe." : (res.error || "Error de impresión.");
            const link   = url_html ? `<a href="${url_html}" target="_blank" style="color:inherit;font-weight:900;text-decoration:underline">Ver ticket</a>` : "";
            boxImpresion.innerHTML = `⚠ ${motivo} ${link}`;
            boxImpresion.className = "pos-resultado-impresion pos-resultado-impresion--error";
        }
    });

    btnCerrar.onclick = () => modal.classList.add("pos-modal--hidden");

    // Enter cuando el modal de resultado está abierto → cerrar (Aceptar)
    document.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        if (modal.classList.contains("pos-modal--hidden")) return;
        e.preventDefault();
        btnCerrar.click();
    });
}


// ============================================================
// 10. Modal de cobro rápido — sumadora integrada
// ============================================================

function initModalCobroRapido() {
    console.log("[POS:ui] initModalCobroRapido");

    // ── Estado de la sumadora ──
    let _buf        = "";   // número que se está tecleando
    let _accum      = 0;    // acumulador (total corriente)
    let _lastOp     = "+";  // operación pendiente para aplicar al próximo buffer
    let _multiplier = null; // factor × pendiente (5 × 12.50 → se guarda 5 aquí)

    function _display() { return document.getElementById("cr-display"); }
    function _totalEl() { return document.getElementById("cr-total"); }
    function _tape()    { return document.getElementById("cr-tape"); }

    function _syncDisplay() {
        const d = _display();
        if (d) d.textContent = _buf || "0";
    }
    function _syncTotal() {
        const t = _totalEl();
        if (t) t.textContent = `$${_accum.toFixed(2)}`;
    }

    function _addTapeLine(val, op, isTotal = false, label = null) {
        const tape = _tape();
        if (!tape) return;
        const row = document.createElement("div");
        if (isTotal) {
            row.style.cssText = "display:flex;justify-content:space-between;font-weight:900;border-top:2px solid #000;margin-top:3px;padding-top:2px;";
            row.innerHTML = `<span>TOTAL</span><span>$${val.toFixed(2)}</span>`;
        } else {
            const color = op === "−" ? "#dc2626" : "#16a34a";
            const leftText = label ?? op;
            row.style.cssText = `display:flex;justify-content:space-between;color:${color};`;
            row.innerHTML = `<span>${leftText}</span><span>$${val.toFixed(2)}</span>`;
        }
        tape.appendChild(row);
        tape.scrollTop = tape.scrollHeight;
    }

    function _pressKey(key) {
        // ── Dígitos ──
        if (key >= "0" && key <= "9") {
            if (_buf.replace(".", "").length >= 10) return;
            _buf = (_buf === "0" || _buf === "") ? key : _buf + key;
            _syncDisplay();
            return;
        }
        if (key === "00") {
            if (!_buf || _buf === "0") return;
            if (_buf.replace(".", "").length >= 9) return;
            _buf += "00";
            _syncDisplay();
            return;
        }
        if (key === ".") {
            if (_buf.includes(".")) return;
            _buf = (_buf || "0") + ".";
            _syncDisplay();
            return;
        }
        if (key === "Backspace") {
            _buf = _buf.slice(0, -1);
            _syncDisplay();
            return;
        }

        // ── C: si hay buffer lo limpia; si no, limpia todo ──
        if (key === "C") {
            if (_buf || _multiplier !== null) {
                _buf = "";
                _multiplier = null;
                _syncDisplay();
            } else {
                _accum  = 0;
                _lastOp = "+";
                const tape = _tape();
                if (tape) tape.innerHTML = "";
                _syncDisplay();
                _syncTotal();
            }
            return;
        }

        // ── Multiplicación: guarda el factor y espera el precio ──
        if (key === "x") {
            _multiplier = parseFloat(_buf || "1");
            _buf = "";
            // Muestra el factor en el display para que el usuario sepa que está en modo ×
            const d = _display();
            if (d) d.textContent = `${_multiplier} ×`;
            return;
        }

        // ── Operaciones +  −  = ──
        if (key === "+" || key === "-" || key === "=") {
            let val = parseFloat(_buf || "0");

            // Si hay un multiplicador pendiente, aplicarlo al precio unitario
            const tapeLabel = _multiplier !== null
                ? `${_multiplier}×$${val.toFixed(2)}`
                : null;
            if (_multiplier !== null) {
                val = val * _multiplier;
                _multiplier = null;
            }

            // Aplicar operación pendiente al acumulador
            if (_lastOp === "+") _accum += val;
            else                 _accum -= val;

            // Agregar línea a la cinta si había algo en el buffer
            if (_buf !== "") {
                _addTapeLine(val, _lastOp === "+" ? "+" : "−", false, tapeLabel);
            }

            _buf    = "";
            _lastOp = key === "=" ? "+" : key;
            _syncDisplay();
            _syncTotal();

            // = imprime línea de total en la cinta (el input de precio es independiente)
            if (key === "=") {
                _addTapeLine(_accum, null, true);
            }
            return;
        }
    }

    // Exponer para botones del HTML
    window._crPressKey = _pressKey;

    // ── Abrir / cerrar ──
    function abrirCobroRapido() {
        console.log("[POS:ui] abrirCobroRapido");
        _buf = ""; _accum = 0; _lastOp = "+"; _multiplier = null;
        _syncDisplay();
        _syncTotal();
        const tape = _tape();
        if (tape) tape.innerHTML = "";
        const err = document.getElementById("cr-error");
        if (err) err.style.display = "none";
        const precioInput = document.getElementById("cr-precio");
        if (precioInput) precioInput.value = "";
        const m = document.getElementById("modal-cobro-rapido");
        if (m) {
            m.style.display = "flex";
            setTimeout(() => precioInput?.focus(), 50);
        }
    }

    window.abrirCobroRapido = abrirCobroRapido;

    window.cerrarCobroRapido = function () {
        console.log("[POS:ui] cerrarCobroRapido");
        const m = document.getElementById("modal-cobro-rapido");
        if (m) m.style.display = "none";
        document.getElementById("scan-input")?.focus();
    };

    // ── Confirmar: lee el campo de precio (independiente de la calculadora) ──
    window.confirmarCobroRapido = function () {
        console.log("[POS:ui] confirmarCobroRapido");
        const precioInput = document.getElementById("cr-precio");
        const precio = parseFloat(precioInput?.value || "0");

        const err = document.getElementById("cr-error");
        if (!precio || precio <= 0) {
            err.textContent = "Escribe un precio mayor a $0 en el campo de precio";
            err.style.display = "block";
            precioInput?.focus();
            return;
        }
        err.style.display = "none";
        agregarCobroRapido(Math.round(precio * 100) / 100);
        window.cerrarCobroRapido();
    };

    // Enter en el input de precio confirma
    document.getElementById("cr-precio")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter")  { e.preventDefault(); window.confirmarCobroRapido(); }
        if (e.key === "Escape") { e.preventDefault(); window.cerrarCobroRapido(); }
    });

    // ── Clicks en los botones [data-cr] ──
    document.querySelectorAll("[data-cr]").forEach(btn => {
        btn.addEventListener("mousedown", (e) => e.preventDefault()); // evita perder foco
        btn.addEventListener("click", () => _pressKey(btn.dataset.cr));
    });

    // ── Teclado físico → calculadora (solo cuando el foco NO está en el input de precio) ──
    document.addEventListener("keydown", (e) => {
        const m = document.getElementById("modal-cobro-rapido");
        if (m?.style.display !== "flex") return;
        // Si el foco está en el input de precio → dejar que el input maneje todo
        if (document.activeElement?.id === "cr-precio") return;

        const map = {
            "0":"0","1":"1","2":"2","3":"3","4":"4",
            "5":"5","6":"6","7":"7","8":"8","9":"9",
            ".":".","+":" +","-":"-","=":"=","*":"x",
        };
        const numpadMap = {
            "Numpad0":"0","Numpad1":"1","Numpad2":"2","Numpad3":"3","Numpad4":"4",
            "Numpad5":"5","Numpad6":"6","Numpad7":"7","Numpad8":"8","Numpad9":"9",
            "NumpadDecimal":".","NumpadAdd":"+","NumpadSubtract":"-",
            "NumpadEnter":"=","NumpadEqual":"=","NumpadMultiply":"x",
        };

        if (e.key === "Escape") { e.preventDefault(); window.cerrarCobroRapido(); return; }
        if (e.key === "Backspace") { e.preventDefault(); _pressKey("Backspace"); return; }
        if (e.key === "Delete")    { e.preventDefault(); _pressKey("C");         return; }

        const mapped = map[e.key] ?? numpadMap[e.code];
        if (mapped !== undefined) {
            e.preventDefault();
            _pressKey(mapped.trim());
        }
    });

    // ── R desde teclado fuera de inputs ──
    document.addEventListener("keydown", (e) => {
        if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
        if (e.key === "r" || e.key === "R") { e.preventDefault(); abrirCobroRapido(); }
    });

    document.getElementById("modal-cobro-rapido")?.addEventListener("click", function (e) {
        if (e.target === this) window.cerrarCobroRapido();
    });
}


// ============================================================
// 11. Alertas UI
// ============================================================

export function mostrarAlertaUI(msg, tipo = "ok") {
    console.log(`[POS:ui] mostrarAlertaUI [${tipo}]: "${msg}"`);
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