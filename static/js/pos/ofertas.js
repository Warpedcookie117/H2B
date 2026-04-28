// ofertas.js — Aplicación automática de descuentos en el POS

import { carrito } from "./core.js";

// ============================================================
// API pública
// ============================================================

export function aplicarOfertas() {
    const ofertas = window.OFERTAS || [];

    // Limpia estado de oferta anterior en cada ítem para evitar badges fantasma
    carrito.forEach(i => {
        if (_esElegible(i)) { i.oferta_activa = null; i.precio_sin_oferta = null; }
    });

    if (!ofertas.length) return;

    for (const oferta of ofertas) {
        if (oferta.aplica_a === "producto") {
            _aplicarAProducto(oferta);
        } else if (oferta.aplica_a === "categoria") {
            _aplicarACategoria(oferta);
        }
    }
}

export function initOfertas() { /* se llama desde pos.js, sin setup propio */ }

// ============================================================
// Helpers de filtrado
// ============================================================

function _esElegible(item) {
    return !item.es_servicio && !item.es_regalo;
}

function _matchesCategoria(item, oferta) {
    return item.subcategoria_id == oferta.categoria_id ||
           item.cat_padre_id    == oferta.categoria_id;
}

// Devuelve true si el item cumple TODOS los filtros de atributo de la oferta.
// Un array vacío significa sin restricción.
function _matchesAtributos(item, oferta) {
    const filtros = oferta.filtros_atributos;
    if (!filtros || filtros.length === 0) return true;
    const attrs = item.atributos || {};
    return filtros.every(f => {
        const val = attrs[f.nombre];
        return val !== undefined && val.toLowerCase() === f.valor.toLowerCase();
    });
}

// ============================================================
// Despacho por aplica_a
// ============================================================

function _aplicarAProducto(oferta) {
    const item = carrito.find(i => _esElegible(i) && i.id == oferta.producto_id);
    if (!item) return;
    _aplicarTipoItem(item, oferta);
}

function _aplicarACategoria(oferta) {
    const items = carrito.filter(
        i => _esElegible(i) && _matchesCategoria(i, oferta) && _matchesAtributos(i, oferta)
    );
    if (!items.length) return;

    if (oferta.tipo === "nxprecio") {
        // Agrupación N en N entre productos mezclados de la categoría
        _aplicarNxPrecioCategoria(oferta, items);
    } else {
        // porcentaje, fijo, 2x1 → aplica a cada item de la categoría por separado
        items.forEach(i => _aplicarTipoItem(i, oferta));
    }
}

// ============================================================
// Agrupación N × $X entre ítems de la misma categoría
//
// Regla: cada grupo completo de N unidades cuesta $X total.
// Si sobran unidades sin completar grupo, van a precio normal.
// Los productos más caros reciben el descuento primero (beneficio al cliente).
// ============================================================

function _aplicarNxPrecioCategoria(oferta, items) {
    const N         = parseInt(oferta.cantidad_n);
    const precioUnit = parseFloat(oferta.valor) / N;

    const totalQty = items.reduce((s, i) => s + i.cantidad, 0);
    let quotaDesc  = Math.floor(totalQty / N) * N; // unidades que entran en grupos completos

    if (quotaDesc === 0) return; // ni un grupo completo → sin descuento

    // Los más caros primero para maximizar el ahorro del cliente
    const sorted = [...items].sort((a, b) => b.precio_aplicado - a.precio_aplicado);

    for (const item of sorted) {
        if (quotaDesc <= 0) break;

        item.oferta_activa     = oferta;
        item.precio_sin_oferta = item.precio_aplicado;

        if (quotaDesc >= item.cantidad) {
            // Todas las unidades de este SKU entran al precio de oferta
            item.precio_aplicado = precioUnit;
            quotaDesc -= item.cantidad;
        } else {
            // El ítem se parte: quotaDesc unidades al precio de oferta, el resto normal
            const normal = item.precio_sin_oferta;
            item.precio_aplicado =
                (quotaDesc * precioUnit + (item.cantidad - quotaDesc) * normal) / item.cantidad;
            quotaDesc = 0;
        }
    }
}

// ============================================================
// Aplicar tipo de oferta a un solo ítem
// ============================================================

function _aplicarTipoItem(item, oferta) {
    const base = item.precio_aplicado;
    const q    = item.cantidad;

    item.oferta_activa     = oferta;
    item.precio_sin_oferta = base;

    switch (oferta.tipo) {
        case "porcentaje":
            item.precio_aplicado = base * (1 - parseFloat(oferta.valor) / 100);
            break;

        case "fijo":
            item.precio_aplicado = Math.max(0, base - parseFloat(oferta.valor));
            break;

        case "2x1": {
            // Cada 2 unidades paga 1. Si lleva 3: paga 2. Si lleva 4: paga 2, etc.
            const pagados = Math.ceil(q / 2);
            item.precio_aplicado = (pagados * base) / q;
            break;
        }

        case "nxprecio":
            // Producto específico: precio plano por unidad = valor / N
            item.precio_aplicado = parseFloat(oferta.valor) / parseInt(oferta.cantidad_n);
            break;
    }
}
