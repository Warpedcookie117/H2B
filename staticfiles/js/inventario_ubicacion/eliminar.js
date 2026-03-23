/* ============================================================
   ELIMINAR INVENTARIO / PRODUCTO — MODAL PROFESIONAL
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
        // ⭐ SOLO eliminar inventario de esta ubicación
        titulo = "Eliminar inventario";
        mensaje = `Este producto aún existe en otras ubicaciones.\n\n
                   ¿Deseas eliminar SOLO el inventario de esta ubicación?`;
        tipo = "inventario";
    } else {
        // ⭐ Eliminar producto COMPLETO
        titulo = "Eliminar producto";
        mensaje = `Este producto YA NO existe en ninguna ubicación.\n\n
                   ¿Deseas eliminarlo COMPLETAMENTE de la base de datos?`;
        tipo = "producto";
    }

    abrirModalEliminar(titulo, mensaje, productoId, ubicacionId, tipo);
}


/* ============================================================
   CONFIRMAR ELIMINACIÓN
   ============================================================ */

async function confirmarEliminar() {
    const productoId = document.getElementById("eliminar_producto_id").value;
    const ubicacionId = document.getElementById("eliminar_ubicacion_id").value;
    const tipo = document.getElementById("eliminar_tipo").value;

    cerrarModal("modalEliminar");

    if (tipo === "inventario") {
        // ⭐ Eliminar inventario SOLO de esta ubicación
        const resp = await fetch(`/inventario/api/inventario-ubicacion/${productoId}/${ubicacionId}/`, {
            method: "DELETE",
            headers: { "X-CSRFToken": getCSRFToken() }
        });

        const result = await resp.json();

        if (!result.success) {
            mostrarError(result.errors || "Error al eliminar inventario.");
            return;
        }

        actualizarCard(productoId, ubicacionId, 0);
        return;
    }

    if (tipo === "producto") {
        // ⭐ Eliminar producto COMPLETO
        const resp = await fetch(`/inventario/api/producto/${productoId}/`, {
            method: "DELETE",
            headers: { "X-CSRFToken": getCSRFToken() }
        });

        const result = await resp.json();

        if (!result.success) {
            mostrarError(result.errors || "Error al eliminar producto.");
            return;
        }

        // Eliminar TODAS las cards del producto
        document.querySelectorAll(`[id^="card_${productoId}_"]`).forEach(c => c.remove());
    }
}


/* ============================================================
   ELIMINAR INVENTARIO
   ============================================================ */

function eliminarInventarioUbicacion(productoId, ubicacionId) {

    fetch(`/inventario/api/inventario-ubicacion/${productoId}/${ubicacionId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCSRFToken() }
    })
        .then(r => {
            if (!r.ok) throw new Error("Error al eliminar inventario.");
            return r.json();
        })
        .then(() => eliminarCardUI(productoId, ubicacionId))
        .catch(err => {
            console.error(err);
            mostrarError("No se pudo eliminar el inventario.");
        });
}


/* ============================================================
   ELIMINAR PRODUCTO COMPLETO
   ============================================================ */

function eliminarProductoCompleto(productoId) {

    fetch(`/inventario/api/producto/${productoId}/`, {
        method: "DELETE",
        headers: { "X-CSRFToken": getCSRFToken() }
    })
        .then(r => {
            if (!r.ok) throw new Error("Error al eliminar producto.");
            return r.json();
        })
        .then(() => eliminarTodasLasCardsDelProducto(productoId))
        .catch(err => {
            console.error(err);
            mostrarError("No se pudo eliminar el producto.");
        });
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