import { carrito } from "./core.js";
import { actualizarTotales } from "./totales.js";
import { aplicarPreciosGlobales } from "./precios.js";

export function agregarProducto(id, nombre, precios, stock_piso, stock_bodega) {

    if (!id) return;
    if (!precios || !precios.men) return;

    const existente = carrito.find(p => p.id === id);

    if (existente) {
        existente.cantidad++;
    } else {
        const nuevo = {
            id,
            nombre,
            cantidad: 1,
            modo_precio: "AUTO",
            precios,
            precio_aplicado: precios.men,
            modo_resuelto: "MEN",
            stock_piso: stock_piso ?? 0,
            stock_bodega: stock_bodega ?? 0
        };

        carrito.push(nuevo);
    }

    aplicarPreciosGlobales();
    actualizarTotales();
    renderCarrito();
}

export function renderCarrito() {
    const carritoLista = document.getElementById("carrito-lista");
    carritoLista.innerHTML = "";

    carrito.forEach((item, index) => {

        let aviso = "";

        if (item.cantidad <= item.stock_piso) {
            aviso = `
                <div class="mt-1">
                    <span class="inline-block bg-green-600 text-white text-xs font-semibold px-2 py-1 rounded">
                        Se descontará de Piso
                    </span>
                </div>
            `;
        } else if (item.cantidad > item.stock_piso && item.cantidad <= item.stock_bodega) {
            aviso = `
                <div class="mt-1">
                    <span class="inline-block bg-yellow-500 text-white text-xs font-semibold px-2 py-1 rounded">
                        Se descontará de Bodega Interna
                    </span>
                </div>
            `;
        } else if (item.cantidad > item.stock_bodega) {
            aviso = `
                <div class="mt-1">
                    <span class="inline-block bg-red-600 text-white text-xs font-semibold px-2 py-1 rounded">
                        No hay stock suficiente, verifica otras ubicaciones
                    </span>
                </div>
            `;
        }

        const precioSeguro = Number(item.precio_aplicado || 0);

        const colores = {
            AUTO: "bg-blue-600 text-white",
            MEN: "bg-pink-300 text-black",
            MAY: "bg-green-500 text-white",
            DOC: "bg-purple-500 text-white"
        };

        const tieneDoc = item.precios.doc && item.precios.doc > 0;

        const div = document.createElement("div");
        div.className = "bg-gray-100 p-3 rounded-lg shadow flex flex-col gap-2";

        div.innerHTML = `
            <div class="flex justify-between items-center">
                <span class="font-semibold">${item.nombre}</span>

                <div class="flex items-center gap-3">
                    <button class="px-3 py-1 bg-red-500 text-white rounded" data-idx="${index}" data-action="menos">-</button>
                    <span class="text-lg font-bold">${item.cantidad}</span>
                    <button class="px-3 py-1 bg-green-500 text-white rounded" data-idx="${index}" data-action="mas">+</button>
                </div>
            </div>

            ${aviso}

            <div class="flex gap-2">
                ${["MEN", "MAY", "DOC", "AUTO"].map(m => {

                    // 🔒 DOC deshabilitado si no existe precio DOC
                    if (m === "DOC" && !tieneDoc) {
                        return `
                            <button class="px-2 py-1 rounded text-xs font-bold bg-gray-400 opacity-50 cursor-not-allowed"
                                disabled>
                                DOC
                            </button>
                        `;
                    }

                    // 1) Si el cajero eligió manualmente
                    if (item.modo_precio === m) {
                        return `
                            <button class="px-2 py-1 rounded text-xs font-bold ${colores[m]}"
                                data-idx="${index}" data-modo="${m}">
                                ${m}
                            </button>
                        `;
                    }

                    // 2) Si está en AUTO, AUTO es el activo
                    if (item.modo_precio === "AUTO" && m === "AUTO") {
                        return `
                            <button class="px-2 py-1 rounded text-xs font-bold ${colores.AUTO}"
                                data-idx="${index}" data-modo="AUTO">
                                AUTO
                            </button>
                        `;
                    }

                    // 3) Si está en AUTO y este botón es el modo aplicado → borde negro
                    if (item.modo_precio === "AUTO" && item.modo_resuelto === m) {
                        return `
                            <button class="px-2 py-1 rounded text-xs font-bold ${colores[m]} border-4 border-black"
                                data-idx="${index}" data-modo="${m}">
                                ${m}
                            </button>
                        `;
                    }

                    // 4) Botón normal
                    return `
                        <button class="px-2 py-1 rounded text-xs font-bold bg-gray-300"
                            data-idx="${index}" data-modo="${m}">
                            ${m}
                        </button>
                    `;
                }).join("")}
            </div>

            <div class="text-right font-bold text-lg text-red-600">
                $${precioSeguro.toFixed(2)}
            </div>
        `;

        carritoLista.appendChild(div);
    });

    carritoLista.querySelectorAll("button").forEach(btn => {
        const idx = parseInt(btn.dataset.idx);

        if (btn.dataset.action === "mas") {
            btn.onclick = () => {
                carrito[idx].cantidad++;
                aplicarPreciosGlobales();
                actualizarTotales();
                renderCarrito();
            };
        }

        if (btn.dataset.action === "menos") {
            btn.onclick = () => {
                carrito[idx].cantidad--;

                if (carrito[idx].cantidad <= 0) {
                    carrito.splice(idx, 1);
                }

                aplicarPreciosGlobales();
                actualizarTotales();
                renderCarrito();
            };
        }

        if (btn.dataset.modo) {
            btn.onclick = () => {
                carrito[idx].modo_precio = btn.dataset.modo;
                aplicarPreciosGlobales();
                actualizarTotales();
                renderCarrito();
            };
        }
    });
}