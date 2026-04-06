import { carrito, setDescuentoActivo } from "./core.js";

// ============================================================
// REGLA GLOBAL AUTO
// ============================================================

export function calcularModoGlobal() {
    const totalPiezas = carrito.reduce((acc, p) => acc + p.cantidad, 0);

    const totalValor = carrito.reduce((acc, p) => {
        return acc + (p.precios.men * p.cantidad);
    }, 0);

    if (totalPiezas >= 12) return "DOC";
    if (totalPiezas >= 6 && totalValor > 80) return "MAY";
    return "MEN";
}

// ============================================================
// APLICAR PRECIOS A CADA PRODUCTO
// ============================================================

export function aplicarPreciosGlobales() {
    const modoGlobal = calcularModoGlobal();

    carrito.forEach(item => {

        let modoPrecio = modoGlobal;

        if (item.modo_precio !== "AUTO") {
            modoPrecio = item.modo_precio;
        }

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
