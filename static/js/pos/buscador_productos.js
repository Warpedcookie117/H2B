import { normalizar } from "./core.js";
import { agregarProducto } from "./carrito.js";

export function initBuscador() {
    const buscarInput = document.getElementById("buscar-producto");

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
}

export function initDragDrop() {
    const listaProductos = document.getElementById("lista-productos");
    const carritoLista = document.getElementById("carrito-lista");

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

export function initEscaneo() {
    const scanInput = document.getElementById("scan-input");

    scanInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;

        const texto = normalizar(scanInput.value.trim());
        if (!texto) return;

        const producto = Array.from(document.querySelectorAll(".producto-item"))
            .find(p =>
                normalizar(p.dataset.nombre).includes(texto) ||
                normalizar(p.dataset.codigo || "").includes(texto) ||
                normalizar(p.dataset.sku || "").includes(texto)
            );

        if (producto) {
            const stock_piso = parseInt(producto.dataset.stockPiso);
            const stock_bodega = parseInt(producto.dataset.stockBodega);

            agregarProducto(
                parseInt(producto.dataset.id),
                producto.dataset.nombre,
                {
                    men: parseFloat(producto.dataset.men),
                    may: parseFloat(producto.dataset.may),
                    doc: parseFloat(producto.dataset.doc)
                },
                stock_piso,
                stock_bodega
            );

            scanInput.value = "";
        } else {
            alert("Producto no encontrado");
        }
    });
}