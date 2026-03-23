function submitAjuste(productoId, esDueno) {
    const form = document.getElementById(`formAjustar_${productoId}`);
    const modalId = `modalAjustar_${productoId}`;

    const formData = new FormData(form);

    fetch(form.action, {
        method: "POST",
        body: formData,
        headers: { "X-Requested-With": "XMLHttpRequest" }
    })
    .then(res => res.json())
    .then(data => {

        console.log("RESPUESTA:", data); // DEBUG

        if (!data.success) {
            mostrarError(data.errors?.join("<br>") || "Ocurrió un error.");
            return;
        }

        // ⭐ CASO 1: SOLICITUD (empleado)
        if (data.solicitud === true) {

            cerrarModal(modalId);

            mostrarMensaje("Se ha enviado su solicitud. Espere a que el dueño la apruebe.");

            return; // IMPORTANTE
        }

        // ⭐ CASO 2: AJUSTE DIRECTO (dueño)
        actualizarCard(
            data.producto_id,
            data.ubicacion_id,
            data.cantidad_actual
        );

        cerrarModal(modalId);

        mostrarMensaje("Ajuste aplicado correctamente.");
    })
    .catch(err => {
        console.error("ERROR EN FETCH:", err); // DEBUG
        mostrarError("Error de conexión.");
    });
}

document.addEventListener("input", function (e) {
    if (!e.target.matches(".input-ajustar-cantidad")) return;

    const input = e.target;
    const productoId = input.dataset.producto;
    const ubicacionId = input.dataset.ubicacion;

    const cantidadNueva = parseFloat(input.value) || 0;

    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    const cantidadActual = parseFloat(card.dataset.cantidad);

    const btn = document.getElementById(`btnAjustar_${productoId}`);
    if (!btn) return;

    if (cantidadNueva > cantidadActual) {
        btn.textContent = "Ajustar inventario";
        btn.classList.remove("bg-green-600", "hover:bg-green-700");
        btn.classList.add("bg-blue-600", "hover:bg-blue-700");
    } else if (cantidadNueva < cantidadActual) {
        btn.textContent = "Enviar solicitud";
        btn.classList.remove("bg-blue-600", "hover:bg-blue-700");
        btn.classList.add("bg-green-600", "hover:bg-green-700");
    } else {
        btn.textContent = "Ajustar inventario";
        btn.classList.remove("bg-green-600", "hover:bg-green-700");
        btn.classList.add("bg-blue-600", "hover:bg-blue-700");
    }
});