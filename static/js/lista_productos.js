const LIMITE_COLUMNA = 10;

// ============================================================
// LÍMITE POR COLUMNA — máx N cards visible, resto oculto
// ============================================================

function aplicarLimite() {
    document.querySelectorAll(".cards-grid").forEach(grid => {
        // Limpiar botón previo
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

function quitarLimite() {
    document.querySelectorAll("[data-limitada='1']").forEach(card => {
        delete card.dataset.limitada;
        card.style.display = "";
    });
    document.querySelectorAll(".btn-ver-todos-col").forEach(b => b.remove());
}

// ============================================================
// FILTRADO DE BÚSQUEDA
// ============================================================

function filtrarCards(texto) {
    texto = texto.toLowerCase().trim();

    const cards = Array.from(document.querySelectorAll(".producto-card"));

    if (texto) {
        // Con búsqueda: quitar límite → mostrar solo coincidencias
        quitarLimite();

        cards.forEach(card => {
            const coincide =
                (card.dataset.nombre      || "").includes(texto) ||
                (card.dataset.descripcion || "").includes(texto) ||
                (card.dataset.categoria   || "").includes(texto) ||
                (card.dataset.temporada   || "").includes(texto) ||
                (card.dataset.codigo      || "").includes(texto);

            card.style.display = coincide ? "" : "none";
        });
    } else {
        // Sin búsqueda: mostrar todo y reaplicar límite por columna
        cards.forEach(card => { card.style.display = ""; });
        aplicarLimite();
    }
}

// ============================================================
// BUSCADOR
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // Aplicar límite inicial
    aplicarLimite();

    // Colorear cards (lógica original)
    const colores = [
        "#FFF176", "#F48FB1", "#80DEEA", "#CE93D8",
        "#A5D6A7", "#FFCC80", "#EF9A9A", "#90CAF9"
    ];
    document.querySelectorAll(".cards-grid").forEach(grid => {
        grid.querySelectorAll(".card-producto").forEach((card, i) => {
            card.style.backgroundColor = colores[i % colores.length];
        });
    });

    const buscador = document.getElementById("buscadorProductos");
    if (!buscador) return;

    buscador.focus();

    let esperandoNuevoEscaneo = false;

    buscador.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = buscador.value.trim();
            if (!codigo) return;
            filtrarCards(codigo);
            esperandoNuevoEscaneo = true;
            return;
        }
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
            filtrarCards("");
        }
    });

    buscador.addEventListener("input", function () {
        filtrarCards(this.value.toLowerCase().trim());
    });

    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab","Escape","Enter","ArrowUp","ArrowDown","ArrowLeft","ArrowRight",
             "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"].includes(e.key)) return;
        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
    });

    if (typeof initEscanerCamara === "function") {
        initEscanerCamara((codigo) => {
            buscador.value = codigo;
            filtrarCards(codigo);
        });
    }
});
