/* ============================================================
   SISTEMA CENTRALIZADO DE MODALES
   ============================================================ */

function abrirModal(modalId) {
    const modal   = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) {
        console.error("❌ Modal no encontrado:", modalId);
        return;
    }

    const errorBox = modal.querySelector(".modal-error");
    if (errorBox) {
        errorBox.innerHTML = "";
        errorBox.classList.add("hidden");
    }

    modal.classList.remove("hidden");

    requestAnimationFrame(() => {
        content.classList.remove("opacity-0", "scale-95");
        content.classList.add("opacity-100", "scale-100");
    });

    document.addEventListener("keydown", cerrarConEsc);
    modal.addEventListener("click", cerrarClickFuera);
}

function cerrarModal(modalId) {
    const modal   = document.getElementById(modalId);
    const content = document.getElementById(`${modalId}Content`);

    if (!modal || !content) return;

    const errorBox = modal.querySelector(".modal-error");
    if (errorBox) {
        errorBox.innerHTML = "";
        errorBox.classList.add("hidden");
    }

    content.classList.remove("opacity-100", "scale-100");
    content.classList.add("opacity-0", "scale-95");

    setTimeout(() => modal.classList.add("hidden"), 150);

    document.removeEventListener("keydown", cerrarConEsc);
    modal.removeEventListener("click", cerrarClickFuera);
}

function cerrarConEsc(e) {
    if (e.key === "Escape") {
        const modal = document.querySelector(".modal-90s:not(.hidden)");
        if (modal) cerrarModal(modal.id);
    }
}

function cerrarClickFuera(e) {
    if (e.target === e.currentTarget) cerrarModal(e.currentTarget.id);
}

/* ============================================================
   CSRF TOKEN
   ============================================================ */

function getCSRFToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

/* ============================================================
   ACTUALIZAR CARD — REGLA UNIVERSAL
   ============================================================ */

function actualizarCard(productoId, ubicacionId, nuevaCantidad) {
    // Always sync inventarioTodas first — even when the card is not in the DOM
    // (e.g. destination location in a transfer is never rendered on this page)
    if (window.inventarioTodas) {
        const pid = parseInt(productoId);
        const uid = parseInt(ubicacionId);
        const qty = parseInt(nuevaCantidad);
        const entry = window.inventarioTodas.find(
            i => i.producto_id === pid && i.ubicacion_id === uid
        );
        if (entry) {
            entry.cantidad_actual = qty;
        } else {
            window.inventarioTodas.push({ producto_id: pid, ubicacion_id: uid, cantidad_actual: qty });
        }
    }

    // Refresh comparison panel count + always-visible location summary
    window.refrescarComparacionPiso?.();
    window.refrescarResumenUbicaciones?.(productoId);

    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    if (!card) return;

    const cantidadSpan = card.querySelector(".cantidad-ubicacion");
    if (cantidadSpan) cantidadSpan.textContent = nuevaCantidad;

    card.dataset.cantidad = nuevaCantidad;

    if (parseInt(nuevaCantidad) === 0) {
        card.style.backgroundColor = "#f3f4f6";
        card.style.borderColor     = "#9ca3af";
        card.style.order           = 9999;

        let btnEliminar = card.querySelector(".btn-eliminar-inv");
        if (!btnEliminar) {
            btnEliminar          = document.createElement("button");
            btnEliminar.className = "btn-eliminar-inv btn-90s w-full border-4 border-black shadow-[3px_3px_0_0_black] bg-[#FF006E] text-white font-black text-[10px] uppercase tracking-widest py-1.5 flex items-center justify-center gap-1 mt-1";
            btnEliminar.innerHTML = "⏳ Cargando...";
            btnEliminar.disabled  = true;
            btnEliminar.onclick   = () => eliminarInventarioHandler(productoId, ubicacionId);

            cantidadSpan.parentElement.insertAdjacentElement("afterend", btnEliminar);

            fetch(`/inventario/api/ubicaciones-del-producto/${productoId}/`)
                .then(r => r.json())
                .then(data => {
                    const otras = (data.ubicaciones || []).filter(
                        u => u.id != ubicacionId && u.cantidad > 0
                    );
                    btnEliminar.innerHTML = otras.length > 0
                        ? "🗑 Eliminar de aquí"
                        : "🚫 Desactivar";
                    btnEliminar.disabled = false;
                })
                .catch(() => {
                    btnEliminar.innerHTML = "🗑 Eliminar de aquí";
                    btnEliminar.disabled  = false;
                });
        }
        return;
    }

    // Restaurar card con cantidad > 0
    card.style.backgroundColor = card.dataset.color || "";
    card.style.borderColor     = "";
    card.style.order           = 0;

    const btnEliminar = card.querySelector(".btn-eliminar-inv");
    if (btnEliminar) btnEliminar.remove();
}

/* ============================================================
   ORDENAMIENTO INICIAL — cantidad 0 al final
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("#gridProductos .cardProducto").forEach(card => {
        card.style.order = parseInt(card.dataset.cantidad) === 0 ? 9999 : 0;
    });
});

/* ============================================================
   MENSAJES GLOBALES — estilo 90s
   ============================================================ */

function mostrarMensaje(texto) {
    const cont = document.getElementById("mensajeGlobal");
    if (!cont) return;

    cont.innerHTML = `
        <div class="border-4 border-black shadow-[4px_4px_0_0_black] bg-[#06D6A0]
                    text-black font-black px-5 py-3 uppercase tracking-widest text-sm">
            ${texto}
        </div>
    `;
    setTimeout(() => cont.innerHTML = "", 4000);
}

function mostrarError(texto) {
    const cont = document.getElementById("mensajeGlobal");
    if (!cont) return;

    cont.innerHTML = `
        <div class="border-4 border-black shadow-[4px_4px_0_0_black] bg-[#FF006E]
                    text-white font-black px-5 py-3 uppercase tracking-widest text-sm">
            ${texto}
        </div>
    `;
    setTimeout(() => cont.innerHTML = "", 5000);
}

function mostrarToastEnCard(productoId, ubicacionId, mensaje) {
    const card = document.getElementById(`card_${productoId}_${ubicacionId}`);
    if (!card) return;

    const old = card.querySelector(".card-toast");
    if (old) old.remove();

    const toast = document.createElement("div");
    toast.className = "card-toast";
    toast.style.cssText = [
        "border:2px solid black",
        "background:#CCFF00",
        "color:black",
        "font-weight:900",
        "font-size:0.65rem",
        "text-transform:uppercase",
        "letter-spacing:0.07em",
        "padding:0.3rem 0.5rem",
        "display:flex",
        "align-items:flex-start",
        "justify-content:space-between",
        "gap:0.25rem",
        "margin-top:0.375rem",
        "line-height:1.3",
    ].join(";");
    toast.innerHTML = `<span style="flex:1">${mensaje}</span><button onclick="this.parentElement.remove()" style="flex-shrink:0;font-weight:900;font-size:0.85rem;line-height:1;cursor:pointer;background:none;border:none;color:black;padding:0">✕</button>`;
    card.appendChild(toast);

    card.scrollIntoView({ behavior: "smooth", block: "center" });

    setTimeout(() => { if (toast.parentElement) toast.remove(); }, 6000);
}

function mostrarErrorEnModal(modalId, mensaje) {
    const modal = document.getElementById(modalId);
    if (!modal) return;

    const box = modal.querySelector(".modal-error");
    if (!box) return;

    box.innerHTML = mensaje;
    box.classList.remove("hidden");

    setTimeout(() => {
        box.innerHTML = "";
        box.classList.add("hidden");
    }, 2500);
}