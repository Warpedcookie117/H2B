/* ============================================================
   AGREGAR INVENTARIO — AJAX COMPLETO
   ============================================================ */

async function confirmarAgregar(event) {
    event.preventDefault();

    const form = event.currentTarget.closest("form");
    const cantidad = form.querySelector('input[name="cantidad"]').value;

    if (!cantidad || cantidad <= 0) {
        mostrarError("Debes ingresar una cantidad válida.");
        return;
    }

    const data = new FormData(form);
    const productoId = data.get("producto_id");
    const ubicacionId = data.get("ubicacion_id");

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });

        const result = await response.json();

        if (!result.success) {
            mostrarError(result.errors.join(", "));
            return;
        }

        // ⭐ Actualizar card en vivo
        actualizarCard(productoId, ubicacionId, result.cantidad_actual);

        // ⭐ Cerrar modal
        cerrarModal(`modalAgregar_${productoId}`);

        // ⭐ Mostrar mensaje de éxito
        mostrarMensaje("Cantidad agregada correctamente.");

    } catch (err) {
        mostrarError("Error inesperado al agregar inventario.");
    }
}