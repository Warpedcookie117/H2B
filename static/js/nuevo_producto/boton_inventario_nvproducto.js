import { iniciarBarraProgreso } from "./barra_progreso.js";

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

    let msgBox = document.getElementById("msg-validacion");
    if (!msgBox) {
        msgBox = document.createElement("div");
        msgBox.id = "msg-validacion";
        msgBox.className = "hidden border-4 border-black shadow-[4px_4px_0_0_black] bg-[#FFBE0B] text-black font-black px-6 py-3 uppercase tracking-widest text-sm";
        form.prepend(msgBox);
    }

    function mostrarError(msg) {
        msgBox.textContent = msg;
        msgBox.classList.remove("hidden");
        msgBox.scrollIntoView({ behavior: "smooth", block: "center" });
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
            submitBtn.classList.remove("bg-[#FF006E]");
            submitBtn.classList.add("bg-[#3A86FF]");
        } else {
            submitBtn.textContent = "Registrar producto";
            submitBtn.classList.remove("bg-[#3A86FF]");
            submitBtn.classList.add("bg-[#FF006E]");
        }
    }

    codigoInput.addEventListener("input", actualizarBotonSegunCodigo);
    actualizarBotonSegunCodigo();

    // ============================
    // CLICK EN BOTÓN
    // ============================
    submitBtn.addEventListener("click", (e) => {

        // Si el form ya tiene action de agregar_inventario → submit directo vía POST
        if (form.action.includes("/inventario/agregar_inventario/")) {
            // Dejar que el form haga POST normal — no interceptar
            return;
        }

        const botonEsAzul = submitBtn.classList.contains("bg-[#3A86FF]");

        if (botonEsAzul) {
            e.preventDefault();
            limpiarError();

            let errores = false;

            const obligatorios = [
                nombreInput, descripcionInput, mayoreoInput, menudeoInput,
                duenioSelect, categoriaPadreSelect, subcategoriaSelect, ubicacionSelect
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

            const temporadaChecks = document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]');
            if (temporadaChecks.length > 0) {
                const alguna = Array.from(temporadaChecks).some(cb => cb.checked);
                if (!alguna) {
                    mostrarError("Selecciona al menos una temporada.");
                    return;
                }
            }

            const fotoInput = document.getElementById("id_foto_url");
            if (fotoInput && fotoInput.files.length === 0) {
                marcarCampo(fotoInput);
                mostrarError("Debes subir una foto del producto.");
                return;
            }

            const modal = document.getElementById("modal-etiqueta");
            if (modal) modal.showModal();
            return;
        }

        // Botón rojo → validar, luego fetch + barra de progreso
        e.preventDefault();
        limpiarError();

        let erroresRojo = false;

        const obligatoriosRojo = [
            nombreInput, descripcionInput, mayoreoInput, menudeoInput,
            duenioSelect, categoriaPadreSelect, subcategoriaSelect, ubicacionSelect
        ];
        obligatoriosRojo.forEach(el => {
            limpiarCampo(el);
            if (!el.value || el.value.trim() === "") {
                marcarCampo(el);
                erroresRojo = true;
            }
        });

        const cantidadInput = document.getElementById("id_cantidad_inicial");
        if (cantidadInput) {
            limpiarCampo(cantidadInput);
            if (!cantidadInput.value || parseInt(cantidadInput.value) < 1) {
                marcarCampo(cantidadInput);
                erroresRojo = true;
            }
        }

        const fotoInputRojo = document.getElementById("id_foto_url");
        if (fotoInputRojo && fotoInputRojo.files.length === 0) {
            marcarCampo(fotoInputRojo);
            erroresRojo = true;
        }

        if (erroresRojo) {
            mostrarError("Completa todos los campos obligatorios antes de registrar.");
            return;
        }

        const fetchPromise = fetch(form.action || window.location.href, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" }
        });

        iniciarBarraProgreso(fetchPromise);
    });

    // ============================
    // CAMBIO DE UBICACIÓN
    // ============================
    ubicacionSelect?.addEventListener("change", () => {
        const productoId = document.getElementById("id_producto_id")?.value;
        if (productoId) {
            verificarInventario(productoId, ubicacionSelect.value);
        }
    });

    // ============================
    // VERIFICAR INVENTARIO
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
                submitBtn.classList.remove("bg-[#06D6A0]");
                submitBtn.classList.add("bg-[#FF006E]");
                return;
            }

            form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;
            form.method = "post";

            if (!inventario_existe) {
                submitBtn.textContent = "Crear inventario en esta ubicación";
            } else {
                submitBtn.textContent = "Agregar inventario";
            }

            submitBtn.classList.remove("bg-[#FF006E]", "bg-[#3A86FF]");
            submitBtn.classList.add("bg-[#06D6A0]");

        } catch (err) {
            console.error("Error verificando inventario:", err);
        }
    }

    return { verificarInventario };
}