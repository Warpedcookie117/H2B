// ============================
// CATEGORÍAS Y SUBCATEGORÍAS
// ============================
//
// Responsabilidad ÚNICA:
// Manejar selects dependientes (padre → subcategoría)
// No toca atributos, inventario, AJAX ni producto existente.
//

export function initCategorias({
    categoriaPadreSelect,
    subcategoriaSelect,
    onSubcategoriaCargada = null
}) {

    // Listener: cuando el usuario cambia la categoría padre
    categoriaPadreSelect.addEventListener("change", () => {
        const padreId = categoriaPadreSelect.value;
        cargarSubcategorias(padreId);
    });

    // ⭐ Listener: cuando el usuario cambia la SUBCATEGORÍA manualmente
    subcategoriaSelect.addEventListener("change", () => {
        const subId = subcategoriaSelect.value;

        if (onSubcategoriaCargada) {
            onSubcategoriaCargada(subId);
        }
    });

    // ----------------------------
    // FUNCIÓN PRINCIPAL
    // ----------------------------
    function cargarSubcategorias(padreId, subId = null) {
        // Limpiar select
        subcategoriaSelect.innerHTML = "";

        // Leer subcategorías desde el DOM oculto
        const subData = document.querySelectorAll("#subcategorias-data div");

        subData.forEach((sub) => {
            if (String(sub.dataset.padre) === String(padreId)) {
                const opt = document.createElement("option");
                opt.value = sub.dataset.id;
                opt.textContent = sub.dataset.nombre;
                subcategoriaSelect.appendChild(opt);
            }
        });

        // Si viene desde producto existente → seleccionar subcategoría correcta
        if (subId) {
            subcategoriaSelect.value = String(subId);
        }

        // Avisar al orquestador que ya se cargaron las subcategorías
        if (onSubcategoriaCargada) {
            onSubcategoriaCargada(subcategoriaSelect.value);
        }
    }

    // Exponer función para que otros módulos puedan usarla
    return {
        cargarSubcategorias
    };
}