// ============================
// PRODUCTO EXISTENTE (AJAX)
// ============================
//
// Este módulo detecta si el código existe y trae sus datos.
// No bloquea campos aquí — eso lo hace el orquestador.
//

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

    // Flag para evitar que "input" limpie mientras estamos buscando
    let buscando = false;

    // ============================
    // EVENTO PRINCIPAL: ENTER
    // ============================
    codigoInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            buscarYCompletar(codigoInput.value);
        }
    });

    // ============================
    // LIMPIEZA AL ESCRIBIR
    // ============================
    codigoInput.addEventListener("input", () => {

        if (buscando) return; // ← NO limpiar mientras se busca

        // 1. Borrar hiddenId
        const hiddenId = document.getElementById("id_producto_id");
        if (hiddenId) hiddenId.remove();

        // 2. Limpiar campos del producto
        nombreInput.value = "";
        descripcionInput.value = "";
        mayoreoInput.value = "";
        menudeoInput.value = "";
        docenaInput.value = "";
        tipoCodigoInput.value = "";
        duenioSelect.value = "";
        categoriaPadreSelect.value = "";
        subcategoriaSelect.innerHTML = "";

        // 3. Limpiar atributos dinámicos
        atributosContainer.innerHTML = "";

        // 4. Desbloquear campos
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

        // 5. Resetear botón y acción del form
        form.action = "/inventario/nuevo_producto/";
        submitBtn.textContent = "Registrar producto";

        submitBtn.classList.remove("bg-green-600", "hover:bg-green-700");
        submitBtn.classList.add("bg-red-600", "hover:bg-red-700");
        
        // 6. Limpiar temporadas
        const checkboxes = document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]');
        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.disabled = false;
        });

        // 7. Limpiar y habilitar foto
        const fotoInput = document.getElementById("id_foto_url");
        if (fotoInput) {
            fotoInput.disabled = false;
            fotoInput.value = ""; // limpia selección de archivo
        }

        const previewFoto = document.getElementById("preview-foto");
        if (previewFoto) {
            previewFoto.innerHTML = "";
        }

    });

    // ============================
    // FUNCIÓN PRINCIPAL
    // ============================
    async function buscarYCompletar(codigo) {
        if (!codigo) return;

        buscando = true; // ← ACTIVAMOS FLAG

        codigoInput.classList.add("opacity-50");

        try {
            const url = `/inventario/buscar_producto/?codigo=${encodeURIComponent(codigo)}`;
            const resp = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();

            // NO EXISTE
            if (!data.existe) {
                alert("No encontré ninguna coincidencia con ese código.");
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

            // Callback final
            onProductoEncontrado(data);

        } catch (err) {
            console.error("Error buscando producto:", err);
            alert("Ocurrió un error al buscar el producto.");
        } finally {
            codigoInput.classList.remove("opacity-50");
            buscando = false; // ← DESACTIVAMOS FLAG
        }
    }
}