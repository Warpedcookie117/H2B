/* ============================================================
   AGREGAR INVENTARIO — AJAX COMPLETO
   ============================================================ */

async function confirmarAgregar(event) {
    event.preventDefault();

    const form = event.currentTarget.closest("form");
    const cantidad = form.querySelector('input[name="cantidad"]').value;

    const productoId = form.querySelector('input[name="producto_id"]').value;
    const modalId = `modalAgregar_${productoId}`;

    if (!cantidad || cantidad <= 0) {

        // ⭐⭐⭐ ERROR DENTRO DEL MODAL
        mostrarErrorEnModal(modalId, "Debes ingresar una cantidad válida.");

        return;
    }

    const data = new FormData(form);
    const ubicacionId = data.get("ubicacion_id");

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });

        const result = await response.json();

        if (!result.success) {

            // ⭐⭐⭐ ERROR DENTRO DEL MODAL
            mostrarErrorEnModal(modalId, result.errors.join(", "));

            return;
        }

        // ⭐ Actualizar card en vivo
        actualizarCard(productoId, ubicacionId, result.cantidad_actual);

        // ⭐ Cerrar modal
        cerrarModal(modalId);

        // ⭐ Mostrar mensaje de éxito
        mostrarMensaje("Cantidad agregada correctamente.");

    } catch (err) {

        // ⭐⭐⭐ ERROR DENTRO DEL MODAL
        mostrarErrorEnModal(modalId, "Error inesperado al agregar inventario.");
    }
}