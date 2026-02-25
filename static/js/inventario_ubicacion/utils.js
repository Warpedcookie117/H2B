/* ============================================================
   SISTEMA CENTRALIZADO DE MODALES
   ============================================================ */

function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) {
        console.error("❌ Modal o contenido no encontrado:", modalId);
        return;
    }

    modal.classList.remove("hidden");

    requestAnimationFrame(() => {
        content.classList.remove("opacity-0", "scale-95");
        content.classList.add("opacity-100", "scale-100");
    });

    document.addEventListener("keydown", cerrarConEsc);
    modal.addEventListener("click", cerrarClickFuera);
}

function cerrarModal(modalId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) return;

    content.classList.remove("opacity-100", "scale-100");
    content.classList.add("opacity-0", "scale-95");

    setTimeout(() => {
        modal.classList.add("hidden");
    }, 150);

    document.removeEventListener("keydown", cerrarConEsc);
    modal.removeEventListener("click", cerrarClickFuera);
}


/* ============================================================
   EVENTOS GLOBALES
   ============================================================ */

function cerrarConEsc(e) {
    if (e.key === "Escape") {
        const modal = document.querySelector(".fixed:not(.hidden)");
        if (modal) cerrarModal(modal.id);
    }
}

function cerrarClickFuera(e) {
    const modal = e.currentTarget;
    if (e.target === modal) cerrarModal(modal.id);
}


/* ============================================================
   UTILIDADES GENERALES
   ============================================================ */

function getCSRFToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}


/* ============================================================
   ACTUALIZAR CARD — REGLA UNIVERSAL
   ============================================================ */

function actualizarCard(productoId, ubicacionId, nuevaCantidad) {
    let card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    if (!card) return;

    const cantidadSpan = card.querySelector(".cantidad-ubicacion");
    if (cantidadSpan) cantidadSpan.textContent = nuevaCantidad;

    card.dataset.cantidad = nuevaCantidad;

    /* ============================================================
       SI LLEGA A 0 → MODO SIN INVENTARIO
       ============================================================ */
    if (parseInt(nuevaCantidad) === 0) {

        card.classList.remove("bg-white");
        card.classList.add("bg-gray-100", "border-gray-400");

        card.style.backgroundColor = "#f3f4f6";
        card.style.borderColor = "#9ca3af";

        let btnEliminar = card.querySelector(".btn-eliminar-inv");

        if (!btnEliminar) {
            btnEliminar = document.createElement("button");
            btnEliminar.className =
                "btn-eliminar-inv mt-2 text-red-600 text-xs flex items-center gap-1 hover:text-red-800 font-semibold";
            btnEliminar.innerHTML = "🗑️ Eliminar inventario";
            btnEliminar.onclick = () => eliminarInventarioHandler(productoId, ubicacionId);

            const cantidadP = cantidadSpan.parentElement;
            cantidadP.insertAdjacentElement("afterend", btnEliminar);
        }

        card.style.order = 9999;
        return;
    }

    /* ============================================================
       SI LA CANTIDAD > 0 → MODO NORMAL
       ============================================================ */
    card.style.backgroundColor = "";
    card.style.borderColor = "";
    card.classList.remove("bg-gray-100", "border-gray-400");
    card.classList.add("bg-white");
    card.style.order = 0;

    const btnEliminar = card.querySelector(".btn-eliminar-inv");
    if (btnEliminar) btnEliminar.remove();
}


/* ============================================================
   ORDENAMIENTO INICIAL (MANDAR CARDS EN 0 AL FINAL)
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    const cards = document.querySelectorAll("#gridProductos .cardProducto");

    cards.forEach(card => {
        const cantidad = parseInt(card.dataset.cantidad);
        card.style.order = cantidad === 0 ? 9999 : 0;
    });
});


/* ============================================================
   BUSCADOR CON ANIMACIÓN + REORDENAMIENTO
   ============================================================ */

document.getElementById("buscadorProductos").addEventListener("input", function () {
    const texto = this.value.toLowerCase().trim();
    const cards = Array.from(document.querySelectorAll("#gridProductos .cardProducto"));

    cards.forEach(card => {
        const nombre = card.querySelector(".nombre").textContent.toLowerCase();
        const categoria = card.querySelector(".categoria").textContent.toLowerCase();
        const subcategoria = card.querySelector(".subcategoria").textContent.toLowerCase();
        const codigo = card.querySelector(".codigo")
            ? card.querySelector(".codigo").textContent.toLowerCase()
            : "";

        const coincide =
            nombre.includes(texto) ||
            categoria.includes(texto) ||
            subcategoria.includes(texto) ||
            codigo.includes(texto);

        if (coincide) {
            card.style.display = "flex";
            requestAnimationFrame(() => {
                card.style.opacity = "1";
                card.style.transform = "scale(1)";
            });
        } else {
            card.style.opacity = "0";
            card.style.transform = "scale(0.95)";
            setTimeout(() => {
                if (!texto) return;
                card.style.display = "none";
            }, 150);
        }
    });

    // Reordenar coincidencias arriba
    const coincidencias = cards.filter(card => {
        const nombre = card.querySelector(".nombre").textContent.toLowerCase();
        const categoria = card.querySelector(".categoria").textContent.toLowerCase();
        const subcategoria = card.querySelector(".subcategoria").textContent.toLowerCase();
        const codigo = card.querySelector(".codigo")
            ? card.querySelector(".codigo").textContent.toLowerCase()
            : "";

        return (
            nombre.includes(texto) ||
            categoria.includes(texto) ||
            subcategoria.includes(texto) ||
            codigo.includes(texto)
        );
    });

    const noCoincidencias = cards.filter(card => !coincidencias.includes(card));

    coincidencias.forEach(card => card.style.order = 0);
    noCoincidencias.forEach(card => card.style.order = 1);

    // Restaurar orden original si el buscador está vacío
    if (!texto) {
        cards.forEach(card => {
            const cantidad = parseInt(card.dataset.cantidad);
            card.style.order = cantidad === 0 ? 9999 : 0;
        });
    }
});


/* ============================================================
   MENSAJES GLOBALES
   ============================================================ */

function mostrarMensaje(texto) {
    const cont = document.getElementById("mensajeGlobal");
    if (!cont) return;

    cont.innerHTML = `
        <div class="px-4 py-3 bg-green-100 border border-green-300 text-green-800 rounded-lg shadow mb-4">
            ${texto}
        </div>
    `;

    setTimeout(() => cont.innerHTML = "", 4000);
}

function mostrarError(texto) {
    const cont = document.getElementById("mensajeGlobal");
    if (!cont) return;

    cont.innerHTML = `
        <div class="px-4 py-3 bg-red-100 border border-red-300 text-red-800 rounded-lg shadow mb-4">
            ${texto}
        </div>
    `;

    setTimeout(() => cont.innerHTML = "", 5000);
}