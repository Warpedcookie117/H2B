// paginacion.js — Paginación + filtro de búsqueda con animación

console.log("[POS:paginacion] Módulo cargado");

const ITEMS_POR_PAGINA = 6;

let paginaActual = 1;
let filteredItems = null;   // null = todos, array = resultados de búsqueda ordenados
let itemsVisibles = [];     // las cards mostradas ahora — para ocultar solo esas
                            // (las demás arrancan ocultas por CSS)

// ============================================================
// INIT
// ============================================================

export function initPaginacion() {
    console.log("[POS:paginacion] initPaginacion");
    renderPagina(1);

    document.getElementById("pos-pag-prev")?.addEventListener("click", () => {
        if (paginaActual > 1) irAPagina(paginaActual - 1);
    });

    document.getElementById("pos-pag-next")?.addEventListener("click", () => {
        if (paginaActual < getTotalPaginas()) irAPagina(paginaActual + 1);
    });

    // NO se precargan las ~3300 imágenes: en una compu lenta eran 3300
    // descargas + decode presionando memoria y red. Cada página carga sus 6
    // imágenes bajo demanda (cargarImagenCard en renderPagina), que es lo justo.
}

// ============================================================
// ITEMS
// ============================================================

function getAllItems() {
    return Array.from(document.querySelectorAll(".producto-item"));
}

function getActiveItems() {
    return filteredItems !== null ? filteredItems : getAllItems();
}

function getTotalPaginas() {
    return Math.max(1, Math.ceil(getActiveItems().length / ITEMS_POR_PAGINA));
}

function irAPagina(n) {
    paginaActual = Math.max(1, Math.min(n, getTotalPaginas()));
    console.log(`[POS:paginacion] irAPagina → ${paginaActual}`);
    renderPagina(paginaActual);
}

// ============================================================
// RENDER
// ============================================================

function renderPagina(n) {
    window.__posPerf?.marca(`renderPagina p${n}`);
    const _t0 = performance.now();
    const activeItems = getActiveItems();
    const inicio = (n - 1) * ITEMS_POR_PAGINA;
    const fin    = inicio + ITEMS_POR_PAGINA;

    // Las cards arrancan OCULTAS por CSS (#lista-productos .producto-item{
    // display:none}). Así NUNCA recorremos las ~3300: solo ocultamos las 6
    // que estaban visibles y mostramos las 6 nuevas. Sin animación de card —
    // el toggle de clases sobre este DOM enorme disparaba el observador de
    // Tailwind-CDN y generaba un diluvio de requestAnimationFrame.
    itemsVisibles.forEach(item => { item.style.display = "none"; });

    const nuevos = activeItems.slice(inicio, fin);
    nuevos.forEach(item => {
        item.style.display = "flex";
        cargarImagenCard(item);
    });
    itemsVisibles = nuevos;

    const _dt = performance.now() - _t0;
    if (_dt > 40) console.warn(`[POS:perf] ⏱️ renderPagina p${n} tardó ${_dt.toFixed(0)}ms (${activeItems.length} items activos)`);
    console.log(`[POS:paginacion] renderPagina ${n}: ${inicio}–${Math.min(fin, activeItems.length) - 1} de ${activeItems.length}`);
    actualizarUI();
}

// ============================================================
// UI DE PAGINACIÓN
// ============================================================

function actualizarUI() {
    const total = getTotalPaginas();

    const info = document.getElementById("pos-pag-info");
    if (info) info.textContent = `${paginaActual} / ${total}`;

    const prev = document.getElementById("pos-pag-prev");
    const next = document.getElementById("pos-pag-next");
    if (prev) prev.disabled = paginaActual <= 1;
    if (next) next.disabled = paginaActual >= total;

    // Siempre visible — también pagina resultados de búsqueda
    const paginacion = document.getElementById("pos-paginacion");
    if (paginacion) paginacion.classList.toggle("pos-paginacion--hidden", total <= 1);
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
// API DE FILTRO (usada por buscador_productos.js)
// ============================================================

export function setFiltro(items) {
    filteredItems = items;
    paginaActual  = 1;
    renderPagina(1);
}

export function clearFiltro() {
    filteredItems = null;
    paginaActual  = 1;
    renderPagina(1);
}

// ============================================================
// REFRESCO EN VIVO (usado por stock.js al insertar/quitar cards via WS)
// ============================================================

export function refrescarGrid() {
    // Si hay una búsqueda activa, descartar del filtro las cards que ya
    // no estén en el DOM (p. ej. una que se agotó mientras se buscaba).
    if (filteredItems !== null) {
        filteredItems = filteredItems.filter(el => el.isConnected);
    }
    // Reajustar la página actual por si se redujo el total de páginas.
    paginaActual = Math.min(paginaActual, getTotalPaginas());
    console.log("[POS:paginacion] refrescarGrid → re-render");
    renderPagina(paginaActual);
}

// Alias de compatibilidad — no hacen nada, la paginación ahora funciona en ambos modos
export const activarBusqueda  = () => {};
export const desactivarBusqueda = clearFiltro;
