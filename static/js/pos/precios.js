// precios.js

import { carrito, setTotales, setDescuentoActivo } from "./core.js";

// Regla: 6+ piezas y total > 80 → MAY
//        12+ piezas → DOC
export function calcularModoGlobal() {
    const totalPiezas = carrito.reduce((acc, p) => acc + p.cantidad, 0);

    const totalValor = carrito.reduce((acc, p) => {
        return acc + (p.precios.men * p.cantidad);
    }, 0);

    if (totalPiezas >= 12) return "DOC";
    if (totalPiezas >= 6 && totalValor > 80) return "MAY";
    return "MEN";
}

export function aplicarPreciosGlobales() {
    const modoGlobal = calcularModoGlobal();

    carrito.forEach(item => {
        // 1) Qué modo se usa para el PRECIO
        let modoPrecio = modoGlobal;

        // Si el usuario eligió MEN/MAY/DOC, se respeta
        if (item.modo_precio !== "AUTO") {
            modoPrecio = item.modo_precio;
        }

        // 2) Aplicar precio según modoPrecio
        if (modoPrecio === "MEN") item.precio_aplicado = item.precios.men;
        if (modoPrecio === "MAY") item.precio_aplicado = item.precios.may;
        if (modoPrecio === "DOC") item.precio_aplicado = item.precios.doc;

        // OJO: aquí YA NO tocamos item.modo_precio
    });
}

// ============================================================
// 🔥 FUNCIÓN EXTRA: DESCUENTO DEL 10%
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