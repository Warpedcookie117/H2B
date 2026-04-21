// ======================================================
// ABRIR / CERRAR MODAL DE ATRIBUTO
// ======================================================

function abrirModalAtributo(subcat_id, atributo_id = null) {
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
// RENDERIZAR LISTA DE ATRIBUTOS EN EL DOM
// ======================================================

const TIPO_DISPLAY = { texto: "Texto", numero: "Número" };

function renderAtributos(subcat_id, atributos) {
    const card = document.getElementById(`card-${subcat_id}`);
    if (!card) return;

    // Eliminar lista o mensaje vacío existente
    const viejaLista = card.querySelector("ul");
    const viejoVacio = card.querySelector(".sin-atributos");
    if (viejaLista) viejaLista.remove();
    if (viejoVacio) viejoVacio.remove();

    if (atributos.length === 0) {
        const p = document.createElement("p");
        p.className = "sin-atributos text-gray-400 font-bold text-sm border-4 border-dashed border-gray-200 p-4 text-center";
        p.textContent = "Sin atributos todavía. Ponle, no seas flojo. 👀";
        card.appendChild(p);
        return;
    }

    const ul = document.createElement("ul");
    ul.className = "space-y-3";

    atributos.forEach(a => {
        const tipoLabel = TIPO_DISPLAY[a.tipo] || a.tipo;
        ul.innerHTML += `
            <li class="border-4 border-black p-4 bg-[#F0FFF4] flex items-center justify-between gap-4 flex-wrap">
                <div class="min-w-0 flex-1">
                    <p class="font-black text-black text-base uppercase tracking-wide">${a.nombre}</p>
                    <span class="inline-block mt-1 border-2 border-black bg-[#CCFF00]
                                 text-black font-black text-[10px] uppercase tracking-widest px-2 py-0.5">
                        ${tipoLabel}
                    </span>
                </div>
                <div class="flex gap-2 flex-shrink-0">
                    <button onclick="abrirModalAtributo(${subcat_id}, ${a.id})"
                            class="btn-90s bg-[#06D6A0] border-4 border-black shadow-[3px_3px_0_0_black]
                                   text-black font-black text-xs uppercase px-3 py-2">✏️</button>
                    <button onclick="confirmarEliminar(${subcat_id}, ${a.id})"
                            class="btn-90s bg-[#FF006E] border-4 border-black shadow-[3px_3px_0_0_black]
                                   text-white font-black text-xs uppercase px-3 py-2">🗑️</button>
                </div>
            </li>
        `;
    });

    card.appendChild(ul);
}


// ======================================================
// GUARDAR ATRIBUTO
// ======================================================

function guardarAtributo(subcat_id, atributo_id = null) {
    const form = document.getElementById("formAtributo");
    const formData = new FormData(form);

    let url = atributo_id
        ? `/inventario/atributo/editar/${subcat_id}/${atributo_id}/`
        : `/inventario/atributo/nuevo/${subcat_id}/`;

    fetch(url, { method: "POST", body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                renderAtributos(subcat_id, data.atributos);
                cerrarModalAtributo();
                showSuccess("Atributo guardado correctamente");
            } else if (data.error) {
                showError(data.error);
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
// ELIMINAR ATRIBUTO
// ======================================================

function eliminarAtributo(subcat_id, atributo_id) {
    fetch(`/inventario/atributo/eliminar/${subcat_id}/${atributo_id}/`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                renderAtributos(subcat_id, data.atributos);
                showSuccess("Atributo eliminado correctamente");
            } else {
                showError("No se pudo eliminar el atributo");
            }
        })
        .catch(() => showError("Error de conexión al eliminar atributo"));
}
