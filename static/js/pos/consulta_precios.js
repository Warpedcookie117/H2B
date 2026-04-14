// consulta_precios.js — Modal de consulta de precios (tecla E)

import { normalizar } from "./core.js";

// Estado para restaurar el foco al cerrar
let focoAnterior = null;

// ============================================================
// INICIALIZACIÓN
// ============================================================

export function initConsultaPrecios() {
    const modal = document.getElementById("modal-consulta-precios");
    const input = document.getElementById("consulta-scan-input");
    const btnCerrar = document.getElementById("cerrar-consulta-precios");

    if (!modal || !input) return;

    // Tecla E para abrir (sin estar en input)
    document.addEventListener("keydown", (e) => {
        if (e.key === "e" || e.key === "E") {
            // No abrir si está en un input, textarea, contenteditable, o modal ya abierto
            const active = document.activeElement;
            if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;
            if (!modal.classList.contains("pos-modal--hidden")) return;

            abrirModal();
        }
    });

    // Cerrar con botón
    btnCerrar.onclick = cerrarModal;

    // Cerrar con Escape
    modal.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            e.stopPropagation();
            cerrarModal();
        }
    });

    // Escaneo dentro del modal
    input.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;

        const texto = normalizar(input.value.trim());
        if (!texto) return;

        buscarYMostrar(texto);
        input.value = "";
    });
}

// ============================================================
// ABRIR / CERRAR
// ============================================================

function abrirModal() {
    const modal = document.getElementById("modal-consulta-precios");
    const input = document.getElementById("consulta-scan-input");

    focoAnterior = document.activeElement;

    // Limpiar resultados previos
    document.getElementById("consulta-resultado").classList.add("pos-consulta-resultado--hidden");
    document.getElementById("consulta-no-encontrado").classList.add("pos-consulta-no-encontrado--hidden");

    modal.classList.remove("pos-modal--hidden");

    setTimeout(() => input.focus(), 100);
}

function cerrarModal() {
    const modal = document.getElementById("modal-consulta-precios");
    modal.classList.add("pos-modal--hidden");

    // Restaurar foco
    if (focoAnterior && focoAnterior.isConnected) {
        focoAnterior.focus();
    }
    focoAnterior = null;
}

// ============================================================
// BÚSQUEDA Y DISPLAY
// ============================================================

function buscarYMostrar(texto) {
    const producto = Array.from(document.querySelectorAll(".producto-item"))
        .find(p =>
            normalizar(p.dataset.codigo || "") === texto ||
            normalizar(p.dataset.sku || "") === texto ||
            normalizar(p.dataset.nombre).includes(texto)
        );

    const resultado = document.getElementById("consulta-resultado");
    const noEncontrado = document.getElementById("consulta-no-encontrado");

    if (!producto) {
        resultado.classList.add("pos-consulta-resultado--hidden");
        noEncontrado.classList.remove("pos-consulta-no-encontrado--hidden");
        return;
    }

    noEncontrado.classList.add("pos-consulta-no-encontrado--hidden");

    document.getElementById("consulta-nombre").textContent = producto.dataset.nombre;
    document.getElementById("consulta-codigo").textContent = producto.dataset.codigo || producto.dataset.sku || "N/A";

    const men = parseFloat(producto.dataset.men);
    const may = parseFloat(producto.dataset.may);
    const doc = parseFloat(producto.dataset.doc);

    document.getElementById("consulta-men").textContent = `$${men.toFixed(2)}`;
    document.getElementById("consulta-may").textContent = `$${may.toFixed(2)}`;
    document.getElementById("consulta-doc").textContent = doc && doc > 0 ? `$${doc.toFixed(2)}` : "N/A";

    document.getElementById("consulta-stock-piso").textContent = producto.dataset.stockPiso || "0";
    document.getElementById("consulta-stock-bodega").textContent = producto.dataset.stockBodega || "0";

    resultado.classList.remove("pos-consulta-resultado--hidden");
}
