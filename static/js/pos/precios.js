import { carrito, piezasItem } from "./core.js";

console.log("[POS:precios] Módulo cargado");

// ============================================================
// REGLAS DE NEGOCIO
// ============================================================
// MAY  → 6+ productos (mismo o distinto) con valor total > $80
// DOC  → 12+ unidades del MISMO producto (solo ese item)
// MEN  → todo lo demás
// PRES → precio por cantidad (Caja, Media docena…): precio fijo, no lo
//        tocan estas reglas; sus piezas sí cuentan para el mayoreo de lo demás
// ============================================================

export function aplicarPreciosGlobales() {

    // --- Paso 1: Calcular modo global (MAY vs MEN) ignorando servicios y regalos ---
    const productos = carrito.filter(p => !p.es_servicio && !p.es_regalo);
    const totalPiezas = productos.reduce((acc, p) => acc + piezasItem(p), 0);
    const totalValor  = productos.reduce((acc, p) => acc + (p.precios.men * piezasItem(p)), 0);

    let modoGlobal = "MEN";
    if (totalPiezas >= 6 && totalValor > 80) {
        modoGlobal = "MAY";
    }

    console.log(`[POS:precios] aplicarPreciosGlobales → totalPiezas=${totalPiezas} totalValor=$${totalValor.toFixed(2)} modoGlobal=${modoGlobal}`);

    // --- Paso 2: Aplicar a cada item (saltar servicios y regalos) ---
    carrito.forEach(item => {
        if (item.es_servicio || item.es_regalo) return;

        if (item.presentacion) {
            item.modo_precio     = "PRES";
            item.modo_resuelto   = "PRES";
            item.precio_aplicado = Number(item.presentacion.precio);
            return;
        }

        let modoPrecio = item.modo_precio;

        if (modoPrecio === "AUTO") {
            const tieneDoc = item.precios.doc && item.precios.doc > 0;
            if (item.cantidad >= 12 && tieneDoc) {
                modoPrecio = "DOC";
            } else {
                modoPrecio = modoGlobal;
            }
        }

        const tieneDoc = item.precios.doc && item.precios.doc > 0;
        if (modoPrecio === "DOC" && !tieneDoc) {
            modoPrecio = "MAY";
        }

        const precioAnterior = item.precio_aplicado;
        item.modo_resuelto = modoPrecio;

        if (modoPrecio === "MEN") item.precio_aplicado = item.precios.men;
        else if (modoPrecio === "MAY") item.precio_aplicado = item.precios.may;
        else if (modoPrecio === "DOC") item.precio_aplicado = item.precios.doc;
        else item.precio_aplicado = item.precios.men;

        if (precioAnterior !== item.precio_aplicado) {
            console.log(`[POS:precios]   "${item.nombre}" modo=${modoPrecio} precio: $${precioAnterior.toFixed(2)} → $${item.precio_aplicado.toFixed(2)}`);
        }
    });
}
