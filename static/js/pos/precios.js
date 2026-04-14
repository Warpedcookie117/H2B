import { carrito, setDescuentoActivo } from "./core.js";

// ============================================================
// REGLAS DE NEGOCIO
// ============================================================
// MAY  → 6+ productos (mismo o distinto) con valor total > $80
// DOC  → 12+ unidades del MISMO producto (solo ese item)
// MEN  → todo lo demás
// ============================================================

export function aplicarPreciosGlobales() {

    // --- Paso 1: Calcular modo global (MAY vs MEN) ---
    const totalPiezas = carrito.reduce((acc, p) => acc + p.cantidad, 0);
    const totalValor = carrito.reduce((acc, p) => {
        return acc + (p.precios.men * p.cantidad);
    }, 0);

    let modoGlobal = "MEN";
    if (totalPiezas >= 6 && totalValor > 80) {
        modoGlobal = "MAY";
    }

    // --- Paso 2: Aplicar a cada item ---
    carrito.forEach(item => {

        let modoPrecio = item.modo_precio;

        if (modoPrecio === "AUTO") {
            // DOC solo si ESE item tiene 12+ unidades y tiene precio de docena
            const tieneDoc = item.precios.doc && item.precios.doc > 0;

            if (item.cantidad >= 12 && tieneDoc) {
                modoPrecio = "DOC";
            } else {
                modoPrecio = modoGlobal; // MAY o MEN según reglas globales
            }
        }

        // Si el modo resuelto es DOC pero no tiene precio de docena, bajar a MAY
        const tieneDoc = item.precios.doc && item.precios.doc > 0;
        if (modoPrecio === "DOC" && !tieneDoc) {
            modoPrecio = "MAY";
        }

        item.modo_resuelto = modoPrecio;

        if (modoPrecio === "MEN") item.precio_aplicado = item.precios.men;
        else if (modoPrecio === "MAY") item.precio_aplicado = item.precios.may;
        else if (modoPrecio === "DOC") item.precio_aplicado = item.precios.doc;
        else item.precio_aplicado = item.precios.men;
    });
}

// ============================================================
// DESCUENTO DEL 10%
// ============================================================

export function aplicarDescuento10() {
    setDescuentoActivo(true);
}

export function quitarDescuento10() {
    setDescuentoActivo(false);
}
