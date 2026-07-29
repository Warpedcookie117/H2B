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

        // Incluir filtros de atributo (listas paralelas an/av) — panel por subcat
        url.searchParams.delete("an");
        url.searchParams.delete("av");
        document.querySelectorAll("#atributos-rows select[data-attr]").forEach(sel => {
            if (sel.value) {
                url.searchParams.append("an", sel.dataset.attr);
                url.searchParams.append("av", sel.value);
            }
        });

        // Filtro global por atributo (gan/gav) — toda la ubicación
        url.searchParams.delete("gan");
        url.searchParams.delete("gav");
        const gNom = document.getElementById("ub-global-attr-nombre");
        const gVal = document.getElementById("ub-global-attr-valor");
        if (gNom && gVal && gNom.value && gVal.value) {
            url.searchParams.append("gan", gNom.value);
            url.searchParams.append("gav", gVal.value);
        }

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
                // Re-pintar las badges de resumen (piso/bodega) en las cards nuevas.
                // El grid viene del server sin ellas; se inyectan client-side.
                window.renderAllResumenes?.();
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
    // QUITAR TECLADO al tocar zona vacía (móvil)
    // En iPhone el teclado tapa media pantalla y no había dónde picarle
    // sin activar un botón por accidente. Ahora tocar cualquier lugar que
    // NO sea un control (fondo, grid, zona libre de los botones) le quita
    // el foco al buscador y el teclado se baja.
    // ============================
    document.addEventListener("touchend", function (e) {
        if (document.activeElement !== buscador) return;
        if (e.target.closest("input, textarea, select, button, a")) return;
        buscador.blur();
    }, { passive: true });

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

    // ── Filtro por atributos ────────────────────────────────────
    const panelAtributos = document.getElementById("panel-atributos");
    const atributosRows   = document.getElementById("atributos-rows");
    const atributosPorSub = JSON.parse(
        document.getElementById("atributos-subcat-json")?.textContent || "{}"
    );
    // Pares [nombre, valor] preseleccionados (al recargar o paginar con filtros)
    const attrParesInit = JSON.parse(
        document.getElementById("attr-pares-json")?.textContent || "[]"
    );

    function renderPanelAtributos(subcatNombre, preseleccion = []) {
        if (!panelAtributos || !atributosRows) return;
        const atributos = atributosPorSub[subcatNombre] || [];
        atributosRows.innerHTML = "";

        if (!subcatNombre || !atributos.length) {
            panelAtributos.classList.add("hidden");
            return;
        }
        panelAtributos.classList.remove("hidden");

        const preMap = {};
        preseleccion.forEach(([n, v]) => { preMap[n] = v; });

        atributos.forEach(a => {
            const wrap = document.createElement("div");
            wrap.className = "w-full";

            // Etiqueta arriba con el nombre del atributo — grande y legible.
            // El dropdown de abajo muestra SOLO el valor, sin cortarse.
            const label = document.createElement("label");
            label.className = "block text-sm font-black uppercase tracking-widest text-black mb-1";
            label.textContent = a.nombre;

            const selWrap = document.createElement("div");
            selWrap.className = "relative";

            const sel = document.createElement("select");
            sel.dataset.attr = a.nombre;
            // font-size:16px evita el zoom automático de iOS y se lee bien.
            sel.style.cssText = "appearance:none;-webkit-appearance:none;background:#fff;font-size:16px;";
            sel.className = "w-full border-4 border-black px-3 py-3 pr-10 font-bold " +
                            "text-black outline-none cursor-pointer";

            const opt0 = document.createElement("option");
            opt0.value = "";
            opt0.textContent = "Cualquiera";
            sel.appendChild(opt0);

            (a.valores || []).forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = v;
                if (preMap[a.nombre] === v) opt.selected = true;
                sel.appendChild(opt);
            });

            sel.addEventListener("change", () => dispararFetch());

            const flecha = document.createElement("span");
            flecha.className = "pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-sm font-black select-none";
            flecha.textContent = "▼";

            selWrap.appendChild(sel);
            selWrap.appendChild(flecha);
            wrap.appendChild(label);
            wrap.appendChild(selWrap);
            atributosRows.appendChild(wrap);
        });
    }

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
    // Panel de atributos: si venía subcategoría, redibuja con lo preseleccionado
    renderPanelAtributos(initSubcat, initSubcat ? attrParesInit : []);
    actualizarBtnLimpiar();

    // Eventos
    filtroCategoria.addEventListener("change", () => {
        poblarSubcat(filtroCategoria.value);
        filtroSubcat.value = "";
        renderPanelAtributos("");   // sin subcategoría, no hay atributos
        actualizarBtnLimpiar();
        dispararFetch();
    });

    filtroSubcat.addEventListener("change", () => {
        renderPanelAtributos(filtroSubcat.value);   // atributos frescos, sin preselección
        actualizarBtnLimpiar();
        dispararFetch();
    });

    btnLimpiar?.addEventListener("click", () => {
        filtroCategoria.value = "";
        poblarSubcat("");
        filtroSubcat.value = "";
        renderPanelAtributos("");
        limpiarGlobal();   // el "Limpiar" también quita el filtro global
        actualizarBtnLimpiar();
        dispararFetch();
    });

    // ============================================================
    // FILTRO GLOBAL POR ATRIBUTO — toda la ubicación, sin subcategoría.
    // Se arma del mapa atributosPorSub (ya scoped a esta ubicación): junta
    // los atributos de todas las subcategorías y sus valores. Sin backend nuevo.
    // ============================================================
    const gBuscar     = document.getElementById("ub-global-attr-buscar");
    const gNombreHid  = document.getElementById("ub-global-attr-nombre");
    const gResultados = document.getElementById("ub-global-attr-resultados");
    const gValorSel   = document.getElementById("ub-global-attr-valor");
    const gPanel      = document.getElementById("panel-global-atributos");

    // Índice: nombre → { subcats: cuántas subcats lo tienen, valores: Set }
    const globalIndex = {};
    Object.values(atributosPorSub).forEach(atributos => {
        (atributos || []).forEach(a => {
            if (!globalIndex[a.nombre]) globalIndex[a.nombre] = { subcats: 0, valores: new Set() };
            globalIndex[a.nombre].subcats += 1;
            (a.valores || []).forEach(v => globalIndex[a.nombre].valores.add(v));
        });
    });
    // Ordenados por en cuántas subcats aparecen (los más "globales" primero)
    const globalNombres = Object.keys(globalIndex).sort((x, y) =>
        globalIndex[y].subcats - globalIndex[x].subcats || x.localeCompare(y)
    );

    // Si esta ubicación no tiene atributos, no tiene caso mostrar el filtro
    if (!globalNombres.length) gPanel?.classList.add("hidden");

    function _normalizarUb(t) {
        return (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    }

    function renderGlobalResultados(filtro) {
        if (!gResultados) return;
        const f = _normalizarUb((filtro || "").trim());
        const lista = f
            ? globalNombres.filter(n => _normalizarUb(n).includes(f)).slice(0, 12)
            : globalNombres.slice(0, 5);

        gResultados.innerHTML = "";
        if (!lista.length) {
            gResultados.innerHTML = '<p class="px-3 py-2 text-xs font-semibold text-gray-500">Sin coincidencias</p>';
            gResultados.classList.remove("hidden");
            return;
        }
        if (!f) {
            const h = document.createElement("p");
            h.className = "px-3 py-1.5 text-[10px] font-black uppercase tracking-widest text-gray-400 bg-gray-50";
            h.textContent = "Los más usados entre subcategorías";
            gResultados.appendChild(h);
        }
        lista.forEach(n => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "w-full text-left px-3 py-2 font-bold text-sm text-black hover:bg-black hover:text-white border-b-2 border-gray-100 last:border-0 transition-colors";
            b.textContent = n;
            b.addEventListener("click", () => seleccionarGlobal(n));
            gResultados.appendChild(b);
        });
        gResultados.classList.remove("hidden");
    }

    function poblarGlobalValores(nombre, preValor = "") {
        if (!gValorSel) return;
        if (!nombre || !globalIndex[nombre]) {
            gValorSel.innerHTML = '<option value="">— Elige atributo primero —</option>';
            gValorSel.disabled = true;
            return;
        }
        const valores = Array.from(globalIndex[nombre].valores).sort((a, b) => a.localeCompare(b));
        let html = '<option value="">Cualquiera</option>';
        valores.forEach(v => {
            const sel = (v === preValor) ? " selected" : "";
            html += `<option value="${v}"${sel}>${v}</option>`;
        });
        gValorSel.innerHTML = html;
        gValorSel.disabled = false;
    }

    function seleccionarGlobal(nombre) {
        gBuscar.value = nombre;
        gNombreHid.value = nombre;
        gResultados.classList.add("hidden");
        poblarGlobalValores(nombre);
        dispararFetch();
    }

    function limpiarGlobal() {
        if (gBuscar)    gBuscar.value = "";
        if (gNombreHid) gNombreHid.value = "";
        poblarGlobalValores("");
    }

    gBuscar?.addEventListener("focus", () => renderGlobalResultados(gBuscar.value));
    gBuscar?.addEventListener("input", () => {
        renderGlobalResultados(gBuscar.value);
        // Vaciar el campo quita el filtro global
        if (!gBuscar.value.trim() && gNombreHid.value) {
            gNombreHid.value = "";
            poblarGlobalValores("");
            dispararFetch();
        }
    });
    gValorSel?.addEventListener("change", () => dispararFetch());
    document.addEventListener("click", (e) => {
        if (!e.target.closest("#ub-global-attr-buscar") && !e.target.closest("#ub-global-attr-resultados")) {
            gResultados?.classList.add("hidden");
        }
    });

    // Restaurar el filtro global si venía en la URL (recarga / paginación)
    let globalParesInit = [];
    try {
        globalParesInit = JSON.parse(document.getElementById("attr-global-pares-json")?.textContent || "[]");
    } catch (e) { globalParesInit = []; }
    if (globalParesInit.length && gBuscar && gNombreHid) {
        const [gn, gv] = globalParesInit[0];
        gBuscar.value = gn;
        gNombreHid.value = gn;
        poblarGlobalValores(gn, gv);
    }
})();
