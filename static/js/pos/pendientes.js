// pendientes.js — Cuentas pendientes: pausar la venta actual para atender
// a otro cliente sin perder lo que ya se había marcado, y retomarla después.
// Viven solo en localStorage de esta caja — nunca tocan el backend, porque
// una cuenta pendiente no es una Venta hasta que se cobra.

import { carrito, descuentoPct, setDescuentoPct } from "./core.js";
import { obtenerSnapshotCarrito, cargarCarrito, limpiarCarrito } from "./carrito.js";

const STORAGE_KEY = "pos_cuentas_pendientes";
const MAX_PENDIENTES = 3;

let pendientes = [];

console.log("[POS:pendientes] Módulo cargado");

function cargarDeStorage() {
    try {
        pendientes = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    } catch {
        pendientes = [];
    }
}

function guardarEnStorage() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(pendientes));
}

// Reutiliza el número (1..MAX) más bajo que esté libre, para que las
// etiquetas no crezcan sin control aunque se vayan cobrando/borrando.
function siguienteNumero() {
    for (let n = 1; n <= MAX_PENDIENTES; n++) {
        if (!pendientes.some(p => p.num === n)) return n;
    }
    return null;
}

function renderTabs() {
    const cont = document.getElementById("pos-pendientes-tabs");
    if (!cont) return;

    if (pendientes.length === 0) {
        cont.innerHTML = "";
        cont.hidden = true;
        return;
    }
    cont.hidden = false;

    cont.innerHTML = [...pendientes]
        .sort((a, b) => a.num - b.num)
        .map(p => `
            <span class="pos-pendiente-tab" data-num="${p.num}">
                Cuenta pendiente ${p.num}
                <button type="button" class="pos-pendiente-tab-x" data-num="${p.num}" title="Eliminar cuenta pendiente">×</button>
            </span>
        `).join("");
}

// Guarda el carrito activo (si lo hay) como una nueva cuenta pendiente y
// deja el carrito vacío. No persiste ni renderiza — lo hace quien la llame.
function _avisarDescuentoCambio() {
    document.dispatchEvent(new CustomEvent("pos:descuento-externo"));
}

function _parkearActiva() {
    const num = siguienteNumero();
    if (num == null) return false;
    pendientes.push({
        num,
        items: obtenerSnapshotCarrito(),
        descuentoPct,
    });
    limpiarCarrito();
    setDescuentoPct(0);
    _avisarDescuentoCambio();
    return true;
}

function guardarComoPendiente() {
    console.log("[POS:pendientes] guardarComoPendiente");
    if (carrito.length === 0) {
        alert("El carrito está vacío — no hay nada que guardar como pendiente.");
        return;
    }
    if (pendientes.length >= MAX_PENDIENTES) {
        alert(`Ya tienes ${MAX_PENDIENTES} cuentas pendientes. Cobra o elimina alguna antes de guardar otra.`);
        return;
    }
    _parkearActiva();
    guardarEnStorage();
    renderTabs();
}

function restaurarPendiente(num) {
    console.log(`[POS:pendientes] restaurarPendiente → num=${num}`);
    const i = pendientes.findIndex(p => p.num === num);
    if (i === -1) return;

    // Se quita primero para liberar su número — así siempre hay lugar
    // para parquear la venta activa (si tenía algo) sin chocar con el límite.
    const pendiente = pendientes.splice(i, 1)[0];

    if (carrito.length > 0) _parkearActiva();

    cargarCarrito(pendiente.items);
    setDescuentoPct(pendiente.descuentoPct || 0);
    _avisarDescuentoCambio();
    guardarEnStorage();
    renderTabs();
}

function eliminarPendiente(num) {
    const pendiente = pendientes.find(p => p.num === num);
    if (!pendiente) return;
    if (!confirm(`¿Eliminar la Cuenta pendiente ${num}? Se perderá lo que tenía guardado.`)) return;

    console.log(`[POS:pendientes] eliminarPendiente → num=${num}`);
    pendientes = pendientes.filter(p => p.num !== num);
    guardarEnStorage();
    renderTabs();
}

export function initPendientes() {
    console.log("[POS:pendientes] initPendientes");
    cargarDeStorage();
    renderTabs();

    document.getElementById("btn-pendiente")?.addEventListener("click", guardarComoPendiente);

    document.getElementById("pos-pendientes-tabs")?.addEventListener("click", (e) => {
        const btnX = e.target.closest(".pos-pendiente-tab-x");
        if (btnX) {
            e.stopPropagation();
            eliminarPendiente(Number(btnX.dataset.num));
            return;
        }
        const tab = e.target.closest(".pos-pendiente-tab");
        if (tab) restaurarPendiente(Number(tab.dataset.num));
    });
}
