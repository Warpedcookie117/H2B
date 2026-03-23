// -------------------------------------------------------------
// DASHBOARD SUCURSAL — CREAR CAJA (MODAL + AJAX)
// -------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {

    const modal = document.getElementById("modalCrearCaja");
    const modalContent = document.getElementById("modalCrearCajaContent");
    const btnAbrir = document.getElementById("btnAbrirModalCrearCaja");
    const listaCajas = document.getElementById("listaCajas");
    const noCajas = document.getElementById("noCajas");

    // -------------------------------------------------------------
    // ABRIR MODAL → CARGAR FORM DJANGO POR AJAX
    // -------------------------------------------------------------
    if (btnAbrir) {
        btnAbrir.addEventListener("click", () => {

            const urlModal = btnAbrir.dataset.urlModal;

            fetch(urlModal)
                .then(r => r.json())
                .then(data => {
                    modalContent.innerHTML = data.html;
                    modal.classList.remove("hidden");

                    // Conectar botones del modal recién cargado
                    conectarEventosModal(btnAbrir.dataset.urlCrear);
                });
        });
    }

    // -------------------------------------------------------------
    // FUNCIÓN PARA CONECTAR EVENTOS DEL MODAL CARGADO
    // -------------------------------------------------------------
    function conectarEventosModal(urlCrear) {

        const btnGuardar = document.getElementById("modalCrearCajaGuardar");
        const btnCancelar = document.getElementById("modalCrearCajaCancelar");
        const form = document.getElementById("formCrearCaja");

        // Cerrar modal
        btnCancelar.addEventListener("click", () => {
            modal.classList.add("hidden");
        });

        // Guardar caja
        btnGuardar.addEventListener("click", () => {

            const formData = new FormData(form);

            fetch(urlCrear, {
                method: "POST",
                body: formData   // 🔥 CSRF VIENE AQUÍ AUTOMÁTICO
            })
            .then(r => r.json())
            .then(data => {

                if (data.error) {
                    // Volver a renderizar el form con errores
                    modalContent.innerHTML = data.html;
                    conectarEventosModal(urlCrear);
                    return;
                }

                // Si existía el mensaje "no hay cajas", lo quitamos
                if (noCajas) noCajas.remove();

                // Crear nuevo elemento en la lista
                const li = document.createElement("li");
                li.id = `caja-${data.id}`;
                li.className = "flex items-center justify-between p-3 border-2 border-black bg-white text-black";
                li.style.boxShadow = "3px 3px 0 0 black";

                li.innerHTML = `
                    <span class="font-bold">${data.nombre}</span>
                    <button
                        class="btn-entrar-caja px-4 py-1 font-black border-2 border-black text-white"
                        style="background: #FF0066; box-shadow: 3px 3px 0 0 black;"
                        data-caja-id="${data.id}"
                        data-caja-nombre="${data.nombre}">
                        Entrar
                    </button>
                `;

                listaCajas.appendChild(li);

                // Cerrar modal
                modal.classList.add("hidden");
            });
        });
    }

});