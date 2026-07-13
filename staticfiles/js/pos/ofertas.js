// ofertas.js — Aplicación automática de descuentos en el POS

import { carrito } from "./core.js";

console.log("[POS:ofertas] Módulo cargado");

export function aplicarOfertas() {
    const ofertas = window.OFERTAS || [];

    carrito.forEach(i => {
        if (_esElegible(i)) { i.oferta_activa = null; i.precio_sin_oferta = null; }
    });

    if (!ofertas.length) return;

    let aplicadas = 0;
    for (const oferta of ofertas) {
        if (oferta.aplica_a === "producto") {
            if (_aplicarAProducto(oferta)) aplicadas++;
        } else if (oferta.aplica_a === "categoria") {
            if (_aplicarACategoria(oferta)) aplicadas++;
        }
    }

    if (aplicadas > 0) {
        console.log(`[POS:ofertas] aplicarOfertas → ${aplicadas} oferta(s) aplicada(s)`);
    }
}

export function initOfertas() {
    console.log(`[POS:ofertas] initOfertas — ofertas disponibles: ${(window.OFERTAS || []).length}`);
}

function _esElegible(item) {
    return !item.es_servicio && !item.es_regalo;
}

function _matchesCategoria(item, oferta) {
    return item.subcategoria_id == oferta.categoria_id ||
           item.cat_padre_id    == oferta.categoria_id;
}

function _matchesAtributos(item, oferta) {
    const filtros = oferta.filtros_atributos;
    if (!filtros || filtros.length === 0) return true;
    const attrs = item.atributos || {};
    return filtros.every(f => {
        const val = attrs[f.nombre];
        return val !== undefined && val.toLowerCase() === f.valor.toLowerCase();
    });
}

function _aplicarAProducto(oferta) {
    const item = carrito.find(i => _esElegible(i) && i.id == oferta.producto_id);
    if (!item) return false;
    console.log(`[POS:ofertas] aplicando oferta "${oferta.nombre}" (${oferta.tipo}) a "${item.nombre}"`);
    _aplicarTipoItem(item, oferta);
    return true;
}

function _aplicarACategoria(oferta) {
    const items = carrito.filter(
        i => _esElegible(i) && _matchesCategoria(i, oferta) && _matchesAtributos(i, oferta)
    );
    if (!items.length) return false;

    console.log(`[POS:ofertas] aplicando oferta "${oferta.nombre}" (${oferta.tipo}) a ${items.length} item(s) de categoría`);

    if (oferta.tipo === "nxprecio") {
        _aplicarNxPrecioCategoria(oferta, items);
    } else {
        items.forEach(i => _aplicarTipoItem(i, oferta));
    }
    return true;
}

function _aplicarNxPrecioCategoria(oferta, items) {
    const N         = parseInt(oferta.cantidad_n);
    const precioUnit = parseFloat(oferta.valor) / N;

    const totalQty = items.reduce((s, i) => s + i.cantidad, 0);
    let quotaDesc  = Math.floor(totalQty / N) * N;

    if (quotaDesc === 0) {
        console.log(`[POS:ofertas] nxprecio "${oferta.nombre}": sin grupos completos (qty=${totalQty} N=${N})`);
        return;
    }

    console.log(`[POS:ofertas] nxprecio "${oferta.nombre}": ${quotaDesc}/${totalQty} unidades con descuento`);

    const sorted = [...items].sort((a, b) => b.precio_aplicado - a.precio_aplicado);

    for (const item of sorted) {
        if (quotaDesc <= 0) break;

        item.oferta_activa     = oferta;
        item.precio_sin_oferta = item.precio_aplicado;

        if (quotaDesc >= item.cantidad) {
            item.precio_aplicado = precioUnit;
            quotaDesc -= item.cantidad;
        } else {
            const normal = item.precio_sin_oferta;
            item.precio_aplicado =
                (quotaDesc * precioUnit + (item.cantidad - quotaDesc) * normal) / item.cantidad;
            quotaDesc = 0;
        }
    }
}

function _aplicarTipoItem(item, oferta) {
    const base = item.precio_aplicado;
    const q    = item.cantidad;

    // nxprecio: solo aplica si hay al menos un grupo completo de N unidades
    if (oferta.tipo === "nxprecio") {
        const N          = parseInt(oferta.cantidad_n);
        const precioUnit = parseFloat(oferta.valor) / N;
        const conDesc    = Math.floor(q / N) * N;   // unidades en grupos completos

        if (conDesc === 0) {
            console.log(`[POS:ofertas]   "${item.nombre}" nxprecio: qty=${q} < N=${N}, no aplica`);
            return;
        }

        item.oferta_activa     = oferta;
        item.precio_sin_oferta = base;

        // Si todas las unidades caben en grupos completos → precio unitario promocional
        // Si sobran unidades → precio ponderado entre las con descuento y las sin descuento
        item.precio_aplicado = conDesc === q
            ? precioUnit
            : (conDesc * precioUnit + (q - conDesc) * base) / q;

        console.log(`[POS:ofertas]   "${item.nombre}" nxprecio ${conDesc}/${q} uds: $${base.toFixed(2)} → $${item.precio_aplicado.toFixed(2)}`);
        return;
    }

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
            const pagados = Math.ceil(q / 2);
            item.precio_aplicado = (pagados * base) / q;
            break;
        }
    }

    console.log(`[POS:ofertas]   "${item.nombre}" ${oferta.tipo}: $${base.toFixed(2)} → $${item.precio_aplicado.toFixed(2)}`);
}
