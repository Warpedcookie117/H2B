/* ============================================================
   TRANSFERENCIA MÚLTIPLE — PROCESAR FORMULARIO
   ============================================================ */

/* ---------------------------
   ABRIR MODAL
---------------------------- */
function abrirModalTransferirMultiple(ubicacionId) {
    abrirModal("modalTransferirMultiple");

    // ⭐ CRÍTICO: asignar origen
    document.getElementById("transferir_multiple_origen_id").value = ubicacionId;

    // Limpiar tabla y buscador
    document.getElementById("transferir_multiple_tabla").innerHTML = "";
    document.getElementById("transferir_multiple_search").value = "";
    document.getElementById("transferir_multiple_resultados").classList.add("hidden");
}


/* ---------------------------
   BUSCAR PRODUCTO
---------------------------- */
async function buscarProductoMultiple(event) {
    const query = event.target.value.trim();
    const origenId = document.getElementById("transferir_multiple_origen_id").value;
    const resultadosDiv = document.getElementById("transferir_multiple_resultados");

    if (query.length < 2) {
        resultadosDiv.classList.add("hidden");
        return;
    }

    const response = await fetch(`/inventario/buscar_producto_en_ubicacion/?q=${query}&ubicacion=${origenId}`);
    const data = await response.json();

    resultadosDiv.innerHTML = "";
    resultadosDiv.classList.remove("hidden");

    data.resultados.forEach(prod => {
        const item = document.createElement("div");
        item.className = "p-2 hover:bg-gray-100 cursor-pointer";
        item.textContent = `${prod.nombre} (${prod.cantidad_actual} disponibles)`;
        item.onclick = () => agregarProductoMultiple(prod);
        resultadosDiv.appendChild(item);
    });
}


/* ---------------------------
   AGREGAR PRODUCTO A LA TABLA
---------------------------- */
function agregarProductoMultiple(prod) {
    const tabla = document.getElementById("transferir_multiple_tabla");

    // Evitar duplicados
    if (document.getElementById(`fila_prod_${prod.id}`)) return;

    const tr = document.createElement("tr");
    tr.id = `fila_prod_${prod.id}`;
    tr.className = "border-b";

    tr.innerHTML = `
        <td class="py-2">${prod.nombre}</td>
        <td class="py-2">${prod.cantidad_actual}</td>
        <td class="py-2">
            <input type="number" min="1" max="${prod.cantidad_actual}"
                   class="w-24 border border-gray-300 rounded-lg px-2 py-1 focus:ring-blue-500 focus:border-blue-500"
                   name="cantidad_${prod.id}">
        </td>
        <td class="py-2">
            <button onclick="this.closest('tr').remove()"
                    class="text-red-600 hover:text-red-800">
                Quitar
            </button>
        </td>
    `;

    tabla.appendChild(tr);

    document.getElementById("transferir_multiple_resultados").classList.add("hidden");
    document.getElementById("transferir_multiple_search").value = "";
}


/* ---------------------------
   CONFIRMAR TRANSFERENCIA MÚLTIPLE
---------------------------- */
async function confirmarTransferirMultiple(event) {
    event.preventDefault();

    const origenId = document.getElementById("transferir_multiple_origen_id").value;
    const destinoId = document.getElementById("transferir_multiple_destino").value;

    if (!origenId) {
        mostrarError("No se pudo determinar la ubicación origen.");
        return;
    }

    const filas = document.querySelectorAll("#transferir_multiple_tabla tr");

    if (filas.length === 0) {
        mostrarError("No has agregado productos.");
        return;
    }

    const payload = {
        destino_id: destinoId,
        productos: []
    };

    filas.forEach(fila => {
        const prodId = fila.id.replace("fila_prod_", "");
        const cantidad = fila.querySelector("input").value;

        if (cantidad && Number(cantidad) > 0) {
            payload.productos.push({
                id: prodId,
                cantidad: Number(cantidad)
            });
        }
    });

    if (payload.productos.length === 0) {
        mostrarError("Debes ingresar cantidades válidas.");
        return;
    }

    try {
        const response = await fetch(`/inventario/transferencia-multiple/${origenId}/`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCSRFToken()
            },
            body: JSON.stringify(payload)
        });

        const result = await response.json();

        if (!result.success) {
            mostrarError(result.errors || "Error desconocido del servidor.");
            return;
        }

        // Actualizar cards
        if (result.resultados) {
            result.resultados.forEach(r => {
                actualizarCard(r.producto_id, r.origen_id, r.cantidad_origen);
                actualizarCard(r.producto_id, r.destino_id, r.cantidad_destino);
            });
        }

        cerrarModal("modalTransferirMultiple");

        // ⭐ Mensaje de éxito consistente
        mostrarMensaje("Transferencia realizada correctamente.");

    } catch (err) {
        console.error(err);
        mostrarError("Error inesperado al realizar la transferencia múltiple.");
    }
}