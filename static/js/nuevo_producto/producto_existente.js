// ============================
// PRODUCTO EXISTENTE (AJAX)
// ============================

export function initProductoExistente({
    form,
    codigoInput,
    submitBtn,
    nombreInput,
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
    onLimpiar,
}) {

    let buscando              = false;
    let limpiando             = false;
    let esperandoNuevoEscaneo = false;

    // Teclas de edición manual — no deben tratarse como inicio de nuevo escaneo
    const TECLAS_EDICION = [
        "Backspace", "Delete", "ArrowLeft", "ArrowRight",
        "ArrowUp", "ArrowDown", "Home", "End"
    ];

    // ============================
    // MENSAJE
    // ============================
    function mostrarMensaje(msg, tipo = "info") {
        let box = document.getElementById("msg-producto-existente");
        if (!box) {
            box = document.createElement("div");
            box.id = "msg-producto-existente";
            codigoInput.closest(".space-y-1")?.insertAdjacentElement("afterend", box);
        }
        const colores = {
            info:    "bg-[#FFBE0B] text-black",
            success: "bg-[#06D6A0] text-black",
            error:   "bg-[#FF006E] text-white",
        };
        box.className = `border-4 border-black shadow-[4px_4px_0_0_black] px-6 py-3
                         font-black uppercase tracking-widest text-sm mb-4
                         ${colores[tipo] || colores.info}`;
        box.textContent = msg;
        setTimeout(() => { if (box) box.remove(); }, 2500);
    }

    // ============================
    // LIMPIAR Y DESBLOQUEAR
    // ============================
    function limpiarYDesbloquear() {
        limpiando = true;

        document.getElementById("id_producto_id")?.remove();

        nombreInput.value      = "";
        mayoreoInput.value     = "";
        menudeoInput.value     = "";
        docenaInput.value      = "";
        tipoCodigoInput.value  = "";

        [nombreInput, mayoreoInput,
         menudeoInput, docenaInput, tipoCodigoInput].forEach(el => {
            el.removeAttribute("readonly");
            el.classList.remove("bg-gray-100");
        });

        duenioSelect.disabled = false;
        duenioSelect.value    = "";
        duenioSelect.classList.remove("bg-gray-100");

        categoriaPadreSelect.disabled = false;
        categoriaPadreSelect.value    = "";
        categoriaPadreSelect.classList.remove("bg-gray-100");

        subcategoriaSelect.disabled  = false;
        subcategoriaSelect.innerHTML = "<option value=''>---------</option>";
        subcategoriaSelect.classList.remove("bg-gray-100");

        document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]')
            .forEach(cb => { cb.checked = false; cb.disabled = false; });

        const circle      = document.getElementById("foto-circle");
        const placeholder = document.getElementById("foto-placeholder");
        if (circle)      { circle.src = ""; circle.style.display = "none"; }
        if (placeholder) placeholder.style.display = "flex";

        const fotoInput = document.getElementById("id_foto_url");
        if (fotoInput) {
            fotoInput.style.pointerEvents = "auto";
            fotoInput.style.opacity       = "1";
        }

        submitBtn.textContent = "Continuar para seleccionar etiqueta";
        submitBtn.classList.remove("bg-[#06D6A0]", "bg-[#FF006E]");
        submitBtn.classList.add("bg-[#3A86FF]");

        if (onLimpiar) onLimpiar();

        limpiando = false;
    }

    // ============================
    // KEYDOWN
    // ============================
    codigoInput.addEventListener("keydown", (e) => {

        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = codigoInput.value.trim();
            if (!codigo) return;
            buscarYCompletar(codigo);
            esperandoNuevoEscaneo = true;
            return;
        }

        // Backspace y teclas de edición → NO son nuevo escaneo
        // Dejar que el input event maneje el borrado
        if (TECLAS_EDICION.includes(e.key)) return;

        // Cualquier otro carácter después de una búsqueda → nuevo escaneo
        if (esperandoNuevoEscaneo) {
            codigoInput.value     = "";
            esperandoNuevoEscaneo = false;
        }
    });

    // ============================
    // INPUT → si había producto cargado, limpiar todo
    // ============================
    codigoInput.addEventListener("input", () => {
        if (buscando || limpiando) return;
        if (!document.getElementById("id_producto_id")) return;
        limpiarYDesbloquear();
    });

    // ============================
    // BUSCAR
    // ============================
    async function buscarYCompletar(codigo) {
        if (!codigo || buscando) return;

        buscando = true;
        codigoInput.classList.add("opacity-50");

        try {
            const resp = await fetch(
                `/inventario/buscar_producto/?codigo=${encodeURIComponent(codigo)}`,
                { headers: { "X-Requested-With": "XMLHttpRequest" } }
            );

            if (!resp.ok) { mostrarMensaje("Error en el servidor.", "error"); return; }

            const data = await resp.json();

            if (!data.existe) {
                mostrarMensaje("No encontré ese código. Si es nuevo, llena los campos. 👇", "info");
                onProductoNoEncontrado();
                return;
            }

            nombreInput.value      = data.nombre        || "";
            mayoreoInput.value     = data.precio_mayoreo ?? "";
            menudeoInput.value     = data.precio_menudeo ?? "";
            docenaInput.value      = data.precio_docena  ?? "";
            tipoCodigoInput.value  = data.tipo_codigo    ?? "";

            if (data.duenio_id)
                duenioSelect.value = String(data.duenio_id);
            if (data.categoria_padre_id)
                categoriaPadreSelect.value = String(data.categoria_padre_id);

            let hiddenId = document.getElementById("id_producto_id");
            if (!hiddenId) {
                hiddenId      = document.createElement("input");
                hiddenId.type = "hidden";
                hiddenId.id   = "id_producto_id";
                hiddenId.name = "producto_id";
                form.appendChild(hiddenId);
            }
            hiddenId.value = data.producto_id;

            submitBtn.textContent = "Actualizar producto";
            submitBtn.classList.remove("bg-[#FF006E]", "bg-[#3A86FF]");
            submitBtn.classList.add("bg-[#06D6A0]");

            mostrarMensaje("¡Producto encontrado! 🎯", "success");
            onProductoEncontrado(data);

        } catch (err) {
            mostrarMensaje("Error inesperado.", "error");
            console.error(err);
        } finally {
            codigoInput.classList.remove("opacity-50");
            buscando = false;
        }
    }
}