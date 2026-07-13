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

function showSuccess(msg) { toast("msgSuccess", msg, 2800); }
function showError(msg)   { toast("msgError",   msg, 4000); }

function toast(id, msg, duration) {
    const box = document.getElementById(id);
    box.textContent = msg;
    box.style.transition = "opacity .2s ease, transform .2s ease";
    box.style.opacity    = "0";
    box.style.transform  = "translateY(-8px)";
    box.classList.remove("hidden");
    requestAnimationFrame(() => requestAnimationFrame(() => {
        box.style.opacity   = "1";
        box.style.transform = "translateY(0)";
    }));
    clearTimeout(box._timer);
    box._timer = setTimeout(() => {
        box.style.opacity   = "0";
        box.style.transform = "translateY(-8px)";
        setTimeout(() => box.classList.add("hidden"), 220);
    }, duration);
}


// ======================================================
// RENDERIZAR LISTA DE ATRIBUTOS EN EL DOM
// ======================================================

const TIPO_DISPLAY = { texto: "Texto", numero: "Número" };

const S = {
    li:       "border:4px solid black;padding:1rem;background:#F0FFF4;display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;animation:fadeSlideIn .25s ease;",
    nombre:   "font-weight:900;color:black;font-size:1rem;text-transform:uppercase;letter-spacing:.05em;margin:0;",
    badge:    "display:inline-block;margin-top:.25rem;border:2px solid black;background:#CCFF00;color:black;font-weight:900;font-size:.65rem;text-transform:uppercase;letter-spacing:.1em;padding:.1rem .35rem;",
    acciones: "display:flex;gap:.5rem;flex-shrink:0;",
    btnEdit:  "border:4px solid black;box-shadow:3px 3px 0 0 black;background:#06D6A0;color:black;font-weight:900;font-size:.75rem;text-transform:uppercase;padding:.4rem .65rem;cursor:pointer;transition:transform .1s,box-shadow .1s;",
    btnDel:   "border:4px solid black;box-shadow:3px 3px 0 0 black;background:#FF006E;color:white;font-weight:900;font-size:.75rem;text-transform:uppercase;padding:.4rem .65rem;cursor:pointer;transition:transform .1s,box-shadow .1s;",
    hover:    "this.style.transform='translate(-2px,-2px)';this.style.boxShadow='5px 5px 0 0 black'",
    out:      "this.style.transform='';this.style.boxShadow='3px 3px 0 0 black'",
};

function renderAtributos(subcat_id, atributos) {
    const card = document.getElementById(`card-${subcat_id}`);
    if (!card) return;

    card.querySelector("ul")?.remove();
    card.querySelector(".sin-atributos")?.remove();

    if (atributos.length === 0) {
        const p = document.createElement("p");
        p.className   = "sin-atributos";
        p.style.cssText = "color:#9ca3af;font-weight:700;font-size:.875rem;border:4px dashed #e5e7eb;padding:1rem;text-align:center;";
        p.textContent = "Sin atributos todavía. Ponle, no seas flojo. 👀";
        card.appendChild(p);
        return;
    }

    const ul = document.createElement("ul");
    ul.style.cssText = "list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:.75rem;";

    atributos.forEach(a => {
        const tipoLabel = TIPO_DISPLAY[a.tipo] || a.tipo;
        const li = document.createElement("li");
        li.style.cssText = S.li;
        li.innerHTML = `
            <div style="min-width:0;flex:1;">
                <p style="${S.nombre}">${a.nombre}</p>
                <span style="${S.badge}">${tipoLabel}</span>
            </div>
            <div style="${S.acciones}">
                <button onclick="abrirModalAtributo(${subcat_id},${a.id})"
                        style="${S.btnEdit}"
                        onmouseover="${S.hover}" onmouseout="${S.out}">✏️</button>
                <button onclick="confirmarEliminar(${subcat_id},${a.id})"
                        style="${S.btnDel}"
                        onmouseover="${S.hover}" onmouseout="${S.out}">🗑️</button>
            </div>`;
        ul.appendChild(li);
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
