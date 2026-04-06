console.log("🔥 transferir.js CARGADO (inventario_ubicacion) 🔥");

/* ============================================================
   ABRIR MODAL TRANSFERIR
   ============================================================ */

function abrirModalTransferir(producto, origen) {
    console.clear();
    console.log("=== ABRIR MODAL TRANSFERIR ===");

    const form = document.getElementById("formTransferir");
    const selectDestino = document.getElementById("destino_select");

    form.querySelector("[name='producto_id']").value = producto;
    form.querySelector("[name='origen_id']").value = origen;
    selectDestino.value = "";

    // Card origen (solo existe esta)
    const card = document.getElementById(`card_${producto}_${origen}`);
    console.log("Card origen encontrada:", card);

    const cantidadOrigen = card?.dataset.cantidad || "0";

    document.getElementById("cantidad_origen_label").textContent = cantidadOrigen;
    document.getElementById("transferir_producto_nombre").textContent =
        card?.dataset.nombre || "Producto";

    document.getElementById("cantidad_destino_label").textContent = "0";

    // Listener EN VIVO
    selectDestino.onchange = () => {
        const destId = selectDestino.value;
        console.log("📌 Destino seleccionado:", destId);
        actualizarCantidadDestino(producto, destId);
    };

    abrirModal("modalTransferir");
}


/* ============================================================
   ACTUALIZAR CANTIDAD DESTINO EN VIVO (USANDO inventarioTodas)
   ============================================================ */

function actualizarCantidadDestino(producto, destinoId) {
    console.log("=== ACTUALIZAR CANTIDAD DESTINO ===");

    const lblDestino = document.getElementById("cantidad_destino_label");

    if (!destinoId) {
        lblDestino.textContent = "0";
        return;
    }

    // ⭐ Buscar en inventarioTodas (NO en el DOM)
    const inv = window.inventarioTodas.find(
        x => x.producto_id == producto && x.ubicacion_id == destinoId
    );

    console.log("Registro encontrado en inventarioTodas:", inv);

    const cantidad = inv ? inv.cantidad_actual : 0;

    console.log("Cantidad destino REAL:", cantidad);

    lblDestino.textContent = cantidad;
}


/* ============================================================
   TRANSFERENCIA SIMPLE — PROCESAR FORMULARIO
   ============================================================ */

async function confirmarTransferir(event) {
    event.preventDefault();

    console.log("=== CONFIRMAR TRANSFERIR ===");

    const form = event.currentTarget.closest("form");
    const data = new FormData(form);

    const destinoId = document.getElementById("destino_select").value;
    data.set("destino", destinoId);

    console.log("📤 Datos enviados:", Object.fromEntries(data.entries()));

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: data,
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });

        const result = await response.json();

        console.log("📥 Respuesta del servidor:", result);

        if (!result.success) {
            console.error("❌ Errores:", result.errors);

            // ⭐⭐⭐ ERROR DENTRO DEL MODAL (NO SE CIERRA)
            mostrarErrorEnModal("modalTransferir", result.errors.join(", "));

            return;
        }

        mostrarMensaje(result.mensaje);

        console.log("🔄 Actualizando card ORIGEN...");
        actualizarCard(
            result.producto_id,
            result.origen_id,
            result.cantidad_origen
        );

        console.log("🔄 Actualizando card DESTINO...");
        actualizarCard(
            result.producto_id,
            result.destino_id,
            result.cantidad_destino
        );

        console.log("✔ Cerrando modal...");
        cerrarModal("modalTransferir");

    } catch (err) {
        console.error("💥 ERROR FATAL EN TRANSFERENCIA:", err);

        // ⭐⭐⭐ ERROR DENTRO DEL MODAL
        mostrarErrorEnModal("modalTransferir", "Error inesperado al transferir inventario.");
    }
}