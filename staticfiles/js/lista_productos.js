console.log("🔥 lista_productos.js CARGADO 🔥");

const buscador = document.getElementById("buscadorProductos");

if (!buscador) {
    console.warn("⚠️ No existe #buscadorProductos en esta vista.");
} else {

    buscador.addEventListener("input", function () {
        const texto = this.value.toLowerCase().trim();
        const cards = Array.from(document.querySelectorAll(".producto-card"));

        cards.forEach(card => {
            const nombre = card.dataset.nombre.toLowerCase();
            const descripcion = card.dataset.descripcion.toLowerCase();
            const categoria = card.dataset.categoria.toLowerCase();
            const temporada = card.dataset.temporada.toLowerCase();

            const coincide =
                nombre.includes(texto) ||
                descripcion.includes(texto) ||
                categoria.includes(texto) ||
                temporada.includes(texto);

            if (coincide) {
                // ⭐ Mostrar con animación suave
                card.classList.remove("oculto");
                setTimeout(() => {
                    card.style.display = "block";
                }, 10);
            } else {
                // ⭐ Ocultar con animación suave
                card.classList.add("oculto");
                setTimeout(() => {
                    if (!texto) return;
                    card.style.display = "none";
                }, 250); // coincide con la transición CSS
            }
        });

        // ⭐ Restaurar todo si el buscador está vacío
        if (!texto) {
            cards.forEach(card => {
                card.style.display = "block";
                card.classList.remove("oculto");
            });
        }
    });
}