// ============================
// PRODUCTO EXISTENTE (AJAX)
// ============================
//
// Esta versión:
// - NO cambia el action del form
// - NO toca enctype
// - NO destruye el input file
// - Solo llena campos si el producto existe
// - Solo desbloquea si el usuario borra el código
// ============================

export function initProductoExistente({
    form,
    codigoInput,
    submitBtn,
    nombreInput,
    descripcionInput,
    mayoreoInput,
    menudeoInput,
    docenaInput,
    tipoCodigoInput,
    duenioSelect,
    categoriaPadreSelect,
    subcategoriaSelect,
    atributosContainer,
    ubicacionSelect,
    onProductoEncontrado,
    onProductoNoEncontrado,
}) {

    let buscando = false;

    // ============================
    // MINI MENSAJE ELEGANTE
    // ============================
    function mostrarMensaje(msg) {
        let box = document.getElementById("msg-producto-existente");

        if (!box) {
            box = document.createElement("div");
            box.id = "msg-producto-existente";
            box.className = "bg-yellow-100 text-yellow-800 p-2 rounded mb-3 text-sm font-semibold";
            form.prepend(box);
        }

        box.textContent = msg;

        setTimeout(() => {
            if (box) box.remove();
        }, 2500);
    }

    // ============================
    // ENTER → BUSCAR PRODUCTO
    // ============================
    codigoInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            buscarYCompletar(codigoInput.value);
        }
    });

    // ============================
    // INPUT → SOLO LIMPIAR SI HABÍA PRODUCTO CARGADO
    // ============================
    codigoInput.addEventListener("input", () => {

        if (buscando) return;

        const hiddenId = document.getElementById("id_producto_id");

        // 🔥 SOLO limpiar si antes había un producto cargado
        if (hiddenId) {
            hiddenId.remove();

            // Desbloquear campos, pero NO borrar valores
            nombreInput.removeAttribute("readonly");
            descripcionInput.removeAttribute("readonly");
            mayoreoInput.removeAttribute("readonly");
            menudeoInput.removeAttribute("readonly");
            docenaInput.removeAttribute("readonly");
            tipoCodigoInput.removeAttribute("readonly");

            duenioSelect.disabled = false;
            categoriaPadreSelect.disabled = false;
            subcategoriaSelect.disabled = false;

            nombreInput.classList.remove("bg-gray-100");
            descripcionInput.classList.remove("bg-gray-100");
            mayoreoInput.classList.remove("bg-gray-100");
            menudeoInput.classList.remove("bg-gray-100");
            docenaInput.classList.remove("bg-gray-100");
            tipoCodigoInput.classList.remove("bg-gray-100");
            duenioSelect.classList.remove("bg-gray-100");
            categoriaPadreSelect.classList.remove("bg-gray-100");
            subcategoriaSelect.classList.remove("bg-gray-100");

            // 🔥 YA NO CAMBIAMOS EL ACTION DEL FORM
            // El form SIEMPRE se envía a /nuevo_producto/
            submitBtn.textContent = "Registrar producto";

            submitBtn.classList.remove("bg-green-600", "hover:bg-green-700");
            submitBtn.classList.add("bg-red-600", "hover:bg-red-700");
        }
    });

    // ============================
    // FUNCIÓN PRINCIPAL
    // ============================
    async function buscarYCompletar(codigo) {
        if (!codigo) return;

        buscando = true;
        codigoInput.classList.add("opacity-50");

        try {
            const url = `/inventario/buscar_producto/?codigo=${encodeURIComponent(codigo)}`;
            const resp = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });

            if (!resp.ok) {
                mostrarMensaje("Error consultando el servidor.");
                return;
            }

            const data = await resp.json();

            // NO EXISTE
            if (!data.existe) {
                mostrarMensaje("No encontré ningún producto con ese código.");
                onProductoNoEncontrado();
                return;
            }

            // EXISTE → llenar campos
            nombreInput.value = data.nombre || "";
            descripcionInput.value = data.descripcion || "";
            mayoreoInput.value = data.precio_mayoreo ?? "";
            menudeoInput.value = data.precio_menudeo ?? "";
            docenaInput.value = data.precio_docena ?? "";
            tipoCodigoInput.value = data.tipo_codigo ?? "";

            if (duenioSelect && data.duenio_id) {
                duenioSelect.value = String(data.duenio_id);
            }

            if (categoriaPadreSelect && data.categoria_padre_id) {
                categoriaPadreSelect.value = String(data.categoria_padre_id);
            }

            // Guardar ID del producto
            let hiddenId = document.getElementById("id_producto_id");
            if (!hiddenId) {
                hiddenId = document.createElement("input");
                hiddenId.type = "hidden";
                hiddenId.id = "id_producto_id";
                hiddenId.name = "producto_id";
                form.appendChild(hiddenId);
            }
            hiddenId.value = data.producto_id;

            // 🔥 YA NO CAMBIAMOS EL ACTION DEL FORM
            // El backend decide si redirige a seleccionar_etiqueta_temp

            // Cambiar estilo del botón
            submitBtn.textContent = "Actualizar producto";
            submitBtn.classList.remove("bg-red-600", "hover:bg-red-700");
            submitBtn.classList.add("bg-green-600", "hover:bg-green-700");

            onProductoEncontrado(data);

        } catch (err) {
            console.error("Error buscando producto:", err);
            mostrarMensaje("Error inesperado al buscar el producto.");
        } finally {
            codigoInput.classList.remove("opacity-50");
            buscando = false;
        }
    }
}