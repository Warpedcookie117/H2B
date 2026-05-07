/* ============================================================
   RESUMEN DE UBICACIONES — siempre visible en cada card
   PANEL ¿QUÉ FALTA?           — AJAX, sin reload de página
   ============================================================ */

const _ubicMap = {};
const _currId  = window.ubicacionActualId || 0;
(window.todasUbicaciones || []).forEach(u => { _ubicMap[u.id] = u; });

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

window.refrescarResumenUbicaciones = function (productoId) {
    document.querySelectorAll(`#gridProductos [data-producto="${productoId}"]`)
        .forEach(renderResumenCard);
};

document.addEventListener("DOMContentLoaded", renderAllResumenes);


// ── PANEL FALTANTES ───────────────────────────────────────────

(function () {
    const btnFaltan = document.getElementById("btn-faltan-piso");
    if (!btnFaltan) return;

    const selectEl = document.getElementById("select-piso-cmp");
    const btnTodos = document.getElementById("btn-todos-piso");
    const countEl  = document.getElementById("cnt-faltan-piso");
    const grid     = document.getElementById("gridProductos");

    let activoPisoId   = window.pairedUbicacionId || null;
    let gridOriginalHTML = null; // guarda el grid completo para restaurar

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

    // ── AJAX: reemplazar grid sin recargar página ─────────────
    async function cargarGrid(extraParams = {}) {
        const url = new URL(window.location.href);
        url.searchParams.delete("page");
        Object.entries(extraParams).forEach(([k, v]) => {
            if (v === null) url.searchParams.delete(k);
            else            url.searchParams.set(k, v);
        });

        try {
            const res  = await fetch(url.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
            });
            const html    = await res.text();
            const doc     = new DOMParser().parseFromString(html, "text/html");
            const newGrid = doc.getElementById("gridProductos");
            if (newGrid && grid) {
                grid.innerHTML = newGrid.innerHTML;
                window.aplicarColoresCards?.();
                renderAllResumenes();
            }
        } catch (e) {
            console.error("[comparar_piso] Error cargando grid:", e);
        }
    }

    // ── Select (ubicación manual) ─────────────────────────────
    selectEl?.addEventListener("change", e => {
        activoPisoId = e.target.value ? parseInt(e.target.value) : null;
        recalcularConteo();
    });

    // ── Botón "¿Qué falta?" ───────────────────────────────────
    btnFaltan.addEventListener("click", async () => {
        if (!activoPisoId) return;

        // Guardar grid original solo la primera vez
        if (!gridOriginalHTML) gridOriginalHTML = grid.innerHTML;

        btnFaltan.disabled = true;
        btnFaltan.textContent = "Cargando...";

        await cargarGrid({ falta_en: activoPisoId });

        btnFaltan.disabled = false;
        btnFaltan.innerHTML = `¿Qué me falta? (<span id="cnt-faltan-piso">${countEl?.textContent || 0}</span>)`;
        btnTodos?.classList.remove("hidden");
    });

    // ── Botón "Mostrar todos" ─────────────────────────────────
    btnTodos?.addEventListener("click", () => {
        if (gridOriginalHTML && grid) {
            grid.innerHTML = gridOriginalHTML;
            gridOriginalHTML = null;
            window.aplicarColoresCards?.();
            renderAllResumenes();
        }
        btnTodos?.classList.add("hidden");
    });
})();
