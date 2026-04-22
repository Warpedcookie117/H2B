// paginacion.js — Paginación del grid de productos POS

const ITEMS_POR_PAGINA = 4; // 2 columnas × 2 filas

let paginaActual = 1;
let busquedaActiva = false;

// ============================================================
// INIT
// ============================================================

export function initPaginacion() {
    renderPagina(1);

    document.getElementById("pos-pag-prev")?.addEventListener("click", () => {
        if (paginaActual > 1) irAPagina(paginaActual - 1);
    });

    document.getElementById("pos-pag-next")?.addEventListener("click", () => {
        if (paginaActual < getTotalPaginas()) irAPagina(paginaActual + 1);
    });
}

// ============================================================
// PAGINACIÓN
// ============================================================

function getItems() {
    return Array.from(document.querySelectorAll(".producto-item"));
}

function getTotalPaginas() {
    return Math.max(1, Math.ceil(getItems().length / ITEMS_POR_PAGINA));
}

function irAPagina(n) {
    paginaActual = Math.max(1, Math.min(n, getTotalPaginas()));
    renderPagina(paginaActual);
}

function renderPagina(n) {
    if (busquedaActiva) return;

    const items = getItems();
    const inicio = (n - 1) * ITEMS_POR_PAGINA;
    const fin    = inicio + ITEMS_POR_PAGINA;

    items.forEach((item, i) => {
        item.style.display = (i >= inicio && i < fin) ? "flex" : "none";
    });

    actualizarUI();
}

function actualizarUI() {
    const total = getTotalPaginas();
    const info = document.getElementById("pos-pag-info");
    if (info) info.textContent = `${paginaActual} / ${total}`;

    const prev = document.getElementById("pos-pag-prev");
    const next = document.getElementById("pos-pag-next");
    if (prev) prev.disabled = paginaActual <= 1;
    if (next) next.disabled = paginaActual >= total;
}

// ============================================================
// INTEGRACIÓN CON BUSCADOR
// ============================================================

export function activarBusqueda() {
    busquedaActiva = true;
    document.getElementById("pos-paginacion")?.classList.add("pos-paginacion--hidden");
}

export function desactivarBusqueda() {
    busquedaActiva = false;
    paginaActual = 1;
    document.getElementById("pos-paginacion")?.classList.remove("pos-paginacion--hidden");
    renderPagina(paginaActual);
}
