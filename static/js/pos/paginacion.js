// paginacion.js — Paginación del grid de productos POS

console.log("[POS:paginacion] Módulo cargado");

const ITEMS_POR_PAGINA = 6; // 2 columnas × 3 filas

let paginaActual = 1;
let busquedaActiva = false;

// ============================================================
// INIT
// ============================================================

export function initPaginacion() {
    console.log("[POS:paginacion] initPaginacion");
    renderPagina(1);

    document.getElementById("pos-pag-prev")?.addEventListener("click", () => {
        console.log(`[POS:paginacion] click ANT → página ${paginaActual - 1}`);
        if (paginaActual > 1) irAPagina(paginaActual - 1);
    });

    document.getElementById("pos-pag-next")?.addEventListener("click", () => {
        console.log(`[POS:paginacion] click SIG → página ${paginaActual + 1}`);
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
    const anterior = paginaActual;
    paginaActual = Math.max(1, Math.min(n, getTotalPaginas()));
    console.log(`[POS:paginacion] irAPagina: ${anterior} → ${paginaActual} (total=${getTotalPaginas()})`);
    renderPagina(paginaActual);
}

function renderPagina(n) {
    if (busquedaActiva) {
        console.log("[POS:paginacion] renderPagina omitido — búsqueda activa");
        return;
    }

    const items = getItems();
    const inicio = (n - 1) * ITEMS_POR_PAGINA;
    const fin    = inicio + ITEMS_POR_PAGINA;

    items.forEach((item, i) => {
        const visible = (i >= inicio && i < fin);
        item.style.display = visible ? "flex" : "none";
        if (visible) cargarImagenCard(item);
    });

    console.log(`[POS:paginacion] renderPagina ${n}: mostrando items ${inicio}–${fin - 1} de ${items.length}`);
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
// LAZY LOAD DE IMÁGENES
// ============================================================

export function cargarImagenCard(card) {
    const img = card.querySelector("img[data-src]");
    if (!img) return;
    img.src = img.dataset.src;
    img.removeAttribute("data-src");
}

// ============================================================
// INTEGRACIÓN CON BUSCADOR
// ============================================================

export function activarBusqueda() {
    console.log("[POS:paginacion] activarBusqueda");
    busquedaActiva = true;
    document.getElementById("pos-paginacion")?.classList.add("pos-paginacion--hidden");
}

export function desactivarBusqueda() {
    console.log("[POS:paginacion] desactivarBusqueda — restaurando página 1");
    busquedaActiva = false;
    paginaActual = 1;
    document.getElementById("pos-paginacion")?.classList.remove("pos-paginacion--hidden");
    renderPagina(paginaActual);
}
