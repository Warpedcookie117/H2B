export function initAtributos({ atributosContainer }) {

    /**
     * Renderiza los atributos dinámicos de una subcategoría.
     * - Muestra valores previos si existen (Django los manda en el form)
     * - Muestra errores si Django los generó
     */
    function mostrarAtributosDeSubcategoria(subId) {
        atributosContainer.innerHTML = "";

        const allAtributos = document.querySelectorAll("#atributos-data div");

        allAtributos.forEach(attr => {
            if (String(attr.dataset.categoria) === String(subId)) {

                const attrId = attr.dataset.id;
                const fieldName = `atributo_${attrId}`;

                // Crear wrapper
                const wrapper = document.createElement("div");
                wrapper.className = "mb-3";

                // Label
                const label = document.createElement("label");
                label.className = "block font-semibold mb-1";
                label.textContent = attr.dataset.nombre;

                // Input
                const input = document.createElement("input");
                input.type = "text";
                input.name = fieldName;
                input.className = "form-control";

                // Recuperar valor previo del form (si Django recargó con errores)
                const oldValue = document.querySelector(`[name="${fieldName}"]`)?.value;
                if (oldValue) input.value = oldValue;

                // Recuperar error del form (si Django lo generó)
                const errorElement = document.querySelector(`#error_${fieldName}`);
                if (errorElement) {
                    input.classList.add("border-red-500");
                }

                wrapper.appendChild(label);
                wrapper.appendChild(input);

                // Mostrar error debajo del input
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

    /**
     * Renderiza atributos en modo read-only (producto existente)
     */
    function renderAtributosReadOnly(atributos = []) {
        atributosContainer.innerHTML = "";

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