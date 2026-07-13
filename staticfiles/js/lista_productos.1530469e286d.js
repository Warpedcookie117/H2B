// ============================================================
// LISTA_PRODUCTOS — búsqueda server-side con debounce + AbortController
// ============================================================

const LIMITE_COLUMNA = 10;

// ============================================================
// LÍMITE POR COLUMNA — máx N cards visible, resto oculto
// (solo aplica en modo sin búsqueda — al buscar se muestran todos los
// matches del backend en su totalidad)
// ============================================================

function aplicarLimite() {
    document.querySelectorAll(".cards-grid").forEach(grid => {
        grid.parentElement.querySelector(".btn-ver-todos-col")?.remove();

        const cards = Array.from(grid.querySelectorAll(".producto-card"));

        cards.forEach((card, i) => {
            if (i >= LIMITE_COLUMNA) {
                card.dataset.limitada = "1";
                card.style.display = "none";
            } else {
                delete card.dataset.limitada;
                card.style.display = "";
            }
        });

        if (cards.length > LIMITE_COLUMNA) {
            const columna = grid.closest("[data-ubicacion-id]");
            const url     = columna?.dataset.verTodosUrl || "#";

            const btn = document.createElement("a");
            btn.href      = url;
            btn.className = "btn-ver-todos-col btn-90s block w-full border-4 border-black " +
                            "shadow-[4px_4px_0_0_black] bg-[#3A86FF] text-white font-black " +
                            "text-xs uppercase tracking-widest text-center py-2 mt-2";
            btn.textContent = `Ver todos (${cards.length}) →`;
            grid.parentElement.appendChild(btn);
        }
    });
}

// ============================================================
// COLORES de cards (igual que original)
// ============================================================

function colorearCards() {
    const colores = [
        "#FFF176", "#F48FB1", "#80DEEA", "#CE93D8",
        "#A5D6A7", "#FFCC80", "#EF9A9A", "#90CAF9"
    ];
    document.querySelectorAll(".cards-grid").forEach(grid => {
        grid.querySelectorAll(".card-producto").forEach((card, i) => {
            card.style.backgroundColor = colores[i % colores.length];
        });
    });
}

// ============================================================
// FETCH server-side con cancelación de requests anteriores
// ============================================================

let fetchActivo = null;

async function fetchYActualizar(q) {
    if (fetchActivo) fetchActivo.abort();
    fetchActivo = new AbortController();

    const url = new URL(window.location.href);
    if (q) url.searchParams.set("q", q);
    else    url.searchParams.delete("q");
    url.searchParams.delete("page");

    try {
        const res = await fetch(url.toString(), {
            headers: { "X-Requested-With": "XMLHttpRequest" },
            signal:  fetchActivo.signal,
        });
        const html = await res.text();
        const doc  = new DOMParser().parseFromString(html, "text/html");

        // Reemplazar el contenedor mobile Y el desktop (ambos existen siempre,
        // se muestran/ocultan por media query)
        const mobileNuevo  = doc.querySelector(".mobile-wrap");
        const desktopNuevo = doc.querySelector(".kanban-wrap");
        const mobileViejo  = document.querySelector(".mobile-wrap");
        const desktopViejo = document.querySelector(".kanban-wrap");

        if (mobileNuevo && mobileViejo)   mobileViejo.innerHTML  = mobileNuevo.innerHTML;
        if (desktopNuevo && desktopViejo) desktopViejo.innerHTML = desktopNuevo.innerHTML;

        colorearCards();
        if (!q) aplicarLimite();   // límite por columna solo sin búsqueda

        // Actualizar URL del browser sin recargar (para que copy-paste del link funcione)
        history.replaceState({}, "", url.toString());

    } catch (e) {
        if (e.name !== "AbortError") console.error("Error buscando productos:", e);
    }
}

// ============================================================
// BUSCADOR
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    aplicarLimite();
    colorearCards();

    const buscador = document.getElementById("buscadorProductos");
    if (!buscador) return;

    // Foco automático solo en desktop con puntero — en mobile abre teclado
    // virtual sin que el usuario lo haya pedido.
    if (window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
        buscador.focus();
    }

    let esperandoNuevoEscaneo = false;
    let debounceTimer         = null;

    // Enter dispara búsqueda inmediata (desktop / scanner físico)
    buscador.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            clearTimeout(debounceTimer);
            fetchYActualizar(buscador.value.trim());
            esperandoNuevoEscaneo = true;
            return;
        }
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
        }
    });

    // Keyup fallback para Enter en Android Chrome (scanners Bluetooth a veces
    // no disparan keydown con key:"Enter")
    buscador.addEventListener("keyup", (e) => {
        if (e.key === "Enter" || e.keyCode === 13) {
            clearTimeout(debounceTimer);
            fetchYActualizar(buscador.value.trim());
            esperandoNuevoEscaneo = true;
        }
    });

    // Input con debounce 350ms para escritura humana
    buscador.addEventListener("input", () => {
        clearTimeout(debounceTimer);
        const texto = buscador.value.trim();
        debounceTimer = setTimeout(() => fetchYActualizar(texto), 350);
    });

    // Fallback: blur con texto (algunos scanners Bluetooth en Android
    // terminan con Tab/blur en vez de Enter)
    buscador.addEventListener("change", () => {
        clearTimeout(debounceTimer);
        fetchYActualizar(buscador.value.trim());
    });

    // Teclas globales → foco al buscador
    document.addEventListener("keydown", (e) => {
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

    // Escáner de cámara → búsqueda inmediata
    if (typeof initEscanerCamara === "function") {
        initEscanerCamara((codigo) => {
            buscador.value = codigo;
            clearTimeout(debounceTimer);
            fetchYActualizar(codigo);
        });
    }
});
