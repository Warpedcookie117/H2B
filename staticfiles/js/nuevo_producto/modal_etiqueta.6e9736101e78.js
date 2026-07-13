// ============================================
// MODAL DE SELECCIÓN DE ETIQUETA
// ============================================
//
// Responsabilidad ÚNICA:
// - Permitir elegir tamaño de etiqueta
// - Guardar tamaño en un hidden
// - Bloquear el campo código (solo si estaba vacío)
// - NO generar código
// - NO enviar el form
//

document.addEventListener("DOMContentLoaded", () => {

    const modal = document.getElementById("modal-etiqueta");

    // ============================
    // 1. MANEJAR CLIC EN LOS BOTONES DE TAMAÑO
    // ============================
    document.querySelectorAll(".btn-etiqueta").forEach(btn => {
        btn.addEventListener("click", function () {

            const tamaño = this.dataset.tipo;

            // ============================
            // 2. GUARDAR TAMAÑO EN HIDDEN
            // ============================
            const hidden = document.querySelector("#id_tamano_etiqueta");
            if (hidden) hidden.value = tamaño;

            // ============================
            // 3. BLOQUEAR CAMPO CÓDIGO (solo si estaba vacío)
            // ============================
            const codigoInput = document.querySelector("#id_codigo_barras");
            if (codigoInput && !codigoInput.value.trim()) {
                codigoInput.setAttribute("readonly", "true");
                codigoInput.classList.add("bg-gray-100", "cursor-not-allowed");
            }

            // ============================
            // 4. CERRAR MODAL
            // ============================
            modal.close();

            // ============================
            // 5. CAMBIAR BOTÓN A ROJO
            // ============================
            const submitBtn = document.getElementById("submit-btn");
            if (submitBtn) {
                submitBtn.textContent = "Registrar producto";
                submitBtn.style.backgroundColor = "#FF006E";
                submitBtn.dataset.estado = "rojo";
            }

            // *** IMPORTANTE ***
            // NO enviar el form aquí.
            // El usuario debe presionar el botón rojo.
        });
    });

});