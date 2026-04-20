console.log("🔥 lista_productos.js CARGADO 🔥");

const buscador = document.getElementById("buscadorProductos");

if (!buscador) {
    console.warn("⚠️ No existe #buscadorProductos en esta vista.");
} else {

    buscador.focus();

    // ============================
    // Detección de escáner
    // El escáner escribe muy rápido y termina con Enter.
    // Guardamos el timestamp de cada tecla para detectar velocidad de escáner.
    // ============================
    let esperandoNuevoEscaneo = false;

    buscador.addEventListener("keydown", function (e) {

        // ENTER → el escáner terminó de mandar el código
        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = buscador.value.trim();
            if (!codigo) return;

            // Filtrar con el código actual
            filtrarCards(codigo);

            // Marcar que el próximo carácter debe limpiar el campo
            esperandoNuevoEscaneo = true;
            return;
        }

        // Si viene un carácter nuevo después de Enter → limpiar primero
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
            filtrarCards("");
        }

    });

    // ============================
    // Interceptar teclas globales → redirigir al buscador
    // ============================
    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab", "Escape", "Enter", "ArrowUp", "ArrowDown",
             "ArrowLeft", "ArrowRight", "F1", "F2", "F3", "F4",
             "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"].includes(e.key)) return;

        // Limpiar y enfocar para nuevo escaneo
        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
    });

    // ============================
    // Filtrar mientras escribe (para búsqueda manual)
    // ============================
    buscador.addEventListener("input", function () {
        filtrarCards(this.value.toLowerCase().trim());
    });

    // ============================
    // ESCÁNER DE CÁMARA
    // ============================
    if (typeof initEscanerCamara === "function") {
        initEscanerCamara((codigo) => {
            buscador.value = codigo;
            filtrarCards(codigo);
        });
    }

    // ============================
    // Función de filtrado
    // ============================
    function filtrarCards(texto) {
        texto = texto.toLowerCase().trim();
        const cards = Array.from(document.querySelectorAll(".producto-card"));

        cards.forEach(card => {
            const nombre      = (card.dataset.nombre      || "").toLowerCase();
            const descripcion = (card.dataset.descripcion || "").toLowerCase();
            const categoria   = (card.dataset.categoria   || "").toLowerCase();
            const temporada   = (card.dataset.temporada   || "").toLowerCase();
            const codigo      = (card.dataset.codigo      || "").toLowerCase();

            const coincide =
                nombre.includes(texto) ||
                descripcion.includes(texto) ||
                categoria.includes(texto) ||
                temporada.includes(texto) ||
                codigo.includes(texto);

            if (coincide) {
                card.classList.remove("oculto");
                card.style.display = "";
            } else {
                card.classList.add("oculto");
                setTimeout(() => {
                    if (buscador.value.trim()) card.style.display = "none";
                }, 250);
            }
        });

        if (!texto) {
            cards.forEach(card => {
                card.style.display = "";
                card.classList.remove("oculto");
            });
        }
    }
}