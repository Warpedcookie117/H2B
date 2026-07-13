// consulta_precios.js — Modal de consulta de precios (tecla E)

import { normalizar } from "./core.js";

console.log("[POS:consulta_precios] Módulo cargado");

let focoAnterior = null;

export function initConsultaPrecios() {
    const modal = document.getElementById("modal-consulta-precios");
    const input = document.getElementById("consulta-scan-input");
    const btnCerrar = document.getElementById("cerrar-consulta-precios");

    console.log(`[POS:consulta_precios] initConsultaPrecios — modal=${!!modal} input=${!!input}`);
    if (!modal || !input) return;

    window.abrirConsultaPrecios = abrirModal;

    document.addEventListener("keydown", (e) => {
        if (e.key === "e" || e.key === "E") {
            const active = document.activeElement;
            if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;
            if (!modal.classList.contains("pos-modal--hidden")) return;

            console.log("[POS:consulta_precios] tecla E → abriendo modal consulta precios");
            abrirModal();
        }
    });

    btnCerrar.onclick = () => {
        console.log("[POS:consulta_precios] botón cerrar → cerrarModal");
        cerrarModal();
    };

    modal.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            e.stopPropagation();
            console.log("[POS:consulta_precios] Escape → cerrarModal");
            cerrarModal();
        }
    });

    input.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;

        const texto = normalizar(input.value.trim());
        console.log(`[POS:consulta_precios] Enter en consulta-scan-input → texto="${texto}"`);
        if (!texto) return;

        buscarYMostrar(texto);
        input.value = "";
    });
}

function abrirModal() {
    const modal = document.getElementById("modal-consulta-precios");
    const input = document.getElementById("consulta-scan-input");

    focoAnterior = document.activeElement;
    console.log(`[POS:consulta_precios] abrirModal — foco anterior: ${focoAnterior?.id || focoAnterior?.tagName}`);

    document.getElementById("consulta-resultado").classList.add("pos-consulta-resultado--hidden");
    document.getElementById("consulta-no-encontrado").classList.add("pos-consulta-no-encontrado--hidden");

    modal.classList.remove("pos-modal--hidden");
    setTimeout(() => input.focus(), 100);
    console.log("[POS:consulta_precios] modal abierto ✓");
}

function cerrarModal() {
    const modal = document.getElementById("modal-consulta-precios");
    modal.classList.add("pos-modal--hidden");

    if (focoAnterior && focoAnterior.isConnected) {
        console.log(`[POS:consulta_precios] restaurando foco a: ${focoAnterior?.id || focoAnterior?.tagName}`);
        focoAnterior.focus();
    }
    focoAnterior = null;
    console.log("[POS:consulta_precios] modal cerrado ✓");
}

function buscarYMostrar(texto) {
    console.log(`[POS:consulta_precios] buscarYMostrar → "${texto}"`);
    const producto = Array.from(document.querySelectorAll(".producto-item"))
        .find(p =>
            normalizar(p.dataset.codigo || "") === texto ||
            normalizar(p.dataset.sku || "") === texto ||
            normalizar(p.dataset.nombre).includes(texto)
        );

    const resultado = document.getElementById("consulta-resultado");
    const noEncontrado = document.getElementById("consulta-no-encontrado");

    if (!producto) {
        console.warn(`[POS:consulta_precios] producto NO encontrado para "${texto}"`);
        resultado.classList.add("pos-consulta-resultado--hidden");
        noEncontrado.classList.remove("pos-consulta-no-encontrado--hidden");
        return;
    }

    console.log(`[POS:consulta_precios] producto encontrado: "${producto.dataset.nombre}" men=$${producto.dataset.men} may=$${producto.dataset.may} doc=$${producto.dataset.doc}`);
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
