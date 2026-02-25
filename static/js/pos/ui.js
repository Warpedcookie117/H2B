// ui.js — Columna de precios por item (cuadros grandes)

import { carrito } from "./core.js";
import { setModoManual, recalcularPrecios } from "./precios.js";

// Contenedor donde irá la columna nueva
let columnaPrecios;

// ============================================================
// 1. Inicialización
// ============================================================
export function initCarritoUI() {
    // Crear la columna si no existe
    columnaPrecios = document.getElementById("columna-precios");

    if (!columnaPrecios) {
        console.error("ERROR: Falta <div id='columna-precios'> en el HTML");
        return;
    }

    renderPreciosPorItem();
}



// ============================================================
// 2. Render principal de la columna
// ============================================================
export function renderPreciosPorItem() {

    if (!columnaPrecios) return;

    columnaPrecios.innerHTML = "";

    carrito.forEach((item, index) => {

        const fila = document.createElement("div");
        fila.className = "flex flex-col gap-2 p-2 border-b";

        // Título del item
        const titulo = document.createElement("div");
        titulo.className = "text-sm font-semibold text-gray-700";
        titulo.textContent = item.nombre;

        // Contenedor de los 3 cuadros
        const cont = document.createElement("div");
        cont.className = "flex gap-2";

        // Crear los 3 cuadros
        const cuadroMen = crearCuadroPrecio(item, index, "MEN", item.precio_menudeo);
        const cuadroMay = crearCuadroPrecio(item, index, "MAY", item.precio_mayoreo);
        const cuadroDoc = crearCuadroPrecio(item, index, "DOC", item.precio_docena);

        cont.appendChild(cuadroMen);
        cont.appendChild(cuadroMay);

        // Solo mostrar DOC si el producto tiene precio_docena
        if (item.precio_docena) {
            cont.appendChild(cuadroDoc);
        }

        fila.appendChild(titulo);
        fila.appendChild(cont);

        columnaPrecios.appendChild(fila);
    });
}



// ============================================================
// 3. Crear un cuadro de precio (MEN / MAY / DOC)
// ============================================================
function crearCuadroPrecio(item, index, modo, precio) {

    const activo = item.modo_precio_final === modo;

    const btn = document.createElement("button");

    btn.className = `
        flex-1 p-2 rounded-lg border text-center text-sm font-bold transition
        ${activo ? "bg-yellow-300 border-yellow-500" : "bg-white border-gray-400 hover:bg-gray-100"}
    `;

    btn.textContent = `$${precio} ${modo}`;

    btn.addEventListener("click", () => {
        setModoManual(index, modo);
    });

    return btn;
}