/* ============================================================
   PRODUCTOS INACTIVOS — JS
   (mostrarMensaje, mostrarError y getCSRFToken vienen de utils.js)
   ============================================================ */


/* ============================================================
   BUSCADOR + ESCÁNER
   ============================================================ */

const buscador = document.getElementById("buscadorProductos");
const sinResultados = document.getElementById("sinResultados");

if (buscador) {
    buscador.focus();

    let esperandoNuevoEscaneo = false;

    // Enter → el escáner terminó de enviar el código
    buscador.addEventListener("keydown", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = buscador.value.trim();
            if (!codigo) return;
            filtrarCards(codigo);
            esperandoNuevoEscaneo = true;
            return;
        }
        // Primer carácter después de un escaneo → limpiar input
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
            filtrarCards("");
        }
    });

    // Teclas globales → redirigir al buscador (para escanear sin hacer clic)
    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab", "Escape", "Enter", "ArrowUp", "ArrowDown",
             "ArrowLeft", "ArrowRight", "F1", "F2", "F3", "F4",
             "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12"].includes(e.key)) return;
        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
    });

    // Escritura manual → filtrar en tiempo real
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
}

function filtrarCards(texto) {
    texto = texto.toLowerCase().trim();
    const cards = Array.from(document.querySelectorAll(".cardProducto"));
    let visibles = 0;

    cards.forEach(card => {
        const nombre       = (card.dataset.nombre       || "").toLowerCase();
        const categoria    = (card.dataset.categoria    || "").toLowerCase();
        const subcategoria = (card.dataset.subcategoria || "").toLowerCase();

        const coincide = nombre.includes(texto) ||
                         categoria.includes(texto) ||
                         subcategoria.includes(texto);

        if (coincide) {
            card.style.display = "";
            card.classList.remove("oculto");
            visibles++;
        } else {
            card.classList.add("oculto");
            setTimeout(() => {
                if (buscador && buscador.value.trim()) card.style.display = "none";
            }, 250);
        }
    });

    if (!texto) {
        cards.forEach(card => {
            card.style.display = "";
            card.classList.remove("oculto");
        });
        visibles = cards.length;
    }

    if (sinResultados) {
        sinResultados.classList.toggle("hidden", visibles > 0 || !texto);
    }
}


/* ============================================================
   MODAL REACTIVAR — abrir
   ============================================================ */

function abrirModalReactivar(productoId, nombre) {
    document.getElementById("reactivar_producto_id").value = productoId;
    document.getElementById("reactivar_nombre").textContent = nombre;
    document.getElementById("reactivar_ubicacion").value = "";
    document.getElementById("reactivar_cantidad").value = "";
    abrirModal("modalReactivar");
}


/* ============================================================
   MODAL REACTIVAR — confirmar
   ============================================================ */

async function confirmarReactivar() {
    const productoId  = document.getElementById("reactivar_producto_id").value;
    const ubicacionId = document.getElementById("reactivar_ubicacion").value;
    const cantidad    = parseInt(document.getElementById("reactivar_cantidad").value || 0);

    if (!ubicacionId) {
        mostrarErrorEnModal("modalReactivar", "Debes seleccionar una ubicación.");
        return;
    }

    if (cantidad <= 0) {
        mostrarErrorEnModal("modalReactivar", "La cantidad debe ser mayor a 0.");
        return;
    }

    cerrarModal("modalReactivar");

    const resp = await fetch(`/inventario/api/producto/${productoId}/reactivar/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ ubicacion_id: ubicacionId, cantidad })
    });

    const result = await resp.json();

    if (!result.success) {
        mostrarError(result.errors || "Error al reactivar producto.");
        return;
    }

    const card = document.getElementById(`card_inactivo_${productoId}`);
    if (card) {
        card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
        card.style.opacity = "0";
        card.style.transform = "translateY(5px) scale(0.95)";
        setTimeout(() => card.remove(), 250);
    }

    mostrarMensaje(result.mensaje);
}


/* ============================================================
   MODAL ELIMINAR DEFINITIVO — abrir
   ============================================================ */

function abrirModalEliminarDefinitivo(productoId, nombre) {
    document.getElementById("eliminar_def_producto_id").value = productoId;
    document.getElementById("eliminar_def_nombre").textContent = nombre;
    abrirModal("modalEliminarDefinitivo");
}


/* ============================================================
   MODAL ELIMINAR DEFINITIVO — confirmar
   ============================================================ */

async function confirmarEliminarDefinitivo() {
    const productoId = document.getElementById("eliminar_def_producto_id").value;

    cerrarModal("modalEliminarDefinitivo");

    const resp = await fetch(`/inventario/api/producto/${productoId}/eliminar-definitivo/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCSRFToken() }
    });

    const result = await resp.json();

    if (!result.success) {
        mostrarError(result.errors || "Error al eliminar producto.");
        return;
    }

    const card = document.getElementById(`card_inactivo_${productoId}`);
    if (card) {
        card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
        card.style.opacity = "0";
        card.style.transform = "translateY(5px) scale(0.95)";
        setTimeout(() => card.remove(), 250);
    }

    mostrarMensaje(result.mensaje);
}
