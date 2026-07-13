/* ============================================================
   RESUMEN DE UBICACIONES — siempre visible en cada card
   PANEL ¿QUÉ FALTA?           — AJAX, sin reload de página
   ============================================================ */

const _ubicMap = {};
const _currId  = window.ubicacionActualId || 0;
(window.todasUbicaciones || []).forEach(u => { _ubicMap[u.id] = u; });

// ── Precarga de imágenes en idle, en chunks ───────────────────
// Expuesta en window para que buscador_ubicacion.js también la use.
window.precargarImagenesEnIdle = function (imgs) {
    let i = 0;
    const CHUNK = 8;
    const cargarChunk = (deadline) => {
        while (i < imgs.length && (!deadline || deadline.timeRemaining() > 0)) {
            const tope = Math.min(i + CHUNK, imgs.length);
            for (; i < tope; i++) {
                const src = imgs[i].src || imgs[i].dataset?.src;
                if (!src) continue;
                const p = new Image();
                p.src = src;
            }
        }
        if (i < imgs.length) {
            if ("requestIdleCallback" in window) requestIdleCallback(cargarChunk, { timeout: 500 });
            else                                  setTimeout(() => cargarChunk(null), 50);
        }
    };
    if ("requestIdleCallback" in window) requestIdleCallback(cargarChunk, { timeout: 1000 });
    else                                  setTimeout(() => cargarChunk(null), 200);
};

document.addEventListener("DOMContentLoaded", () => {
    const imgs = document.querySelectorAll("#gridProductos img");
    if (imgs.length) window.precargarImagenesEnIdle(Array.from(imgs));
});

// ── RESUMEN SIEMPRE VISIBLE ───────────────────────────────────

function _cantOtraUbic(productoId, ubicId) {
    const r = (window.inventarioTodas || []).find(
        i => i.producto_id === productoId && i.ubicacion_id === ubicId
    );
    return r ? r.cantidad_actual : 0;
}

function renderResumenCard(card) {
    const pid = parseInt(card.dataset.producto);
    const relevantes = Object.values(_ubicMap).filter(u => u.id !== _currId);

    let section = card.querySelector(".loc-summary");
    if (relevantes.length === 0) { if (section) section.remove(); return; }

    if (!section) {
        section = document.createElement("div");
        section.className = "loc-summary";
        section.style.cssText = "border-top:2px solid black;padding:0.3rem 0 0;margin:0.3rem 0 0;";
        const cantSpan = card.querySelector(".cantidad-ubicacion");
        const cantBox  = cantSpan?.closest(".flex.items-center.justify-center");
        const priceBox = cantBox?.nextElementSibling;
        if (priceBox) card.insertBefore(section, priceBox);
        else           card.appendChild(section);
    }

    section.innerHTML = relevantes.map(u => {
        const qty   = _cantOtraUbic(pid, u.id);
        const falta = qty === 0;
        return `<div style="
            background:${falta ? "#FF006E" : "#06D6A0"};
            color:${falta ? "white" : "black"};
            border:2px solid black;font-weight:900;font-size:0.58rem;
            text-transform:uppercase;letter-spacing:0.05em;
            padding:0.18rem 0.45rem;margin-bottom:0.18rem;
            display:flex;justify-content:space-between;align-items:center;gap:0.4rem;">
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0">${u.nombre}</span>
          <span style="flex-shrink:0">${qty} pzas</span>
        </div>`;
    }).join("");
}

function renderAllResumenes() {
    document.querySelectorAll("#gridProductos .cardProducto").forEach(renderResumenCard);
}

// Expuesta para que el buscador re-pinte las badges tras reemplazar el grid.
window.renderAllResumenes = renderAllResumenes;

window.refrescarResumenUbicaciones = function (productoId) {
    document.querySelectorAll(`#gridProductos [data-producto="${productoId}"]`)
        .forEach(renderResumenCard);
};

document.addEventListener("DOMContentLoaded", renderAllResumenes);


// ── PANEL FALTANTES ───────────────────────────────────────────

(function () {
    const btnFaltan = document.getElementById("btn-faltan-piso");
    if (!btnFaltan) return;

    const selectEl     = document.getElementById("select-piso-cmp");
    const btnTodos     = document.getElementById("btn-todos-piso");
    const countEl      = document.getElementById("cnt-faltan-piso");
    const grid         = document.getElementById("gridProductos");
    const paginacionEl = document.getElementById("paginacion-ubicacion");

    const POR_PAGINA = 20;

    let activoPisoId        = window.pairedUbicacionId || null;
    let gridOriginalHTML    = null;
    let paginOriginalHTML   = null;
    let faltanteGroups      = [];  // [[card, modalAgregar, modalAjustar], ...]
    let faltantePage        = 1;

    // ── Conteo desde inventarioTodas ─────────────────────────
    function recalcularConteo() {
        if (!activoPisoId) {
            if (countEl) countEl.textContent = 0;
            btnFaltan.disabled = true;
            return;
        }
        const enActual = new Set(
            (window.inventarioTodas || [])
                .filter(i => i.ubicacion_id === _currId)
                .map(i => i.producto_id)
        );
        const enPaired = new Map(
            (window.inventarioTodas || [])
                .filter(i => i.ubicacion_id === activoPisoId)
                .map(i => [i.producto_id, i.cantidad_actual])
        );
        let n = 0;
        enActual.forEach(pid => { if ((enPaired.get(pid) || 0) === 0) n++; });
        if (countEl)   countEl.textContent = n;
        if (btnFaltan) btnFaltan.disabled   = false;
    }

    window.refrescarComparacionPiso = recalcularConteo;
    document.addEventListener("DOMContentLoaded", recalcularConteo);

    // ── Construir HTML de paginación client-side ──────────────
    function buildPaginHTML(page, numPages, total) {
        if (numPages <= 1) return "";
        const prev = page > 1
            ? `<button data-fp="prev"
                class="btn-90s border-4 border-black shadow-[4px_4px_0_0_black] bg-[#FF006E]
                       text-white font-black text-xs uppercase tracking-widest px-5 py-2">◀ Anterior</button>`
            : `<span class="border-4 border-black bg-gray-200 text-gray-400
                           font-black text-xs uppercase tracking-widest px-5 py-2 cursor-not-allowed">◀ Anterior</span>`;
        const next = page < numPages
            ? `<button data-fp="next"
                class="btn-90s border-4 border-black shadow-[4px_4px_0_0_black] bg-[#FF006E]
                       text-white font-black text-xs uppercase tracking-widest px-5 py-2">Siguiente ▶</button>`
            : `<span class="border-4 border-black bg-gray-200 text-gray-400
                           font-black text-xs uppercase tracking-widest px-5 py-2 cursor-not-allowed">Siguiente ▶</span>`;
        return `<div class="flex flex-wrap items-center justify-center gap-3 mt-8 pt-6 border-t-4 border-black">
            ${prev}
            <div class="border-4 border-black shadow-[4px_4px_0_0_black] bg-[#FFBE0B] px-5 py-2 text-center min-w-[120px]">
                <p class="font-black text-black text-sm uppercase tracking-widest leading-none">${page} / ${numPages}</p>
                <p class="font-semibold text-black/70 text-xs mt-0.5">${total} productos</p>
            </div>
            ${next}
        </div>`;
    }

    // ── Renderizar página de faltantes ────────────────────────
    function renderFaltantePage(page) {
        faltantePage = page;
        const total    = faltanteGroups.length;
        const numPages = Math.ceil(total / POR_PAGINA);
        const start    = (page - 1) * POR_PAGINA;
        const visible  = faltanteGroups.slice(start, start + POR_PAGINA);

        grid.innerHTML = "";
        visible.forEach(group => group.forEach(el => grid.appendChild(el)));
        window.aplicarColoresCards?.();
        renderAllResumenes();

        if (paginacionEl) {
            paginacionEl.innerHTML = buildPaginHTML(page, numPages, total);
            paginacionEl.querySelectorAll("[data-fp]").forEach(btn => {
                btn.addEventListener("click", () => {
                    if (btn.dataset.fp === "prev") renderFaltantePage(faltantePage - 1);
                    else                           renderFaltantePage(faltantePage + 1);
                });
            });
        }
    }

    // ── AJAX: traer todos los faltantes sin paginación ────────
    async function cargarFaltantes() {
        const url = new URL(window.location.href);
        url.searchParams.delete("page");
        url.searchParams.set("falta_en", activoPisoId);

        const res  = await fetch(url.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
        });
        const html    = await res.text();
        const doc     = new DOMParser().parseFromString(html, "text/html");
        const newGrid = doc.getElementById("gridProductos");
        if (!newGrid || !grid) return;

        // Guardar estado original solo la primera vez
        if (!gridOriginalHTML) {
            gridOriginalHTML  = grid.innerHTML;
            paginOriginalHTML = paginacionEl?.innerHTML ?? "";
        }

        // Agrupar card + sus modales hermanos (modal_agregar, modal_ajustar)
        // El template renderea: card, modalAgregar_X, modalAjustar_X, card, ...
        faltanteGroups = [];
        let current = null;
        for (const child of Array.from(newGrid.children)) {
            if (child.classList?.contains("cardProducto")) {
                if (current) faltanteGroups.push(current);
                current = [child];
            } else if (current) {
                current.push(child);
            }
        }
        if (current) faltanteGroups.push(current);

        // Precargar TODAS las imágenes de los faltantes (incluso las de páginas siguientes)
        const allImgs = [];
        faltanteGroups.forEach(g => g[0].querySelectorAll("img").forEach(img => allImgs.push(img)));
        window.precargarImagenesEnIdle?.(allImgs);

        renderFaltantePage(1);
    }

    // ── Select (ubicación manual) ─────────────────────────────
    selectEl?.addEventListener("change", e => {
        activoPisoId = e.target.value ? parseInt(e.target.value) : null;
        recalcularConteo();
    });

    // ── Botón "¿Qué falta?" ───────────────────────────────────
    btnFaltan.addEventListener("click", async () => {
        if (!activoPisoId) return;

        btnFaltan.disabled    = true;
        btnFaltan.textContent = "Cargando...";

        try {
            await cargarFaltantes();
        } finally {
            btnFaltan.disabled = false;
            btnFaltan.innerHTML = `¿Qué me falta? (<span id="cnt-faltan-piso">${countEl?.textContent || 0}</span>)`;
            btnTodos?.classList.remove("hidden");
        }
    });

    // ── Botón "Mostrar todos" ─────────────────────────────────
    btnTodos?.addEventListener("click", () => {
        if (gridOriginalHTML && grid) {
            grid.innerHTML = gridOriginalHTML;
            gridOriginalHTML = null;
        }
        if (paginacionEl && paginOriginalHTML !== null) {
            paginacionEl.innerHTML = paginOriginalHTML;
            paginOriginalHTML = null;
        }
        faltanteGroups = [];
        faltantePage   = 1;
        window.aplicarColoresCards?.();
        renderAllResumenes();
        btnTodos?.classList.add("hidden");
    });
})();


// ─────────────────────────────────────────────────────────────
// PAGINACIÓN AJAX (modo normal, sin reload)
// + prefetch de imágenes de páginas adyacentes en idle
// ─────────────────────────────────────────────────────────────
(function () {
    const grid         = document.getElementById("gridProductos");
    const paginacionEl = document.getElementById("paginacion-ubicacion");
    if (!grid || !paginacionEl) return;

    const prefetchedPages = new Set();

    async function navegarAPagina(href) {
        try {
            grid.style.opacity = "0.5";
            const res  = await fetch(href, { credentials: "same-origin" });
            const html = await res.text();
            const doc  = new DOMParser().parseFromString(html, "text/html");

            const newGrid  = doc.getElementById("gridProductos");
            const newPagin = doc.getElementById("paginacion-ubicacion");

            if (newGrid)  grid.innerHTML         = newGrid.innerHTML;
            if (newPagin) paginacionEl.innerHTML = newPagin.innerHTML;

            history.pushState({ ajaxPagin: true }, "", href);
            window.aplicarColoresCards?.();
            renderAllResumenes();

            // Precargar imágenes del grid actual + adyacentes
            const imgs = grid.querySelectorAll("img");
            window.precargarImagenesEnIdle?.(Array.from(imgs));
            prefetchAdyacentes();

            // Scroll al inicio del grid para que se vea la página nueva
            grid.scrollIntoView({ behavior: "smooth", block: "start" });
        } catch (e) {
            console.error("[paginacion AJAX]", e);
            window.location.href = href; // fallback
        } finally {
            grid.style.opacity = "";
        }
    }

    async function prefetchAdyacentes() {
        const url = new URL(window.location.href);
        const cur = parseInt(url.searchParams.get("page") || "1");
        const candidates = [cur + 1, cur - 1].filter(p => p >= 1);

        for (const page of candidates) {
            if (prefetchedPages.has(page)) continue;
            const u = new URL(window.location.href);
            u.searchParams.set("page", page);
            try {
                const res  = await fetch(u.toString(), { credentials: "same-origin" });
                if (!res.ok) continue;
                const html = await res.text();
                const doc  = new DOMParser().parseFromString(html, "text/html");
                const imgs = Array.from(doc.querySelectorAll("#gridProductos img"));
                window.precargarImagenesEnIdle?.(imgs);
                prefetchedPages.add(page);
            } catch (e) { /* silencioso */ }
        }
    }

    // Interceptar clicks en links de paginación
    paginacionEl.addEventListener("click", (e) => {
        const link = e.target.closest("a[href*='page=']");
        if (!link) return;
        e.preventDefault();
        navegarAPagina(link.href);
    });

    // Manejo del back/forward del navegador
    window.addEventListener("popstate", (e) => {
        if (e.state?.ajaxPagin) navegarAPagina(window.location.href);
    });

    // Al cargar la página, prefetch de páginas adyacentes en idle
    if ("requestIdleCallback" in window) {
        requestIdleCallback(prefetchAdyacentes, { timeout: 2000 });
    } else {
        setTimeout(prefetchAdyacentes, 500);
    }
})();
