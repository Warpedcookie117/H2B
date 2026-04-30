// ============================================
// ATRIBUTOS DINÁMICOS
// ============================================
//
// - No destruye el input file
// - No usa innerHTML = ""
// - Usa clases propias (atributo-input, atributo-wrapper)
//   en lugar de form-control para no depender de forms.css
// - Muestra/oculta el banner de atributos
// ============================================

export function initAtributos({ atributosContainer }) {

    const banner = document.getElementById("atributos-banner");

    // ============================================
    // LIMPIAR CONTENEDOR SIN TOCAR EL INPUT FILE
    // ============================================
    function limpiarContenedorSeguro(container) {
        while (container.firstChild) {
            container.removeChild(container.firstChild);
        }
    }

    // ============================================
    // MOSTRAR / OCULTAR BANNER
    // ============================================
    function mostrarBanner(visible) {
        if (!banner) return;
        banner.style.display = visible ? "block" : "none";
    }

    // ============================================
    // MOSTRAR ATRIBUTOS DE UNA SUBCATEGORÍA
    // ============================================
    function mostrarAtributosDeSubcategoria(subId) {

        limpiarContenedorSeguro(atributosContainer);

        const allAtributos = document.querySelectorAll("#atributos-data div");
        let hayAtributos = false;

        allAtributos.forEach(attr => {
            if (String(attr.dataset.categoria) !== String(subId)) return;

            hayAtributos = true;

            const attrId    = attr.dataset.id;
            const fieldName = `atributo_${attrId}`;
            const tipo      = attr.dataset.tipo.toLowerCase();
            const valoresRaw = attr.dataset.valores || "";
            const valores    = valoresRaw ? valoresRaw.split("||") : [];

            // WRAPPER EXTERNO
            const outer = document.createElement("div");
            outer.style.marginBottom = "0.25rem";

            // LABEL
            const label = document.createElement("label");
            label.className = "atributo-label";
            label.textContent = attr.dataset.nombre;
            label.setAttribute("for", fieldName);

            // WRAPPER DEL INPUT (borde y sombra 90s)
            const wrapper = document.createElement("div");
            wrapper.className = "atributo-wrapper";

            // INPUT
            const input = document.createElement("input");
            input.type          = "text";
            input.name          = fieldName;
            input.id            = fieldName;
            input.className     = "atributo-input";
            input.dataset.atributoId = attrId;
            input.autocomplete  = "new-password";
            input.placeholder   = "Dejar vacío si no aplica";

            // Validación numérica
            if (tipo === "numero") {
                input.addEventListener("input", () => {
                    input.value = input.value.replace(/[^0-9.]/g, "");
                    if (input.value.startsWith(".")) input.value = "";
                });
            }

            // Datalist si hay valores sugeridos
            if (valores.length > 0) {
                const datalist = document.createElement("datalist");
                datalist.id = `${fieldName}_datalist`;
                valores.forEach(v => {
                    const opt = document.createElement("option");
                    opt.value = v;
                    datalist.appendChild(opt);
                });
                input.setAttribute("list", datalist.id);
                wrapper.appendChild(datalist);
            }

            // Valor previo si Django recargó con errores
            const oldValue = document.querySelector(`[name="${fieldName}"]`)?.value;
            if (oldValue) input.value = oldValue;

            wrapper.appendChild(input);
            outer.appendChild(label);
            outer.appendChild(wrapper);

            // Error previo
            const errorElement = document.querySelector(`#error_${fieldName}`);
            if (errorElement) {
                const errorText = document.createElement("p");
                errorText.className = "text-xs font-black text-[#FF006E] uppercase tracking-widest mt-1";
                errorText.textContent = "⚠️ " + errorElement.textContent;
                outer.appendChild(errorText);
            }

            atributosContainer.appendChild(outer);
        });

        mostrarBanner(hayAtributos);
    }

    // ============================================
    // MODO READ-ONLY PARA PRODUCTO EXISTENTE
    // ============================================
    function renderAtributosReadOnly(atributos = []) {

        limpiarContenedorSeguro(atributosContainer);

        if (atributos.length === 0) {
            mostrarBanner(false);
            return;
        }

        mostrarBanner(true);

        atributos.forEach((attr) => {
            const outer = document.createElement("div");
            outer.className = "space-y-1";

            const label = document.createElement("label");
            label.className = "atributo-label";
            label.textContent = attr.nombre;

            const wrapper = document.createElement("div");
            wrapper.className = "atributo-wrapper";
            wrapper.style.opacity = "0.7";

            const input = document.createElement("input");
            input.type      = "text";
            input.className = "atributo-input";
            input.value     = attr.valor || "N/A";
            input.readOnly  = true;
            input.style.cursor = "default";
            input.style.background = "#f3f4f6";

            wrapper.appendChild(input);
            outer.appendChild(label);
            outer.appendChild(wrapper);
            atributosContainer.appendChild(outer);
        });
    }

    return {
        mostrarAtributosDeSubcategoria,
        renderAtributosReadOnly
    };
}