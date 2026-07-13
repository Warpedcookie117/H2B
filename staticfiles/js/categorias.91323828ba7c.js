// ===============================
// TOAST
// ===============================

function showSuccess(msg) {
    toast("msgSuccess", msg);
}
function showError(msg) {
    toast("msgError", msg);
}
function toast(id, msg) {
    const box = document.getElementById(id);
    box.textContent = msg;
    box.style.transition = "opacity .2s ease, transform .2s ease";
    box.style.opacity    = "0";
    box.style.transform  = "translateY(-8px)";
    box.classList.remove("hidden");
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            box.style.opacity   = "1";
            box.style.transform = "translateY(0)";
        });
    });
    clearTimeout(box._timer);
    box._timer = setTimeout(() => {
        box.style.opacity   = "0";
        box.style.transform = "translateY(-8px)";
        setTimeout(() => box.classList.add("hidden"), 220);
    }, 2800);
}


// ===============================
// MODALES
// ===============================

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}
function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
}


// ===============================
// ACTUALIZAR LISTA SIN RELOAD
// ===============================

async function refrescarCategorias() {
    const lista = document.getElementById("lista-categorias");
    if (!lista) return;

    // Guardar qué acordeones están abiertos
    const abiertos = new Set(
        [...lista.querySelectorAll(".accordion-body.open")].map(el => el.id)
    );

    lista.style.opacity   = "0";
    lista.style.transform = "translateY(-6px)";

    const r    = await fetch(window.location.href);
    const html = await r.text();
    const doc  = new DOMParser().parseFromString(html, "text/html");
    const nueva = doc.getElementById("lista-categorias");
    if (nueva) lista.innerHTML = nueva.innerHTML;

    // Restaurar acordeones que estaban abiertos
    abiertos.forEach(id => {
        const body = document.getElementById(id);
        if (!body) return;
        body.classList.add("open");
        // El chevron tiene id chev-X donde X es el número del accordion acc-X
        const chev = document.getElementById(id.replace("acc-", "chev-"));
        if (chev) chev.classList.add("open");
    });

    requestAnimationFrame(() => requestAnimationFrame(() => {
        lista.style.opacity   = "1";
        lista.style.transform = "translateY(0)";
    }));
}


// ===============================
// MODAL CATEGORÍA PADRE
// ===============================

function abrirModalCategoria(categoriaId = null) {
    openModal("modalCategoria");
    fetch(`/inventario/categorias/modal-categoria/${categoriaId || ""}`)
        .then(res => res.text())
        .then(html => {
            document.getElementById("modalCategoriaContent").innerHTML = html;
        });
}

function enviarCategoria(event) {
    event.preventDefault();
    const form = event.target;
    fetch(form.action, { method: "POST", body: new FormData(form) })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalCategoria");
                showSuccess(data.msg);
                refrescarCategorias();
            } else {
                showError(data.msg);
            }
        });
}


// ===============================
// MODAL SUBCATEGORÍA
// ===============================

function abrirModalSubcategoria(padreId, subId = null) {
    openModal("modalSubcategoria");
    fetch(`/inventario/categorias/modal-subcategoria/${padreId}/${subId || ""}`)
        .then(res => res.text())
        .then(html => {
            document.getElementById("modalSubcategoriaContent").innerHTML = html;
        });
}

function enviarSubcategoria(event) {
    event.preventDefault();
    const form = event.target;
    fetch(form.action, { method: "POST", body: new FormData(form) })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalSubcategoria");
                showSuccess(data.msg);
                refrescarCategorias();
            } else {
                showError(data.msg);
            }
        });
}


// ===============================
// ELIMINAR
// ===============================

let deleteInfo = { tipo: null, id: null };

function confirmarEliminarSub(_padreId, subId) {
    deleteInfo = { tipo: "sub", id: subId };
    openModal("modalConfirmar");
}
function confirmarEliminarPadre(padreId) {
    deleteInfo = { tipo: "padre", id: padreId };
    openModal("modalConfirmar");
}

function eliminarConfirmado() {
    fetch(`/inventario/categorias/eliminar/${deleteInfo.tipo}/${deleteInfo.id}/`, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") }
    })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalConfirmar");
                showSuccess(data.msg);
                refrescarCategorias();
            } else {
                showError(data.msg);
            }
        });
}

function cerrarConfirmar() {
    closeModal("modalConfirmar");
}


// ===============================
// CSRF
// ===============================

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== "") {
        for (let cookie of document.cookie.split(";")) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
