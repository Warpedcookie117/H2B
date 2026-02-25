// ===============================
// UTILIDADES
// ===============================

function showSuccess(msg) {
    const box = document.getElementById("msgSuccess");
    box.textContent = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 2500);
}

function showError(msg) {
    const box = document.getElementById("msgError");
    box.textContent = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 2500);
}

function openModal(id) {
    document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
    document.getElementById(id).classList.add("hidden");
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

    fetch(form.action, {
        method: "POST",
        body: new FormData(form)
    })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalCategoria");
                showSuccess(data.msg);
                location.reload();
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

    fetch(form.action, {
        method: "POST",
        body: new FormData(form)
    })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalSubcategoria");
                showSuccess(data.msg);
                location.reload();
            } else {
                showError(data.msg);
            }
        });
}

// ===============================
// MODAL CONFIRMAR ELIMINACIÓN
// ===============================

let deleteInfo = { tipo: null, id: null };

function confirmarEliminarSub(padreId, subId) {
    deleteInfo = { tipo: "sub", id: subId };
    openModal("modalConfirmar");
}

function confirmarEliminarPadre(padreId) {
    deleteInfo = { tipo: "padre", id: padreId };
    openModal("modalConfirmar");
}

function eliminarConfirmado() {
    fetch(`/inventario/categorias/eliminar/${deleteInfo.tipo}/${deleteInfo.id}`, {
        method: "POST",
        headers: { "X-CSRFToken": getCookie("csrftoken") }
    })
        .then(res => res.json())
        .then(data => {
            if (data.ok) {
                closeModal("modalConfirmar");
                showSuccess(data.msg);
                location.reload();
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
        const cookies = document.cookie.split(";");
        for (let cookie of cookies) {
            cookie = cookie.trim();
            if (cookie.startsWith(name + "=")) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}