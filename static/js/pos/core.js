// core.js — Estado global del POS

// ============================================================
// 1. Estado global del carrito
// ============================================================

export let carrito = [];


// ============================================================
// 2. Estado del descuento
// ============================================================

export let descuentoActivo = false;

export function setDescuentoActivo(valor) {
    descuentoActivo = valor;
}

export function resetDescuento() {
    descuentoActivo = false;
}


// ============================================================
// 3. Totales dinámicos (FUNCIONES REALES)
// ============================================================

// Total sin descuento
export function totalSinDescuento() {
    return carrito.reduce((acc, p) => acc + p.precio_aplicado * p.cantidad, 0);
}

// Total con descuento
export function totalConDescuento() {
    let total = totalSinDescuento();
    if (descuentoActivo) total *= 0.90;
    return total;
}


// ============================================================
// 4. Normalizador (buscador)
// ============================================================

export function normalizar(txt) {
    return txt
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}


// ============================================================
// 5. CSRF cookie
// ============================================================

export function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            }
        }
    }
    return cookieValue;
}


// ============================================================
// 6. Callback para notificar cambios del carrito
// ============================================================

export let onCarritoActualizado = () => {};

export function setOnCarritoActualizado(fn) {
    onCarritoActualizado = fn;
}
