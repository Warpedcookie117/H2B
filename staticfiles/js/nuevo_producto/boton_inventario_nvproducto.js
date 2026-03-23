// ============================================
// BOTÓN + INVENTARIO (nuevo producto / existente)
// ============================================
//
// Validación completa ANTES de abrir el modal
// Sin alerts, sin popups feos
// Mensaje elegante + highlight de campos faltantes
//

export function initBotonInventario({
    form,
    submitBtn,
    ubicacionSelect,

    codigoInput,
    nombreInput,
    descripcionInput,
    mayoreoInput,
    menudeoInput,
    docenaInput,
    tipoCodigoInput,
    duenioSelect,
    categoriaPadreSelect,
    subcategoriaSelect
}) {

    // ============================
    // CONTENEDOR DE MENSAJES
    // ============================
    let msgBox = document.getElementById("msg-validacion");
    if (!msgBox) {
        msgBox = document.createElement("div");
        msgBox.id = "msg-validacion";
        msgBox.className = "hidden bg-red-100 text-red-700 p-3 rounded mb-4";
        form.prepend(msgBox);
    }

    function mostrarError(msg) {
        msgBox.textContent = msg;
        msgBox.classList.remove("hidden");
    }

    function limpiarError() {
        msgBox.classList.add("hidden");
        msgBox.textContent = "";
    }

    function marcarCampo(el) {
        el.classList.add("border-red-500", "ring-2", "ring-red-300");
    }

    function limpiarCampo(el) {
        el.classList.remove("border-red-500", "ring-2", "ring-red-300");
    }

    // ============================
    // BOTÓN SEGÚN SI HAY CÓDIGO
    // ============================
    function actualizarBotonSegunCodigo() {
        const codigo = codigoInput.value.trim();

        if (!codigo) {
            submitBtn.textContent = "Continuar para seleccionar etiqueta";
            submitBtn.classList.remove("bg-red-600", "hover:bg-red-700");
            submitBtn.classList.add("bg-blue-600", "hover:bg-blue-700");
            return;
        }

        submitBtn.textContent = "Registrar producto";
        submitBtn.classList.remove("bg-blue-600", "hover:bg-blue-700");
        submitBtn.classList.add("bg-red-600", "hover:bg-red-700");
    }

    codigoInput.addEventListener("input", actualizarBotonSegunCodigo);
    actualizarBotonSegunCodigo();


    // ============================
    // VALIDACIÓN COMPLETA ANTES DE ABRIR MODAL
    // ============================
    submitBtn.addEventListener("click", (e) => {

        const botonEsAzul = submitBtn.classList.contains("bg-blue-600");

        // ============================
        // FLUJO DE ETIQUETA (botón azul)
        // ============================
        if (botonEsAzul) {
            e.preventDefault();
            limpiarError();

            let errores = false;

            // ============================
            // VALIDAR CAMPOS OBLIGATORIOS
            // ============================
            const obligatorios = [
                nombreInput,
                descripcionInput,
                mayoreoInput,
                menudeoInput,
                duenioSelect,
                categoriaPadreSelect,
                subcategoriaSelect,
                ubicacionSelect
            ];

            obligatorios.forEach(el => {
                limpiarCampo(el);
                if (!el.value || el.value.trim() === "") {
                    marcarCampo(el);
                    errores = true;
                }
            });

            if (errores) {
                mostrarError("Completa todos los campos obligatorios antes de seleccionar el tamaño de etiqueta.");
                return;
            }

            // ============================
            // VALIDAR TEMPORADAS (si existen)
            // ============================
            const temporadaChecks = document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]');
            if (temporadaChecks.length > 0) {
                const alguna = Array.from(temporadaChecks).some(cb => cb.checked);
                if (!alguna) {
                    mostrarError("Selecciona al menos una temporada.");
                    return;
                }
            }

            // ============================
            // VALIDAR ATRIBUTOS DINÁMICOS
            // ============================
            const atributosInputs = document.querySelectorAll("#atributos-container input, #atributos-container select");
            for (let el of atributosInputs) {
                limpiarCampo(el);
                if (!el.value || el.value.trim() === "") {
                    marcarCampo(el);
                    errores = true;
                }
            }

            if (errores) {
                mostrarError("Completa todos los atributos del producto antes de continuar.");
                return;
            }

            // ============================
            // VALIDAR FOTO (si es obligatoria)
            // ============================
            const fotoInput = document.getElementById("id_foto_url");
            if (fotoInput && fotoInput.required && fotoInput.files.length === 0) {
                marcarCampo(fotoInput);
                mostrarError("Debes subir una foto del producto.");
                return;
            }

            // ============================
            // TODO OK → ABRIR MODAL
            // ============================
            const modal = document.getElementById("modal-etiqueta");
            if (modal) modal.showModal();

            return;
        }

        // ============================
        // FLUJO NORMAL (botón rojo)
        // ============================
        // Aquí NO se abre modal
        // Aquí NO se valida otra vez
        // Aquí se hace POST directo
    });


    // ============================
    // CAMBIO DE UBICACIÓN (inventario existente)
    // ============================
    ubicacionSelect?.addEventListener("change", () => {
        const productoId = document.getElementById("id_producto_id")?.value;
        if (productoId) {
            verificarInventario(productoId, ubicacionSelect.value);
        }
    });

    // ============================
    // FUNCIÓN PRINCIPAL
    // ============================
    async function verificarInventario(productoId, ubicacionId) {
        if (!productoId || !ubicacionId) return;

        try {
            const url = `/inventario/verificar_estado_producto/?producto=${productoId}&ubicacion=${ubicacionId}`;
            const resp = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });

            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();
            const { producto_existe, inventario_existe } = data;

            if (!producto_existe) {
                form.action = `/inventario/nuevo_producto/`;
                submitBtn.textContent = "Registrar producto";
                submitBtn.classList.remove("bg-green-600", "hover:bg-green-700");
                submitBtn.classList.add("bg-red-600", "hover:bg-red-700");
                return;
            }

            if (producto_existe && !inventario_existe) {
                form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;
                submitBtn.textContent = "Crear inventario en esta ubicación";
                submitBtn.classList.remove("bg-red-600", "hover:bg-red-700");
                submitBtn.classList.add("bg-green-600", "hover:bg-green-700");
                return;
            }

            if (producto_existe && inventario_existe) {
                form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;
                submitBtn.textContent = "Agregar inventario";
                submitBtn.classList.remove("bg-red-600", "hover:bg-red-700");
                submitBtn.classList.add("bg-green-600", "hover:bg-green-700");
                return;
            }

        } catch (err) {
            console.error("Error verificando inventario:", err);
        }
    }

    // ============================
    // INTERCEPTAR SUBMIT PARA PASAR CANTIDAD
    // ============================
    submitBtn.addEventListener("click", (e) => {
        if (form.action.includes("/inventario/agregar_inventario/")) {
            e.preventDefault();

            const cantidad = document.querySelector("#id_cantidad_inicial")?.value || "";
            const url = form.action + `?cantidad_inicial=${cantidad}`;

            window.location.href = url;
        }
    });

    return {
        verificarInventario
    };
}