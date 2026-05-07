// ============================
// BUSCADOR + ESCÁNER — inventario_ubicacion
// ============================

const buscador      = document.getElementById("buscadorProductos");
const sinResultados = document.getElementById("sinResultados");

if (!buscador) {
    console.warn("⚠️ No existe #buscadorProductos en inventario_ubicacion.");
} else {

    buscador.focus();

    let esperandoNuevoEscaneo = false;
    let debounceTimer         = null;
    let fetchActivo           = null; // AbortController del fetch en curso

    // ============================
    // FETCH sin race condition ni parpadeo de colores
    // ============================
    async function fetchYActualizarGrid(q) {
        // Cancela el fetch anterior si todavía está corriendo
        if (fetchActivo) fetchActivo.abort();
        fetchActivo = new AbortController();

        const url = new URL(window.location.href);
        if (q) url.searchParams.set("q", q);
        else    url.searchParams.delete("q");
        url.searchParams.delete("page");

        const grid = document.getElementById("gridProductos");

        try {
            const res  = await fetch(url.toString(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal:  fetchActivo.signal,
            });
            const html       = await res.text();
            const doc        = new DOMParser().parseFromString(html, "text/html");
            const nuevoGrid  = doc.getElementById("gridProductos");
            if (nuevoGrid) {
                grid.innerHTML = nuevoGrid.innerHTML;
                if (typeof window.aplicarColoresCards === "function") {
                    window.aplicarColoresCards();
                }
                // Precargar todas las imágenes del resultado para paginación instantánea
                const imgs = grid.querySelectorAll("img");
                if (imgs.length) window.precargarImagenesEnIdle?.(Array.from(imgs));
            }
        } catch (e) {
            if (e.name !== "AbortError") console.error("Error buscando productos:", e);
        }
    }

    // ============================
    // KEYDOWN — Enter dispara búsqueda inmediata
    // ============================
    buscador.addEventListener("keydown", function (e) {

        if (e.key === "Enter") {
            e.preventDefault();
            clearTimeout(debounceTimer);
            fetchYActualizarGrid(buscador.value.trim());
            esperandoNuevoEscaneo = true;
            return;
        }

        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
        }
    });

    // ============================
    // TECLAS GLOBALES → foco al buscador
    // ============================
    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab","Escape","Enter",
             "ArrowUp","ArrowDown","ArrowLeft","ArrowRight",
             "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"
        ].includes(e.key)) return;

        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
    });

    // ============================
    // INPUT — debounce 350ms → fetch
    // ============================
    buscador.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        const texto = this.value.trim();
        debounceTimer = setTimeout(() => fetchYActualizarGrid(texto), 350);
    });

    // ============================
    // ESCÁNER DE CÁMARA → búsqueda inmediata
    // ============================
    if (typeof initEscanerCamara === "function") {
        initEscanerCamara((codigo) => {
            buscador.value = codigo;
            clearTimeout(debounceTimer);
            fetchYActualizarGrid(codigo);
        });
    }

}
