// ======================================================
// ABRIR / CERRAR MODAL DE ATRIBUTO
// ======================================================

function abrirModalAtributo(subcat_id, atributo_id=null) {
    let url = atributo_id
        ? `/inventario/atributo/editar/${subcat_id}/${atributo_id}/`
        : `/inventario/atributo/nuevo/${subcat_id}/`;

    fetch(url)
        .then(r => r.json())
        .then(data => {
            document.getElementById("modalAtributoContent").innerHTML = data.html;
            document.getElementById("modalAtributo").classList.remove("hidden");
        })
        .catch(() => showError("No se pudo cargar el formulario"));
}

function cerrarModalAtributo() {
    document.getElementById("modalAtributo").classList.add("hidden");
}


// ======================================================
// MENSAJES
// ======================================================

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


// ======================================================
// GUARDAR ATRIBUTO
// ======================================================

function guardarAtributo(subcat_id, atributo_id=null) {
    const form = document.getElementById("formAtributo");
    const formData = new FormData(form);

    let url = atributo_id
        ? `/inventario/atributo/editar/${subcat_id}/${atributo_id}/`
        : `/inventario/atributo/nuevo/${subcat_id}/`;

    fetch(url, {
        method: "POST",
        body: formData
    })
    .then(r => r.json())
    .then(data => {

        if (data.success) {
            let ul = document.querySelector(`#card-${subcat_id} ul`);
            ul.innerHTML = "";

            data.atributos.forEach(a => {
                ul.innerHTML += `
                    <li class="border-4 border-black p-4 bg-[#F0FFF4] flex items-center justify-between gap-4">
                        <div class="min-w-0 flex-1">
                            <p class="font-black text-black text-base uppercase tracking-wide">${a.nombre}</p>
                            <span class="inline-block mt-1 border-2 border-black bg-[#CCFF00]
                                        text-black font-black text-[10px] uppercase px-2 py-0.5">
                                ${a.tipo}
                            </span>
                        </div>
                        <div class="flex gap-2 flex-shrink-0">
                            <button onclick="abrirModalAtributo(${subcat_id}, ${a.id})"
                                    class="btn-90s bg-[#00BBF9] border-4 border-black shadow-[3px_3px_0_0_black]
                                        text-black font-black text-xs uppercase px-3 py-2">✏️</button>
                            <button onclick="confirmarEliminar(${subcat_id}, ${a.id})"
                                    class="btn-90s bg-[#FF006E] border-4 border-black shadow-[3px_3px_0_0_black]
                                        text-white font-black text-xs uppercase px-3 py-2">🗑️</button>
                        </div>
                    </li>
                `;
            });

            cerrarModalAtributo();
            showSuccess("Atributo guardado correctamente");

        } else {
            document.getElementById("modalAtributoContent").innerHTML = data.html;
            showError("Corrige los errores del formulario");
        }
    })
    .catch(() => showError("Error al guardar el atributo"));
}


// ======================================================
// MODAL DE CONFIRMACIÓN PARA ELIMINAR
// ======================================================

let atributoAEliminar = null;
let subcatAEliminar = null;

function confirmarEliminar(subcat_id, atributo_id) {
    subcatAEliminar = subcat_id;
    atributoAEliminar = atributo_id;

    document.getElementById("modalConfirmar").classList.remove("hidden");
}

function cerrarConfirmar() {
    document.getElementById("modalConfirmar").classList.add("hidden");
    subcatAEliminar = null;
    atributoAEliminar = null;
}

document.getElementById("btnConfirmarEliminar").onclick = function () {
    eliminarAtributo(subcatAEliminar, atributoAEliminar);
    cerrarConfirmar();
};


// ======================================================
// ELIMINAR ATRIBUTO (SIN ALERT, CON MODAL)
// ======================================================

function eliminarAtributo(subcat_id, atributo_id) {

    fetch(`/inventario/atributo/eliminar/${subcat_id}/${atributo_id}/`)
        .then(r => r.json())
        .then(data => {

            if (data.success) {
                let ul = document.querySelector(`#card-${subcat_id} ul`);
                ul.innerHTML = "";

                data.atributos.forEach(a => {
                    ul.innerHTML += `
                        <li class="p-2 border rounded bg-gray-50">
                            <div class="flex justify-between items-center">
                                <span class="font-semibold">${a.nombre}</span>
                                <span class="px-2 py-1 bg-gray-200 rounded text-xs">${a.tipo}</span>
                            </div>

                            <div class="flex gap-2 mt-2">
                                <button class="bg-blue-600 text-white px-3 py-1 rounded text-xs"
                                        onclick="abrirModalAtributo(${subcat_id}, ${a.id})">
                                    Editar
                                </button>

                                <button class="bg-red-600 text-white px-3 py-1 rounded text-xs"
                                        onclick="confirmarEliminar(${subcat_id}, ${a.id})">
                                    Eliminar
                                </button>
                            </div>
                        </li>
                    `;
                });

                showSuccess("Atributo eliminado correctamente");

            } else {
                showError("No se pudo eliminar el atributo");
            }
        })
        .catch(() => showError("Error de conexión al eliminar atributo"));
}