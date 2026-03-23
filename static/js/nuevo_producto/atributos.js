// ============================================
// ATRIBUTOS DINÁMICOS (VERSIÓN SEGURA)
// ============================================
//
// - No destruye el input file
// - No usa innerHTML = ""
// - Limpia solo los hijos del contenedor
// - Mantiene fuzzy, datalist y validaciones
// ============================================

export function initAtributos({ atributosContainer }) {

    // ============================================
    // 🔥 FUNCIÓN SEGURA PARA LIMPIAR CONTENEDOR
    // ============================================
    function limpiarContenedorSeguro(container) {
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }

    // ============================================
    // MOSTRAR ATRIBUTOS DE UNA SUBCATEGORÍA
    // ============================================
    function mostrarAtributosDeSubcategoria(subId) {

        // 🔥 YA NO BORRA EL INPUT FILE
        limpiarContenedorSeguro(atributosContainer);

        const allAtributos = document.querySelectorAll("#atributos-data div");

        allAtributos.forEach(attr => {
            if (String(attr.dataset.categoria) === String(subId)) {

                const attrId = attr.dataset.id;
                const fieldName = `atributo_${attrId}`;

                const wrapper = document.createElement("div");
                wrapper.className = "mb-3";

                const label = document.createElement("label");
                label.className = "block font-semibold mb-1";
                label.textContent = attr.dataset.nombre;

                const valoresRaw = attr.dataset.valores || "";
                const valores = valoresRaw ? valoresRaw.split("||") : [];

                const tipo = attr.dataset.tipo.toLowerCase();

                let input;

                // ============================================
                // 1) NÚMEROS → INPUT + DATALIST
                // ============================================
                if (tipo === "numero" && valores.length > 0) {
                    input = document.createElement("input");
                    input.type = "text";
                    input.name = fieldName;
                    input.className = "form-control";
                    input.dataset.atributoId = attrId;
                    input.autocomplete = "new-password";

                    input.addEventListener("input", () => {
                        input.value = input.value.replace(/[^0-9.]/g, "");
                        if (input.value.startsWith(".")) input.value = "";
                    });

                    const datalist = document.createElement("datalist");
                    datalist.id = `${fieldName}_datalist`;

                    valores.forEach(v => {
                        const opt = document.createElement("option");
                        opt.value = v;
                        datalist.appendChild(opt);
                    });

                    input.setAttribute("list", datalist.id);
                    wrapper.appendChild(datalist);

                // ============================================
                // 2) TEXTO CON VALORES → INPUT + DATALIST + FUZZY
                // ============================================
                } else if (tipo === "texto" && valores.length > 0) {
                    input = document.createElement("input");
                    input.type = "text";
                    input.name = fieldName;
                    input.className = "form-control";
                    input.dataset.atributoId = attrId;
                    input.autocomplete = "new-password";

                    const datalist = document.createElement("datalist");
                    datalist.id = `${fieldName}_datalist`;

                    valores.forEach(v => {
                        const opt = document.createElement("option");
                        opt.value = v;
                        datalist.appendChild(opt);
                    });

                    input.setAttribute("list", datalist.id);
                    wrapper.appendChild(datalist);

                // ============================================
                // 3) TEXTO SIN VALORES → INPUT SIMPLE
                // ============================================
                } else {
                    input = document.createElement("input");
                    input.type = "text";
                    input.name = fieldName;
                    input.className = "form-control";
                    input.dataset.atributoId = attrId;
                    input.autocomplete = "new-password";
                }

                // ============================================
                // 🔥 VALOR PREVIO (si Django recargó con errores)
                // ============================================
                const oldValue = document.querySelector(`[name="${fieldName}"]`)?.value;
                if (oldValue) input.value = oldValue;

                // ============================================
                // 🔥 ERRORES PREVIOS
                // ============================================
                const errorElement = document.querySelector(`#error_${fieldName}`);
                if (errorElement) {
                    input.classList.add("border-red-500");
                }

                wrapper.appendChild(label);
                wrapper.appendChild(input);

                if (errorElement) {
                    const errorText = document.createElement("p");
                    errorText.className = "text-red-600 text-sm mt-1";
                    errorText.textContent = errorElement.textContent;
                    wrapper.appendChild(errorText);
                }

                atributosContainer.appendChild(wrapper);
            }
        });
    }

    // ============================================
    // MODO READ-ONLY PARA PRODUCTO EXISTENTE
    // ============================================
    function renderAtributosReadOnly(atributos = []) {

        limpiarContenedorSeguro(atributosContainer);

        atributos.forEach((attr) => {
            const wrapper = document.createElement("div");
            wrapper.className = "mb-2";

            const label = document.createElement("label");
            label.className = "block font-semibold mb-1";
            label.textContent = attr.nombre;

            const input = document.createElement("input");
            input.type = "text";
            input.className = "form-control bg-gray-100";
            input.value = attr.valor || "";
            input.readOnly = true;

            wrapper.appendChild(label);
            wrapper.appendChild(input);
            atributosContainer.appendChild(wrapper);
        });
    }

    return {
        mostrarAtributosDeSubcategoria,
        renderAtributosReadOnly
    };
}