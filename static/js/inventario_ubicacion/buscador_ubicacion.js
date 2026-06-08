// ============================
// BUSCADOR + ESCÁNER — inventario_ubicacion
// ============================

const buscador      = document.getElementById("buscadorProductos");
const sinResultados = document.getElementById("sinResultados");

if (!buscador) {
    console.warn("⚠️ No existe #buscadorProductos en inventario_ubicacion.");
} else {

    // Solo auto-enfocar en dispositivos con puntero (desktop). En móvil el foco
    // automático dispara el teclado virtual antes de que el usuario lo pida.
    if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
        buscador.focus();
    }

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

        // Incluir filtros de categoría activos
        const catVal    = document.getElementById("filtro-cat-padre")?.value || "";
        const subcatVal = document.getElementById("filtro-subcat")?.value    || "";
        if (catVal)    url.searchParams.set("cat",    catVal);
        else           url.searchParams.delete("cat");
        if (subcatVal) url.searchParams.set("subcat", subcatVal);
        else           url.searchParams.delete("subcat");

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
            // Actualizar paginación para que sus links conserven los filtros activos
            const nuevaPag = doc.getElementById("paginacion-ubicacion");
            const pagEl    = document.getElementById("paginacion-ubicacion");
            if (nuevaPag && pagEl) pagEl.innerHTML = nuevaPag.innerHTML;
        } catch (e) {
            if (e.name !== "AbortError") console.error("Error buscando productos:", e);
        }
    }

    // Exponer para que el IIFE de filtros pueda llamarla
    // (async function en bloque es block-scoped, no se eleva al scope global)
    window.fetchYActualizarGrid = fetchYActualizarGrid;

    // Cuando el usuario toca el campo de nuevo, resetear el flag de escaneo
    buscador.addEventListener("focus", () => {
        esperandoNuevoEscaneo = false;
    });

    // ============================
    // KEYDOWN — Enter dispara búsqueda inmediata (desktop / teclados físicos)
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
    // KEYUP — Enter como fallback (Android Chrome a veces no dispara keydown
    // con key:"Enter" desde teclado virtual o escáner Bluetooth)
    // ============================
    buscador.addEventListener("keyup", function (e) {
        if (e.key === "Enter" || e.keyCode === 13) {
            clearTimeout(debounceTimer);
            fetchYActualizarGrid(buscador.value.trim());
            esperandoNuevoEscaneo = true;
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

    // Fallback: si el campo pierde foco con texto (algunos scanners Bluetooth
    // en Android terminan con Tab/blur en vez de Enter)
    buscador.addEventListener("change", function () {
        clearTimeout(debounceTimer);
        fetchYActualizarGrid(this.value.trim());
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

// ============================
// FILTROS DE CATEGORÍA
// ============================
(function () {
    const filtroCategoria = document.getElementById("filtro-cat-padre");
    const filtroSubcat    = document.getElementById("filtro-subcat");
    const btnLimpiar      = document.getElementById("btn-limpiar-filtros");
    const buscadorInput   = document.getElementById("buscadorProductos");

    const categoriasEl = document.getElementById("categorias-json");
    if (!categoriasEl || !filtroCategoria || !filtroSubcat) return;

    const categoriasMap = JSON.parse(categoriasEl.textContent);

    function poblarCatPadre() {
        Object.keys(categoriasMap).forEach(cat => {
            const opt = document.createElement("option");
            opt.value = cat;
            opt.textContent = cat;
            filtroCategoria.appendChild(opt);
        });
    }

    function poblarSubcat(catPadre) {
        if (!catPadre) {
            filtroSubcat.innerHTML = '<option value="">— Elige categoría primero —</option>';
            filtroSubcat.disabled = true;
            filtroSubcat.style.opacity = "0.4";
            filtroSubcat.style.cursor  = "not-allowed";
            filtroSubcat.style.boxShadow = "2px 2px 0 0 black";
            return;
        }
        filtroSubcat.disabled = false;
        filtroSubcat.style.opacity = "1";
        filtroSubcat.style.cursor  = "pointer";
        filtroSubcat.style.boxShadow = "4px 4px 0 0 black";
        filtroSubcat.innerHTML = '<option value="">Todas las subcategorías</option>';
        const subcats = (categoriasMap[catPadre] || []).filter(Boolean);
        subcats.forEach(s => {
            const opt = document.createElement("option");
            opt.value = s;
            opt.textContent = s;
            filtroSubcat.appendChild(opt);
        });
    }

    function actualizarBtnLimpiar() {
        const activo = filtroCategoria.value || filtroSubcat.value;
        btnLimpiar?.classList.toggle("hidden", !activo);
    }

    function dispararFetch() {
        window.fetchYActualizarGrid?.(buscadorInput?.value?.trim() || "");
    }

    // Inicializar dropdowns
    poblarCatPadre();
    poblarSubcat("");

    // Pre-seleccionar si la URL ya trae ?cat= o ?subcat=
    const params = new URLSearchParams(window.location.search);
    const initCat    = params.get("cat")    || "";
    const initSubcat = params.get("subcat") || "";
    if (initCat)    { filtroCategoria.value = initCat; poblarSubcat(initCat); }
    if (initSubcat) { filtroSubcat.value = initSubcat; }
    actualizarBtnLimpiar();

    // Eventos
    filtroCategoria.addEventListener("change", () => {
        poblarSubcat(filtroCategoria.value);
        filtroSubcat.value = "";
        actualizarBtnLimpiar();
        dispararFetch();
    });

    filtroSubcat.addEventListener("change", () => {
        actualizarBtnLimpiar();
        dispararFetch();
    });

    btnLimpiar?.addEventListener("click", () => {
        filtroCategoria.value = "";
        poblarSubcat("");
        filtroSubcat.value = "";
        actualizarBtnLimpiar();
        dispararFetch();
    });
})();
