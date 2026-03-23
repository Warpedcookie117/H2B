// ===============================
// CSRF
// ===============================
function getCSRFToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// ===============================
// ABRIR / CERRAR MODAL
// ===============================

function abrirModalUbicacion(ubicacion_id=null) {
    let url = ubicacion_id
        ? `/inventario/ubicaciones/editar/${ubicacion_id}/`
        : `/inventario/ubicaciones/nueva/`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            document.getElementById("modalUbicacionContent").innerHTML = data.html;
            document.getElementById("modalUbicacion").classList.remove("hidden");
        })
        .catch(() => showError("No se pudo cargar el formulario"));
}

function cerrarModalUbicacion() {
    document.getElementById("modalUbicacion").classList.add("hidden");
}


// ===============================
// MENSAJES
// ===============================

function showSuccess(msg) {
    let box = document.getElementById("msgSuccess");
    box.innerText = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 3000);
}

function showError(msg) {
    let box = document.getElementById("msgError");
    box.innerText = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 4000);
}


// ===============================
// GUARDAR UBICACIÓN
// ===============================

function guardarUbicacion(ubicacion_id=null) {
    const form = document.getElementById("formUbicacion");
    const formData = new FormData(form);

    let url = ubicacion_id
        ? `/inventario/ubicaciones/editar/${ubicacion_id}/`
        : `/inventario/ubicaciones/nueva/`;

    fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken()
        },
        body: formData
    })
    .then(r => r.json())
    .then(data => {

        if (data.success) {

            // Si es nueva ubicación → redirigir al inventario de esa ubicación
            if (!ubicacion_id) {
                window.location.href = `/inventario/ubicacion/${data.id}/`;
                return;
            }

            // Si es edición → solo actualizar cards
            actualizarCardsUbicaciones(data.ubicaciones);
            cerrarModalUbicacion();
            showSuccess("Ubicación actualizada correctamente");

        } else {
            document.getElementById("modalUbicacionContent").innerHTML = data.html;
            showError("Corrige los errores del formulario");
        }
    })
    .catch(() => showError("Error al guardar la ubicación"));
}


// ===============================
// MODAL CONFIRMAR ELIMINACIÓN
// ===============================

let ubicacionAEliminar = null;

function confirmarEliminarUbicacion(id) {
    ubicacionAEliminar = id;
    document.getElementById("modalConfirmarUbicacion").classList.remove("hidden");
}

function cerrarConfirmarUbicacion() {
    document.getElementById("modalConfirmarUbicacion").classList.add("hidden");
    ubicacionAEliminar = null;
}

document.getElementById("btnConfirmarEliminarUbicacion").onclick = function () {
    eliminarUbicacion(ubicacionAEliminar);
    cerrarConfirmarUbicacion();
};


// ===============================
// ELIMINAR UBICACIÓN
// ===============================

function eliminarUbicacion(id) {
    fetch(`/inventario/ubicaciones/eliminar/${id}/`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                actualizarCardsUbicaciones(data.ubicaciones);
                showSuccess("Ubicación eliminada correctamente");

                // 🔥 Recargar para actualizar sidebar
                setTimeout(() => window.location.reload(), 800);

            } else {
                showError("No se pudo eliminar la ubicación");
            }
        })
        .catch(() => showError("Error de conexión al eliminar ubicación"));
}


// ===============================
// ACTUALIZAR CARDS
// ===============================

function actualizarCardsUbicaciones(lista) {
    let grid = document.querySelector(".grid");

    grid.innerHTML = "";

    lista.forEach(u => {
        grid.innerHTML += `
            <div id="card-${u.id}" class="p-4 border rounded bg-white shadow-sm">

                <h3 class="font-semibold text-lg">${u.nombre}</h3>
                <p class="text-gray-600 text-sm">${u.direccion}</p>

                <div class="flex gap-2 mt-3">
                    <button class="bg-blue-600 text-white px-3 py-1 rounded text-xs"
                            onclick="abrirModalUbicacion(${u.id})">
                        Editar
                    </button>

                    <button class="bg-red-600 text-white px-3 py-1 rounded text-xs"
                            onclick="confirmarEliminarUbicacion(${u.id})">
                        Eliminar
                    </button>
                </div>

            </div>
        `;
    });
}