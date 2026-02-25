// core.js

export let carrito = [];
export let descuentoActivo = false;

export let totalSinDescuento = 0;
export let totalConDescuento = 0;

// Actualiza totales globales
export function setTotales(sin, con) {
    totalSinDescuento = sin;
    totalConDescuento = con;
}

// Activa o desactiva el descuento
export function setDescuentoActivo(valor) {
    descuentoActivo = valor;
}

// Resetea el descuento después de una venta o cuando limpias el carrito
export function resetDescuento() {
    descuentoActivo = false;
}

// Normaliza texto (buscador)
export function normalizar(txt) {
    return txt
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "");
}

// CSRF cookie
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