// ============================================================
// detalle_producto.js
// - Auto-oculta mensajes
// - Carga el código de barras como base64
// - Toggle del panel de costo
// - Cascade Categoría padre → Subcategoría
// - Re-renderiza inputs de atributos según la sub seleccionada
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // ── Mensajes ──────────────────────────────────────────
    const msgContainer = document.getElementById("msg-container");
    if (msgContainer) {
        setTimeout(() => { msgContainer.style.opacity = "0"; }, 3000);
        setTimeout(() => { msgContainer.remove(); }, 3500);
    }

    // ── Código de barras ──────────────────────────────────
    const img = document.getElementById("codigo-img");
    const codigoUrl = img?.dataset.url;
    if (img && codigoUrl) {
        fetch(codigoUrl)
            .then(res => res.json())
            .then(data => {
                if (data.imagen) img.src = `data:image/png;base64,${data.imagen}`;
            })
            .catch(err => console.error("Error cargando código:", err));
    }

    // ── Cascade categoría padre → sub + atributos dinámicos ──
    initCategoriaSubAtributos();
});


// ============================================================
// Toggle panel costo (se llama desde onclick="toggleCosto()")
// ============================================================
window.toggleCosto = function () {
    const panel = document.getElementById("panelCosto");
    const icon  = document.getElementById("iconCosto");
    if (!panel || !icon) return;
    const abierto = !panel.classList.contains("hidden");
    panel.classList.toggle("hidden");
    icon.textContent = abierto ? "▼" : "▲";
};


// ============================================================
// Cascade y atributos dinámicos (solo corre si puede_editar
// renderizó los selects en el template)
// ============================================================
function initCategoriaSubAtributos() {
    const selPadre  = document.getElementById("sel-categoria-padre");
    const selSub    = document.getElementById("sel-subcategoria");
    const container = document.getElementById("atributos-container");
    if (!selPadre || !selSub || !container) return;

    // valores actuales del producto (para conservar lo escrito si el usuario
    // regresa a la sub original sin haber guardado todavía)
    const valoresActuales = {};
    document.querySelectorAll("#atributos-actuales div").forEach(d => {
        valoresActuales[d.dataset.id] = d.dataset.valor || "";
    });

    // Snapshot del formulario al cargar la página (para "Restaurar valores originales").
    // Solo guardamos campos que existen al inicio — los inputs de atributos dinámicos
    // se reconstruyen vía renderAtributos() con valoresActuales.
    const padreOriginalId = selPadre.value;
    const subOriginalId   = selSub.value;
    const formEl = selPadre.closest("form");
    const snapshotInputs = new Map();
    if (formEl) {
        formEl.querySelectorAll("input[name], select[name], textarea[name]").forEach(el => {
            // Excluir los inputs de atributos (se restauran vía renderAtributos)
            if (el.name && el.name.startsWith("attr_")) return;
            snapshotInputs.set(el, el.value);
        });
    }

    // filtrar opciones del select de subs según la padre seleccionada
    function filtrarSubs() {
        const padreId = selPadre.value;
        let primeraVisible    = null;
        let haySeleccionVisible = false;

        Array.from(selSub.options).forEach(opt => {
            const visible = opt.dataset.padre === padreId;
            opt.hidden    = !visible;
            opt.disabled  = !visible;
            if (visible && primeraVisible === null) primeraVisible = opt;
            if (visible && opt.selected) haySeleccionVisible = true;
        });

        if (!haySeleccionVisible && primeraVisible) {
            primeraVisible.selected = true;
            renderAtributos(primeraVisible.value);
        }
    }

    // pintar inputs de atributos para la sub indicada
    function renderAtributos(subId) {
        while (container.firstChild) container.removeChild(container.firstChild);

        const atributos = Array.from(document.querySelectorAll("#atributos-data div"))
            .filter(d => String(d.dataset.categoria) === String(subId));

        if (atributos.length === 0) {
            const p = document.createElement("p");
            p.className = "border-4 border-dashed border-gray-300 p-6 text-center text-gray-400 font-bold text-sm";
            p.textContent = "Esta subcategoría no tiene atributos configurados.";
            container.appendChild(p);
            return;
        }

        atributos.forEach(a => {
            const wrap = document.createElement("div");
            wrap.className = "border-4 border-black shadow-[3px_3px_0_0_black] bg-[#F0FFF4] " +
                             "p-4 flex items-center justify-between gap-4 flex-wrap";

            const label = document.createElement("span");
            label.className = "font-black text-black uppercase tracking-wide text-sm";
            label.textContent = a.dataset.nombre;

            const input = document.createElement("input");
            input.type      = "text";
            input.name      = `attr_${a.dataset.nombre}`;
            input.className = "field-90s w-48";
            input.value     = valoresActuales[a.dataset.id] || "";
            input.setAttribute("autocomplete", "off");

            if ((a.dataset.tipo || "").toLowerCase() === "numero") {
                input.addEventListener("input", () => {
                    input.value = input.value.replace(/[^0-9.]/g, "");
                    if (input.value.startsWith(".")) input.value = "";
                });
            }

            wrap.appendChild(label);
            wrap.appendChild(input);
            container.appendChild(wrap);
        });
    }

    selPadre.addEventListener("change", filtrarSubs);
    selSub.addEventListener("change", () => renderAtributos(selSub.value));

    // Botón "Restaurar valores originales"
    const btnRestaurar = document.getElementById("btn-restaurar");
    if (btnRestaurar) {
        btnRestaurar.addEventListener("click", () => {
            // 1) Restaurar todos los campos del snapshot (nombre, descripción, precios, dueño…)
            snapshotInputs.forEach((val, el) => {
                if (el.isConnected) el.value = val;
            });
            // 2) Restaurar padre + sub a los originales y re-renderizar atributos
            selPadre.value = padreOriginalId;
            filtrarSubs();
            selSub.value = subOriginalId;
            renderAtributos(subOriginalId);

            // 3) Feedback visual breve
            btnRestaurar.textContent = "✓ Restaurado";
            setTimeout(() => {
                btnRestaurar.textContent = "↶ Restaurar valores originales";
            }, 1200);
        });
    }

    // estado inicial
    filtrarSubs();
}
