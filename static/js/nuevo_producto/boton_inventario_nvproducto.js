import { iniciarBarraProgreso } from "./barra_progreso.js";

export function initBotonInventario({
    form,
    submitBtn,
    ubicacionSelect,
    codigoInput,
    nombreInput,
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
    function setBotonAzul() {
        submitBtn.textContent = "Continuar para seleccionar etiqueta";
        submitBtn.style.backgroundColor = "#3A86FF";
        submitBtn.dataset.estado = "azul";
    }

    function setBotonRojo() {
        submitBtn.textContent = "Registrar producto";
        submitBtn.style.backgroundColor = "#FF006E";
        submitBtn.dataset.estado = "rojo";
    }

    function setBotonVerde(texto) {
        submitBtn.textContent = texto;
        submitBtn.style.backgroundColor = "#06D6A0";
        submitBtn.dataset.estado = "verde";
    }

    function actualizarBotonSegunCodigo() {
        const codigo = codigoInput.value.trim();
        if (!codigo) {
            setBotonAzul();
        } else {
            setBotonRojo();
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

        const botonEsAzul = submitBtn.dataset.estado === "azul";

        if (botonEsAzul) {
            e.preventDefault();
            limpiarError();

            let errores = false;

            const obligatorios = [
                nombreInput, mayoreoInput, menudeoInput,
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
            nombreInput, mayoreoInput, menudeoInput,
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

        const formData = new FormData(form);
        console.group("📦 nuevo_producto — payload enviado");
        for (const [key, val] of formData.entries()) {
            if (val instanceof File) {
                console.log(`${key}: [File] ${val.name} (${(val.size/1024).toFixed(1)}KB, ${val.type})`);
            } else {
                console.log(`${key}: ${val}`);
            }
        }
        console.log("action →", form.action || window.location.href);
        console.groupEnd();

        const fetchPromise = fetch(form.action || window.location.href, {
            method: "POST",
            body: formData,
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
                setBotonRojo();
                return;
            }

            form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;
            form.method = "post";

            if (!inventario_existe) {
                setBotonVerde("Crear inventario en esta ubicación");
            } else {
                setBotonVerde("Agregar inventario");
            }

        } catch (err) {
            console.error("Error verificando inventario:", err);
        }
    }

    return { verificarInventario };
}