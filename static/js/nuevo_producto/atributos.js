// ============================================
// ATRIBUTOS DINÁMICOS
// ============================================
//
// - No destruye el input file
// - No usa innerHTML = ""
// - Usa clases propias (atributo-input, atributo-wrapper)
//   en lugar de form-control para no depender de forms.css
// - Muestra/oculta el banner de atributos
// - Autocomplete custom (contains, no prefix-only) para iOS
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
    // AUTOCOMPLETE CUSTOM (contains, cross-browser)
    // ============================================
    function attachAutocomplete(input, wrapper, valores) {
        if (!valores || valores.length === 0) return;

        // Dropdown container
        const dropdown = document.createElement("div");
        dropdown.className = "atributo-dropdown";
        dropdown.style.cssText = [
            "position:absolute",
            "z-index:9999",
            "background:#fff",
            "border:3px solid #000",
            "box-shadow:4px 4px 0 #000",
            "max-height:180px",
            "overflow-y:auto",
            "display:none",
            "left:0",
            "right:0",
            "top:100%",
        ].join(";");

        wrapper.style.position = "relative";
        wrapper.appendChild(dropdown);

        function renderOpciones(filtro) {
            while (dropdown.firstChild) dropdown.removeChild(dropdown.firstChild);

            const q = (filtro || "").toLowerCase().trim();
            const matches = q
                ? valores.filter(v => v.toLowerCase().includes(q))
                : valores;

            if (matches.length === 0) {
                dropdown.style.display = "none";
                return;
            }

            matches.forEach(v => {
                const item = document.createElement("div");
                item.textContent = v;
                item.style.cssText = [
                    "padding:8px 12px",
                    "cursor:pointer",
                    "font-weight:600",
                    "font-size:0.85rem",
                    "border-bottom:1px solid #e5e7eb",
                ].join(";");
                item.addEventListener("mousedown", (e) => {
                    e.preventDefault();
                    input.value = v;
                    dropdown.style.display = "none";
                });
                item.addEventListener("touchend", (e) => {
                    e.preventDefault();
                    input.value = v;
                    dropdown.style.display = "none";
                    input.blur();
                });
                dropdown.appendChild(item);
            });

            dropdown.style.display = "block";
        }

        input.addEventListener("focus", () => renderOpciones(input.value));
        input.addEventListener("input", () => renderOpciones(input.value));
        input.addEventListener("blur", () => {
            setTimeout(() => { dropdown.style.display = "none"; }, 150);
        });
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
            input.setAttribute("autocomplete", "off");
            input.placeholder   = "Dejar vacío si no aplica";

            // Validación numérica
            if (tipo === "numero") {
                input.addEventListener("input", () => {
                    input.value = input.value.replace(/[^0-9.]/g, "");
                    if (input.value.startsWith(".")) input.value = "";
                });
            }

            // Valor previo si Django recargó con errores
            const oldValue = document.querySelector(`[name="${fieldName}"]`)?.value;
            if (oldValue) input.value = oldValue;

            wrapper.appendChild(input);

            // Autocomplete custom — debe ir DESPUÉS de appendChild para que wrapper sea el padre
            attachAutocomplete(input, wrapper, valores);
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
