// paginacion.js — Paginación + filtro de búsqueda con animación

console.log("[POS:paginacion] Módulo cargado");

const ITEMS_POR_PAGINA = 6;

let paginaActual = 1;
let filteredItems = null; // null = todos, array = resultados de búsqueda ordenados

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

    // Precargar todas las imágenes en segundo plano para paginación instantánea
    precargarRestantes();
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
    const allItems    = getAllItems();
    const activeItems = getActiveItems();
    const inicio = (n - 1) * ITEMS_POR_PAGINA;
    const fin    = inicio + ITEMS_POR_PAGINA;

    // Ocultar todos
    allItems.forEach(item => { item.style.display = "none"; });

    // Mostrar página actual con lazy-load y animación escalonada
    activeItems.slice(inicio, fin).forEach((item, i) => {
        item.style.display = "flex";
        cargarImagenCard(item);
        animarCard(item, i * 40);
    });

    console.log(`[POS:paginacion] renderPagina ${n}: ${inicio}–${Math.min(fin, activeItems.length) - 1} de ${activeItems.length}`);
    actualizarUI();
}

// ============================================================
// ANIMACIÓN
// ============================================================

function animarCard(card, delayMs = 0) {
    card.style.animationDelay = delayMs + "ms";
    card.classList.remove("pos-card-anim");
    void card.offsetWidth; // reflow para reiniciar la animación
    card.classList.add("pos-card-anim");
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

// Precarga todas las imágenes restantes en idle, en chunks para no saturar la red
function precargarRestantes() {
    const items = getAllItems();
    let i = 0;
    const CHUNK = 8;

    const cargarChunk = (deadline) => {
        while (i < items.length && (!deadline || deadline.timeRemaining() > 0)) {
            const tope = Math.min(i + CHUNK, items.length);
            for (; i < tope; i++) cargarImagenCard(items[i]);
        }
        if (i < items.length) {
            if ("requestIdleCallback" in window) {
                requestIdleCallback(cargarChunk, { timeout: 500 });
            } else {
                setTimeout(() => cargarChunk(null), 50);
            }
        }
    };

    if ("requestIdleCallback" in window) {
        requestIdleCallback(cargarChunk, { timeout: 1000 });
    } else {
        setTimeout(() => cargarChunk(null), 200);
    }
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

// Alias de compatibilidad — no hacen nada, la paginación ahora funciona en ambos modos
export const activarBusqueda  = () => {};
export const desactivarBusqueda = clearFiltro;
