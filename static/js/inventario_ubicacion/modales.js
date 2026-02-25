/* ============================================================
   MODALES — ABRIR Y CERRAR
   ============================================================ */

/**
 * Abre un modal genérico por ID base
 * Ejemplo: abrirModal("modalAgregar_25")
 */
function abrirModal(modalId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) {
        console.error("Modal no encontrado:", modalId);
        return;
    }

    modal.classList.remove("hidden");
    content.classList.remove("opacity-0", "scale-95");
    void content.offsetWidth;
}

/**
 * Cierra un modal genérico
 */
function cerrarModal(modalId) {
    const modal = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) return;

    content.classList.add("opacity-0", "scale-95");

    setTimeout(() => {
        modal.classList.add("hidden");
    }, 150);
}


/* ============================================================
   UTILIDAD — LEER CANTIDAD ACTUAL DESDE LA CARD
   ============================================================ */

function obtenerCantidadActual(productoId, ubicacionId) {
    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    if (!card) {
        console.error("Card no encontrada:", productoId, ubicacionId);
        return 0;
    }
    return card.dataset.cantidad;
}


/* ============================================================
   MODALES ESPECÍFICOS
   ============================================================ */


/* ---------------------------
   AGREGAR INVENTARIO
---------------------------- */

function abrirModalAgregarDesdeCard(productoId, ubicacionId) {
    const modalId = `modalAgregar_${productoId}`;
    abrirModal(modalId);

    // Set hidden fields
    document.querySelector(`#${modalId} input[name="producto_id"]`).value = productoId;
    document.querySelector(`#${modalId} input[name="ubicacion_id"]`).value = ubicacionId;

    // ⭐ LEER CANTIDAD ACTUAL DESDE LA CARD
    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    const cantidadActual = card.dataset.cantidad;

    // ⭐ ACTUALIZAR TEXTO DEL MODAL
    const spanCantidad = document.querySelector(`#${modalId} .cantidad-actual`);
    if (spanCantidad) spanCantidad.textContent = cantidadActual;
}



/* ---------------------------
   AJUSTAR INVENTARIO
---------------------------- */

function abrirModalAjustarDesdeCard(productoId, ubicacionId) {
    const cantidadActual = obtenerCantidadActual(productoId, ubicacionId);
    abrirModalAjustar(productoId, ubicacionId, cantidadActual);
}

function abrirModalAjustar(productoId, ubicacionId, cantidadActual) {
    const modalId = `modalAjustar_${productoId}`;
    abrirModal(modalId);

    // Set hidden fields
    document.querySelector(`#${modalId} input[name="producto_id"]`).value = productoId;
    document.querySelector(`#${modalId} input[name="ubicacion_id"]`).value = ubicacionId;

    // Input cantidad
    const inputCantidad = document.getElementById(`ajustar_cantidad_${productoId}`);
    if (inputCantidad) inputCantidad.value = cantidadActual;

    // Texto de cantidad actual
    const spanCantidad = document.querySelector(`#${modalId} .cantidad-actual`);
    if (spanCantidad) spanCantidad.textContent = cantidadActual;
}



/* ---------------------------
   TRANSFERENCIA SIMPLE
---------------------------- */

function abrirModalTransferirDesdeCard(productoId, ubicacionId) {
    const cantidadActual = obtenerCantidadActual(productoId, ubicacionId);
    abrirModalTransferir(productoId, ubicacionId, cantidadActual);
}

function abrirModalTransferir(productoId, origenId, cantidadActual) {
    const modalId = `modalTransferir_${productoId}`;
    abrirModal(modalId);

    document.querySelector(`#${modalId} input[name="producto_id"]`).value = productoId;
    document.querySelector(`#${modalId} input[name="origen_id"]`).value = origenId;

    // Actualizar texto de cantidad actual
    const spanCantidad = document.querySelector(`#${modalId} .cantidad-actual`);
    if (spanCantidad) spanCantidad.textContent = cantidadActual;
}



/* ---------------------------
   TRANSFERENCIA MÚLTIPLE
---------------------------- */

function abrirModalTransferirMultiple(ubicacionId) {
    const modalId = `modalTransferirMultiple`;
    abrirModal(modalId);

    document.getElementById("transferir_multiple_origen_id").value = ubicacionId;
    document.getElementById("transferir_multiple_tabla").innerHTML = "";
    document.getElementById("transferir_multiple_search").value = "";
    document.getElementById("transferir_multiple_resultados").classList.add("hidden");
}

/* ---------------------------
   ELIMINAR INVENTARIO / PRODUCTO
---------------------------- */

function abrirModalEliminar(titulo, mensaje, productoId, ubicacionId, tipo) {
    const modalId = "modalEliminar";
    abrirModal(modalId);

    // IDs correctos según TU modal
    document.getElementById("modalEliminarTitulo").textContent = titulo;
    document.getElementById("modalEliminarMensaje").textContent = mensaje;

    document.getElementById("eliminar_producto_id").value = productoId;
    document.getElementById("eliminar_ubicacion_id").value = ubicacionId;
    document.getElementById("eliminar_tipo").value = tipo;
}