// ============================================
// Fuzzy en vivo para atributos dinámicos
// ============================================
//
// SOLO se activa en atributos de TEXTO SIN datalist.
// NO se activa en atributos numéricos.
// NO se activa en catálogo.
// NO duplica sugerencias.
// ============================================

document.addEventListener("DOMContentLoaded", () => {

    const contenedor = document.getElementById("atributos-container");
    if (!contenedor) return;

    const observer = new MutationObserver(() => {
        activarFuzzyEnInputs();
    });

    observer.observe(contenedor, {
        childList: true,
        subtree: true
    });

    activarFuzzyEnInputs();
});


// ============================================
// FUNCIÓN PRINCIPAL
// ============================================
function activarFuzzyEnInputs() {

    const inputs = document.querySelectorAll(
        '#atributos-container input[type="text"]:not([data-fuzzy-ready])'
    );

    inputs.forEach(input => {

        const match = input.name.match(/^atributo_(\d+)$/);
        if (!match) return;

        const atributoId = match[1];

        // ============================================
        // 🔥 DETECTAR SI ESTE INPUT TIENE DATALIST
        // ============================================
        const tieneDatalist = input.hasAttribute("list");

        // ============================================
        // 🔥 SI TIENE DATALIST → NO ACTIVAR FUZZY
        // ============================================
        if (tieneDatalist) {
            input.dataset.fuzzyReady = "skip";
            return;
        }

        // ============================================
        // 🔥 SI ES CATÁLOGO → NO ACTIVAR FUZZY
        // ============================================
        const nombre = input.previousSibling?.textContent?.trim().toLowerCase() || "";
        const esCatalogo = ["marca", "color", "material", "modelo"].includes(nombre);

        if (esCatalogo) {
            input.dataset.fuzzyReady = "skip";
            return;
        }

        // ============================================
        // 🔥 SI ES NÚMERO → NO ACTIVAR FUZZY
        // ============================================
        const tipo = document.querySelector(`#atributos-data div[data-id="${atributoId}"]`)?.dataset.tipo;
        if (tipo === "numero") {
            input.dataset.fuzzyReady = "skip";
            return;
        }

        // ============================================
        // 🔥 ACTIVAR FUZZY SOLO EN TEXTO SIN DATALIST
        // ============================================
        input.dataset.fuzzyReady = "1";

        const wrapper = input.parentNode;
        wrapper.style.position = "relative";

        const dropdown = document.createElement("div");
        dropdown.classList.add("fuzzy-dropdown");
        dropdown.style.position = "absolute";
        dropdown.style.top = "100%";
        dropdown.style.left = "0";
        dropdown.style.right = "0";
        dropdown.style.background = "white";
        dropdown.style.border = "1px solid #ddd";
        dropdown.style.zIndex = "50";
        dropdown.style.maxHeight = "150px";
        dropdown.style.overflowY = "auto";
        dropdown.style.display = "none";
        wrapper.appendChild(dropdown);

        input.addEventListener("input", () => {
            const q = input.value.trim();

            if (q.length < 2) {
                dropdown.style.display = "none";
                dropdown.innerHTML = "";
                return;
            }

            fetch(`/inventario/fuzzy/${atributoId}/?q=` + encodeURIComponent(q))
                .then(r => r.json())
                .then(data => {
                    dropdown.innerHTML = "";

                    if (!data.results || data.results.length === 0) {
                        dropdown.style.display = "none";
                        return;
                    }

                    data.results.forEach(item => {
                        const option = document.createElement("div");
                        option.classList.add("fuzzy-option");
                        option.textContent = item.valor;

                        option.style.padding = "6px 10px";
                        option.style.cursor = "pointer";

                        option.addEventListener("mouseover", () => {
                            option.style.background = "#f0f0f0";
                        });

                        option.addEventListener("mouseout", () => {
                            option.style.background = "white";
                        });

                        option.addEventListener("click", () => {
                            input.value = item.valor;
                            dropdown.style.display = "none";
                        });

                        dropdown.appendChild(option);
                    });

                    dropdown.style.display = "block";
                })
                .catch(err => {
                    console.error("Error en fuzzy:", err);
                });
        });

        input.addEventListener("blur", () => {
            setTimeout(() => {
                dropdown.style.display = "none";
            }, 200);
        });
    });
}