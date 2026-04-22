// buscador_productos.js

import { normalizar } from "./core.js";
import { agregarProducto } from "./carrito.js";
import { activarBusqueda, desactivarBusqueda } from "./paginacion.js";

// ============================================================
// 1. BUSCADOR POR TEXTO
// ============================================================

export function initBuscador() {
    const buscarInput = document.getElementById("buscar-producto");

    if (!buscarInput) return;

    // Filtrar cards — también usado al limpiar
    function filtrarProductos(texto) {
        texto = normalizar(texto);
        const items = document.querySelectorAll(".producto-item");

        if (!texto) {
            // Sin texto → restaurar paginación
            desactivarBusqueda();
            return;
        }

        // Con texto → mostrar todos los que coincidan (sin paginación)
        activarBusqueda();
        items.forEach(item => {
            const nombre = normalizar(item.dataset.nombre);
            const codigo = normalizar(item.dataset.codigo || "");
            const sku    = normalizar(item.dataset.sku    || "");
            const coincide = nombre.includes(texto) || codigo.includes(texto) || sku.includes(texto);
            item.style.display = coincide ? "flex" : "none";
        });
    }

    // Búsqueda al escribir
    buscarInput.addEventListener("input", () => {
        filtrarProductos(buscarInput.value);
    });

    // Enter en el buscador → si hay exactamente 1 resultado, agregar al carrito
    buscarInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        const texto = normalizar(buscarInput.value.trim());
        if (!texto) return;

        const visibles = Array.from(document.querySelectorAll(".producto-item"))
            .filter(item => item.style.display !== "none");

        if (visibles.length === 1) {
            agregarDesdeCard(visibles[0]);
            buscarInput.value = "";
            filtrarProductos("");
        } else {
            // Buscar coincidencia exacta de código de barras
            const exacto = buscarProductoPorTextoExacto(texto);
            if (exacto) {
                agregarDesdeCard(exacto);
                buscarInput.value = "";
                filtrarProductos("");
            }
        }
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
// 3. ESCANEO — input dedicado (siempre va al carrito)
// ============================================================

export function initEscaneo() {
    const scanInput = document.getElementById("scan-input");

    if (scanInput) {
        scanInput.addEventListener("keydown", (e) => {
            if (e.key !== "Enter") return;

            const texto = normalizar(scanInput.value.trim());
            if (!texto) return;

            const producto = buscarProductoPorTexto(texto);

            if (producto) {
                agregarDesdeCard(producto);
                scanInput.value = "";
            } else {
                alert("Producto no encontrado");
            }
        });
    }

    // ============================================================
    // 4. ESCANEO GLOBAL — Enter desde cualquier lugar menos el buscador
    // ============================================================

    let scanBuffer = "";
    let scanTimer = null;

    document.addEventListener("keydown", (e) => {
        const active = document.activeElement;

        // Si el foco está en el buscador de productos → dejar que el usuario escriba ahí
        if (active && active.id === "buscar-producto") return;

        // Si el foco está en el scan-input → su propio listener lo maneja
        if (active && active.id === "scan-input") return;

        // Si algún modal está abierto → no capturar
        const modalAbierto = document.querySelector(
            "#modal-pago:not(.pos-modal--hidden), #modal-resultado:not(.pos-modal--hidden), #modal-consulta-precios:not(.pos-modal--hidden)"
        );
        if (modalAbierto) return;

        if (e.key === "Enter") {
            e.preventDefault();
            const texto = normalizar(scanBuffer.trim());
            scanBuffer = "";

            if (!texto) return;

            const producto = buscarProductoPorTextoExacto(texto);
            if (producto) agregarDesdeCard(producto);
            return;
        }

        // Acumular caracteres del escáner — siempre, sin importar qué input esté enfocado
        if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            scanBuffer += e.key;

            // Limpiar buffer después de 500ms sin actividad (los escáneres son rápidos)
            if (scanTimer) clearTimeout(scanTimer);
            scanTimer = setTimeout(() => { scanBuffer = ""; }, 500);
        }
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

// Búsqueda exacta para escaneo global (barcode)
function buscarProductoPorTextoExacto(texto) {
    return Array.from(document.querySelectorAll(".producto-item"))
        .find(p =>
            normalizar(p.dataset.codigo || "") === texto ||
            normalizar(p.dataset.sku || "") === texto
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
