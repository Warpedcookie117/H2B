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

    // ============================
    // KEYDOWN — detección de escáner
    // ============================
    buscador.addEventListener("keydown", function (e) {

        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = buscador.value.trim();
            if (!codigo) return;
            filtrarCards(codigo);
            esperandoNuevoEscaneo = true;
            return;
        }

        // Primer carácter después de Enter → limpiar para nuevo escaneo
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
            // Asignar value programáticamente no dispara "input" → restaurar manualmente
            filtrarCards("");
        }
    });

    // ============================
    // TECLAS GLOBALES → foco al buscador
    // ============================
    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab", "Escape", "Enter",
             "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
             "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"
        ].includes(e.key)) return;

        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
        // Asignar value programáticamente no dispara "input" → restaurar manualmente
        filtrarCards("");
    });

    // ============================
    // INPUT — búsqueda manual mientras escribe
    // ============================
    buscador.addEventListener("input", function () {
        filtrarCards(this.value.toLowerCase().trim());
    });

    // ============================
    // FILTRAR CARDS + ANUNCIO
    // ============================
    function filtrarCards(texto) {
        texto = texto.toLowerCase().trim();
        const cards = Array.from(document.querySelectorAll("#gridProductos .producto-card"));

        // Sin texto → restaurar todo y ocultar anuncio
        if (!texto) {
            cards.forEach(card => {
                card.style.display   = "";
                card.style.opacity   = "1";
                card.style.transform = "scale(1)";
            });
            if (sinResultados) sinResultados.classList.add("hidden");
            return;
        }

        // Dividir en palabras — cada palabra debe aparecer en algún campo (AND)
        const palabras = texto.split(/\s+/).filter(Boolean);
        let hayCoincidencias = false;

        cards.forEach(card => {
            const campos = [
                card.dataset.producto     || "",   // ID del producto
                card.dataset.nombre       || "",
                card.dataset.descripcion  || "",
                card.dataset.categoria    || "",
                card.dataset.subcategoria || "",
                card.dataset.codigo       || "",
            ].map(c => c.toLowerCase());

            // Toda palabra del buscador debe existir en al menos un campo
            const coincide = palabras.every(p => campos.some(c => c.includes(p)));

            if (coincide) {
                card.style.display   = "";
                card.style.opacity   = "1";
                card.style.transform = "scale(1)";
                hayCoincidencias = true;
            } else {
                card.style.opacity   = "0";
                card.style.transform = "scale(0.95)";
                // Ocultar del flujo solo si todavía hay texto (evita que el timer
                // tape cards recién restauradas si el usuario borró muy rápido)
                setTimeout(() => {
                    if (buscador.value.trim()) card.style.display = "none";
                }, 150);
            }
        });

        if (sinResultados) {
            sinResultados.classList.toggle("hidden", hayCoincidencias);
        }
    }

}