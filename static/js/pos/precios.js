import { carrito, setTotales, setDescuentoActivo } from "./core.js";

// ============================================================
// REGLA GLOBAL AUTO
// 6+ piezas y total > 80 → MAY
// 12+ piezas → DOC (solo si existe precio DOC)
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

        // Si el cajero eligió MEN/MAY/DOC, se respeta
        if (item.modo_precio !== "AUTO") {
            modoPrecio = item.modo_precio;
        }

        // Verificar si el producto tiene precio DOC
        const tieneDoc = item.precios.doc && item.precios.doc > 0;

        // 🔥 Si AUTO o el cajero quieren DOC pero no existe → degradar a MAY
        if (modoPrecio === "DOC" && !tieneDoc) {
            modoPrecio = "MAY";
        }

        // 🔥 Guardar el modo realmente aplicado (para el borde negro)
        item.modo_resuelto = modoPrecio;

        // Asignar precio según modo final
        if (modoPrecio === "MEN") item.precio_aplicado = item.precios.men;
        else if (modoPrecio === "MAY") item.precio_aplicado = item.precios.may;
        else if (modoPrecio === "DOC") item.precio_aplicado = item.precios.doc;
        else item.precio_aplicado = item.precios.men; // fallback seguro
    });
}

// ============================================================
// DESCUENTO DEL 10%
// ============================================================

export function aplicarDescuento10() {

    const totalSin = carrito.reduce((acc, p) => {
        return acc + (p.precio_aplicado * p.cantidad);
    }, 0);

    const totalCon = totalSin * 0.90;

    setTotales(totalSin, totalCon);
    setDescuentoActivo(true);
}

export function quitarDescuento10() {

    const totalSin = carrito.reduce((acc, p) => {
        return acc + (p.precio_aplicado * p.cantidad);
    }, 0);

    setTotales(totalSin, totalSin);
    setDescuentoActivo(false);
}