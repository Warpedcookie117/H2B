/* ============================================================
   ELIMINAR INVENTARIO / DESACTIVAR PRODUCTO — MODAL PROFESIONAL
   ============================================================ */

async function eliminarInventarioHandler(productoId, ubicacionId) {

    // 1. Consultar inventario global del producto
    const response = await fetch(`/inventario/api/ubicaciones-del-producto/${productoId}/`);
    const data = await response.json();

    const ubicaciones = data.ubicaciones || [];

    // 2. Verificar si hay inventario en otras ubicaciones
    const otrasUbicaciones = ubicaciones.filter(
        u => u.id != ubicacionId && u.cantidad > 0
    );

    let titulo = "";
    let mensaje = "";
    let tipo = "";

    if (otrasUbicaciones.length > 0) {
        // Solo eliminar inventario de esta ubicación
        titulo = "Eliminar inventario de esta ubicación";
        mensaje = `Este producto aún existe en otras ubicaciones.\n\n¿Deseas eliminar SOLO el inventario de esta ubicación?`;
        tipo = "inventario";
    } else {
        // Desactivar producto completo
        titulo = "Desactivar producto";
        mensaje = `Este producto ya no tiene stock en ninguna ubicación.\n\nAl desactivarlo dejará de aparecer en el inventario y en el POS.\n\nPuedes reactivarlo cuando lo necesites.`;
        tipo = "producto";
    }

    abrirModalEliminar(titulo, mensaje, productoId, ubicacionId, tipo);
}


/* ============================================================
   ABRIR MODAL — muestra u oculta el campo de motivo según tipo
   ============================================================ */

function abrirModalEliminar(titulo, mensaje, productoId, ubicacionId, tipo) {
    document.getElementById("modalEliminarTitulo").textContent = titulo;
    document.getElementById("modalEliminarMensaje").textContent = mensaje;
    document.getElementById("eliminar_producto_id").value = productoId;
    document.getElementById("eliminar_ubicacion_id").value = ubicacionId;
    document.getElementById("eliminar_tipo").value = tipo;

    // Mostrar campo motivo solo si es desactivación
    const campMotivo = document.getElementById("campo_motivo");
    const inputMotivo = document.getElementById("motivo_desactivacion");

    if (tipo === "producto") {
        campMotivo.classList.remove("hidden");
        inputMotivo.value = "";
        // Cambiar texto del botón
        document.getElementById("btn_confirmar_eliminar").textContent = "Desactivar";
        document.getElementById("btn_confirmar_eliminar").className =
            "px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded text-sm transition";
    } else {
        campMotivo.classList.add("hidden");
        document.getElementById("btn_confirmar_eliminar").textContent = "Eliminar";
        document.getElementById("btn_confirmar_eliminar").className =
            "px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded text-sm transition";
    }

    abrirModal("modalEliminar");
}


/* ============================================================
   CONFIRMAR
   ============================================================ */

async function confirmarEliminar() {
    const productoId  = document.getElementById("eliminar_producto_id").value;
    const ubicacionId = document.getElementById("eliminar_ubicacion_id").value;
    const tipo        = document.getElementById("eliminar_tipo").value;

    // ── Eliminar inventario de esta ubicación ────────────────
    if (tipo === "inventario") {
        cerrarModal("modalEliminar");

        const resp = await fetch(`/inventario/api/inventario-ubicacion/${productoId}/${ubicacionId}/`, {
            method: "DELETE",
            headers: { "X-CSRFToken": getCSRFToken() }
        });

        const result = await resp.json();

        if (!result.success) {
            mostrarError(result.errors || "Error al eliminar inventario.");
            return;
        }

        eliminarCardUI(productoId, ubicacionId);
        mostrarMensaje("Inventario eliminado correctamente.");
        return;
    }

    // ── Desactivar producto completo ─────────────────────────
    if (tipo === "producto") {
        const motivo = document.getElementById("motivo_desactivacion").value.trim();

        if (!motivo) {
            document.getElementById("motivo_desactivacion").focus();
            document.getElementById("motivo_desactivacion").classList.add("border-red-500");
            return;
        }

        cerrarModal("modalEliminar");

        const resp = await fetch(`/inventario/api/producto/${productoId}/desactivar/`, {
            method: "POST",
            headers: {
                "X-CSRFToken": getCSRFToken(),
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ motivo })
        });

        const result = await resp.json();

        if (!result.success) {
            mostrarError(result.errors || "Error al desactivar producto.");
            return;
        }

        // Animar y remover todas las cards del producto
        eliminarTodasLasCardsDelProducto(productoId);
    }
}


/* ============================================================
   UI — ANIMACIONES
   ============================================================ */

function eliminarCardUI(productoId, ubicacionId) {
    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    if (!card) return;

    card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
    card.style.opacity = "0";
    card.style.transform = "translateY(5px) scale(0.95)";

    setTimeout(() => card.remove(), 250);
}

function eliminarTodasLasCardsDelProducto(productoId) {
    const cards = document.querySelectorAll(`[data-producto="${productoId}"]`);

    cards.forEach(card => {
        card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
        card.style.opacity = "0";
        card.style.transform = "translateY(5px) scale(0.95)";
        setTimeout(() => card.remove(), 250);
    });
}


/* ============================================================
   CSRF TOKEN
   ============================================================ */

function getCSRFToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}