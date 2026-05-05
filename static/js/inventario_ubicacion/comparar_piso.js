/* ============================================================
   RESUMEN DE UBICACIONES — siempre visible en cada card
   PANEL ¿QUÉ FALTA EN PISO?    — filtro por selección
   ============================================================ */

// ── Mapa rápido id → {nombre, tipo} ──────────────────────────
const _ubicMap  = {};
const _currId   = window.ubicacionActualId || 0;
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

    // Pisos → siempre mostrar (aunque sean 0)
    // Otros → solo si tienen stock
    const relevantes = Object.values(_ubicMap).filter(u => {
        if (u.id === _currId) return false;
        const qty = _cantOtraUbic(pid, u.id);
        return true;
    });

    let section = card.querySelector(".loc-summary");

    if (relevantes.length === 0) {
        if (section) section.remove();
        return;
    }

    if (!section) {
        section = document.createElement("div");
        section.className = "loc-summary";
        section.style.cssText = "border-top:2px solid black;padding:0.3rem 0 0;margin:0.3rem 0 0;";
        // Inserta justo antes del bloque de precios (después del contador de piezas)
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
            border:2px solid black;
            font-weight:900;
            font-size:0.58rem;
            text-transform:uppercase;
            letter-spacing:0.05em;
            padding:0.18rem 0.45rem;
            margin-bottom:0.18rem;
            display:flex;
            justify-content:space-between;
            align-items:center;
            gap:0.4rem;
        ">
          <span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0">${u.nombre}</span>
          <span style="flex-shrink:0">${qty} pzas</span>
        </div>`;
    }).join("");
}

function renderAllResumenes() {
    document.querySelectorAll("#gridProductos .cardProducto").forEach(renderResumenCard);
}

// Hook que llama actualizarCard tras cada operación
window.refrescarResumenUbicaciones = function (productoId) {
    // El producto puede estar en el grid actual (como origen) o en otro
    // En ambos casos, cualquier card del grid con ese producto_id debe actualizarse
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

    // Auto-paired (bodega↔piso misma sucursal) or null (global, usa select)
    let activoPisoId  = window.pairedUbicacionId || null;
    let soloFaltantes = false;

    function recalcularPanel() {
        const cards = document.querySelectorAll("#gridProductos .cardProducto");
        let faltantes = 0;

        cards.forEach(card => {
            if (activoPisoId) {
                const qty = _cantOtraUbic(parseInt(card.dataset.producto), activoPisoId);
                if (qty === 0) faltantes++;
                card.style.display = soloFaltantes && qty !== 0 ? "none" : "";
            } else {
                card.style.display = "";
            }
        });

        if (countEl)   countEl.textContent = faltantes;
        if (btnFaltan) btnFaltan.disabled   = !activoPisoId;
    }

    window.refrescarComparacionPiso = recalcularPanel;

    // Auto-run once DOM is ready (if paired, shows count immediately)
    document.addEventListener("DOMContentLoaded", recalcularPanel);

    selectEl?.addEventListener("change", e => {
        activoPisoId  = e.target.value ? parseInt(e.target.value) : null;
        soloFaltantes = false;
        btnTodos?.classList.add("hidden");
        recalcularPanel();
    });

    btnFaltan.addEventListener("click", () => {
        if (!activoPisoId) return;
        soloFaltantes = true;
        btnTodos?.classList.remove("hidden");
        recalcularPanel();
    });

    btnTodos?.addEventListener("click", () => {
        soloFaltantes = false;
        btnTodos?.classList.add("hidden");
        recalcularPanel();
    });
})();
