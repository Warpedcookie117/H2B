// buscador_productos.js

import { normalizar } from "./core.js";
import { agregarProducto } from "./carrito.js";

// ============================================================
// 1. BUSCADOR POR TEXTO
// ============================================================

export function initBuscador() {
    const buscarInput = document.getElementById("buscar-producto");

    if (!buscarInput) return;

    buscarInput.addEventListener("input", () => {
        const texto = normalizar(buscarInput.value);

        document.querySelectorAll(".producto-item").forEach(item => {
            const nombre = normalizar(item.dataset.nombre);
            const codigo = normalizar(item.dataset.codigo || "");
            const sku = normalizar(item.dataset.sku || "");

            const coincide =
                nombre.includes(texto) ||
                codigo.includes(texto) ||
                sku.includes(texto);

            item.style.display = coincide ? "flex" : "none";
        });
    });

    // ============================================================
    // CLICK EN CARD → AGREGAR AL CARRITO
    // ============================================================

    document.querySelectorAll(".producto-item").forEach(card => {
        card.onclick = () => {
            const id = parseInt(card.dataset.id);
            const nombre = card.dataset.nombre;

            const precios = {
                men: parseFloat(card.dataset.men),
                may: parseFloat(card.dataset.may),
                doc: parseFloat(card.dataset.doc)
            };

            const stock_piso = parseInt(card.dataset.stockPiso);
            const stock_bodega = parseInt(card.dataset.stockBodega);

            agregarProducto(id, nombre, precios, stock_piso, stock_bodega);
        };
    });
}



// ============================================================
// 2. DRAG & DROP
// ============================================================

export function initDragDrop() {
    const listaProductos = document.getElementById("lista-productos");
    const carritoLista = document.getElementById("carrito-lista");

    if (!listaProductos || !carritoLista) return;

    listaProductos.querySelectorAll(".producto-item").forEach(item => {
        item.setAttribute("draggable", "true");

        item.addEventListener("dragstart", (e) => {
            e.dataTransfer.setData("producto_id", item.dataset.id);
            e.dataTransfer.setData("producto_nombre", item.dataset.nombre);

            e.dataTransfer.setData("precios", JSON.stringify({
                men: parseFloat(item.dataset.men),
                may: parseFloat(item.dataset.may),
                doc: parseFloat(item.dataset.doc),
                stock_piso: parseInt(item.dataset.stockPiso),
                stock_bodega: parseInt(item.dataset.stockBodega)
            }));
        });
    });

    carritoLista.addEventListener("dragover", (e) => e.preventDefault());

    carritoLista.addEventListener("drop", (e) => {
        const id = parseInt(e.dataTransfer.getData("producto_id"));
        const nombre = e.dataTransfer.getData("producto_nombre");
        const precios = JSON.parse(e.dataTransfer.getData("precios"));

        agregarProducto(
            id,
            nombre,
            {
                men: precios.men,
                may: precios.may,
                doc: precios.doc
            },
            precios.stock_piso,
            precios.stock_bodega
        );
    });
}



// ============================================================
// 3. ESCANEO (FUNCIONA EN AMBOS INPUTS)
// ============================================================

export function initEscaneo() {
    const scanInputs = [
        document.getElementById("scan-input"),        // input principal
        document.getElementById("buscar-producto")    // input de la columna derecha
    ];

    scanInputs.forEach(input => {
        if (!input) return;

        input.addEventListener("keydown", (e) => {
            if (e.key !== "Enter") return;

            const texto = normalizar(input.value.trim());
            if (!texto) return;

            const producto = buscarProductoPorTexto(texto);

            if (producto) {
                agregarDesdeCard(producto);
                input.value = "";
            } else {
                alert("Producto no encontrado");
            }
        });
    });
}



// ============================================================
// 4. HELPERS
// ============================================================

function buscarProductoPorTexto(texto) {
    return Array.from(document.querySelectorAll(".producto-item"))
        .find(p =>
            normalizar(p.dataset.nombre).includes(texto) ||
            normalizar(p.dataset.codigo || "").includes(texto) ||
            normalizar(p.dataset.sku || "").includes(texto)
        );
}

function agregarDesdeCard(card) {
    const id = parseInt(card.dataset.id);
    const nombre = card.dataset.nombre;

    const precios = {
        men: parseFloat(card.dataset.men),
        may: parseFloat(card.dataset.may),
        doc: parseFloat(card.dataset.doc)
    };

    const stock_piso = parseInt(card.dataset.stockPiso || card.dataset.stock_piso);
    const stock_bodega = parseInt(card.dataset.stockBodega || card.dataset.stock_bodega);

    agregarProducto(id, nombre, precios, stock_piso, stock_bodega);
}
