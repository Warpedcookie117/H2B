// buscador_productos.js

import { normalizar } from "./core.js";
import { agregarProducto } from "./carrito.js";
import { setFiltro, clearFiltro, cargarImagenCard } from "./paginacion.js";

console.log("[POS:buscador] Módulo cargado");

// ============================================================
// ATAJO DE CANTIDAD (*N <Enter> → próximo escaneo lleva N piezas)
// ============================================================
//
// Flujo:
//   1. Cajera teclea:  *  3  0  Enter
//      → badge cambia a "×30 listo, escanea"
//   2. Cajera escanea código (o lo teclea + Enter)
//      → si N=1 variante: se agregan 30 piezas al carrito.
//      → si N>1 variantes: abre modal con cantidad=30 ya pre-rellenada.
//
// Cancelar: Esc en cualquier momento.
//
// El Enter intermedio es indispensable porque sin él los dígitos del
// código de barras (que también son numéricos) se acumularían en el
// buffer de cantidad.

let _modoCantidad   = false;
let _cantBuffer     = "";
let _cantPendiente  = null;   // entero o null
const TIMEOUT_ATAJO = 5000;
let _atajoTimer     = null;

function badge() {
    return document.getElementById("atajo-cantidad-badge");
}

function refrescarBadge() {
    const el = badge();
    if (!el) return;
    if (!_modoCantidad && _cantPendiente == null) {
        el.style.display = "none";
        return;
    }
    const texto = document.getElementById("atajo-cantidad-texto");
    const sub   = document.getElementById("atajo-cantidad-sub");
    if (_modoCantidad) {
        if (texto) texto.textContent = `×${_cantBuffer || "?"}`;
        if (sub)   sub.textContent   = "ENTER para confirmar (Esc cancela)";
    } else {
        if (texto) texto.textContent = `×${_cantPendiente}`;
        if (sub)   sub.textContent   = "escanea ahora (Esc para cancelar)";
    }
    el.style.display = "flex";
}

function activarModoCantidad() {
    _modoCantidad = true;
    _cantBuffer = "";
    _cantPendiente = null;
    refrescarBadge();
    reiniciarTimerAtajo();
}

function reiniciarTimerAtajo() {
    if (_atajoTimer) clearTimeout(_atajoTimer);
    _atajoTimer = setTimeout(() => {
        // Si quedó cantidad pendiente sin escaneo, expira para evitar
        // estados zombi cuando la cajera se distrae.
        cancelarAtajo();
    }, TIMEOUT_ATAJO);
}

function cancelarAtajo() {
    _modoCantidad  = false;
    _cantBuffer    = "";
    _cantPendiente = null;
    if (_atajoTimer) { clearTimeout(_atajoTimer); _atajoTimer = null; }
    refrescarBadge();
}

function confirmarBufferComoPendiente() {
    if (_cantBuffer) {
        _cantPendiente = parseInt(_cantBuffer, 10) || null;
    }
    _modoCantidad = false;
    refrescarBadge();
}

function consumirCantidadPendiente() {
    const n = _cantPendiente;
    _cantPendiente = null;
    if (_atajoTimer) { clearTimeout(_atajoTimer); _atajoTimer = null; }
    refrescarBadge();
    return n;
}

function cantidadParaEsteEscaneo(defaultV = 1) {
    return _cantPendiente && _cantPendiente > 0 ? _cantPendiente : defaultV;
}

// Intercepta una tecla a nivel global o de input.
// Devuelve true si se "comió" la tecla (el caller debe preventDefault y NO
// propagar al handler de scan/Enter).
function atajoKeydown(e) {
    if (e.key === "*") {
        activarModoCantidad();
        return true;
    }
    if (e.key === "Escape" && (_modoCantidad || _cantPendiente != null)) {
        cancelarAtajo();
        return true;
    }
    if (_modoCantidad) {
        if (e.key >= "0" && e.key <= "9") {
            _cantBuffer += e.key;
            refrescarBadge();
            reiniciarTimerAtajo();
            return true;
        }
        if (e.key === "Backspace") {
            _cantBuffer = _cantBuffer.slice(0, -1);
            refrescarBadge();
            reiniciarTimerAtajo();
            return true;
        }
        if (e.key === "Enter") {
            // Enter confirma la cantidad y NO debe ejecutar el handler de
            // escaneo (no hay código aún) → consumir.
            if (_cantBuffer) confirmarBufferComoPendiente();
            else             cancelarAtajo();
            return true;
        }
        // Cualquier otra tecla cancela el modo cantidad sin confirmar
        // (probablemente la cajera cambió de idea o tecleó por error).
        cancelarAtajo();
        return false;
    }
    return false;
}

// ============================================================
// CLOUDINARY: URL ligera para fotos del modal
// ============================================================
function urlImagenLigera(url, w = 160) {
    if (!url || typeof url !== "string") return url;
    if (!url.includes("/image/upload/")) return url;
    const trans = `w_${w},c_limit,q_auto:low,f_auto`;
    // Detectar si ya hay un set de transformaciones (segmento que contiene "_" o ",")
    const match = url.match(/\/image\/upload\/([^/]+)\//);
    if (match && (match[1].includes(",") || match[1].includes("_"))) {
        return url.replace(/\/image\/upload\/[^/]+\//, `/image/upload/${trans}/`);
    }
    return url.replace("/image/upload/", `/image/upload/${trans}/`);
}

// ============================================================
// 1. BUSCADOR POR TEXTO
// ============================================================

export function initBuscador() {
    const buscarInput = document.getElementById("buscar-producto");
    console.log(`[POS:buscador] initBuscador — input encontrado: ${!!buscarInput}`);

    if (!buscarInput) return;

    function filtrarProductos(texto) {
        texto = normalizar(texto);

        if (!texto) {
            console.log("[POS:buscador] filtrar: texto vacío → clearFiltro");
            clearFiltro();
            return;
        }

        const items = Array.from(document.querySelectorAll(".producto-item"));

        const coincidentes = items
            .map(item => {
                const nombre = normalizar(item.dataset.nombre);
                const codigo = normalizar(item.dataset.codigo || "");
                const sku    = normalizar(item.dataset.sku    || "");
                const score  = getScoreBusqueda(nombre, codigo, sku, texto);
                return { item, score };
            })
            .filter(({ score }) => score > 0)
            .sort((a, b) => b.score - a.score)
            .map(({ item }) => item);

        setFiltro(coincidentes);
        console.log(`[POS:buscador] filtrar "${texto}" → ${coincidentes.length} resultados`);
    }

    function getScoreBusqueda(nombre, codigo, sku, texto) {
        if (codigo === texto || sku === texto)                        return 100;
        if (nombre === texto)                                         return 90;
        if (codigo.startsWith(texto) || sku.startsWith(texto))       return 80;
        if (nombre.startsWith(texto))                                 return 70;
        if (nombre.includes(texto))                                   return 60;
        if (codigo.includes(texto) || sku.includes(texto))           return 50;
        return 0;
    }

    buscarInput.addEventListener("input", () => {
        console.log(`[POS:buscador] input en buscar-producto: "${buscarInput.value}"`);
        filtrarProductos(buscarInput.value);
        if (!buscarInput.value) {
            document.getElementById("scan-input")?.focus();
        }
    });

    buscarInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        const texto = normalizar(buscarInput.value.trim());
        if (!texto) return;

        const visibles = Array.from(document.querySelectorAll(".producto-item"))
            .filter(item => item.style.display !== "none");

        if (visibles.length === 1) {
            agregarDesdeCard(visibles[0], cantidadParaEsteEscaneo());
            consumirCantidadPendiente();
            buscarInput.value = "";
            filtrarProductos("");
            return;
        }

        const matches = buscarCardsPorCodigoExacto(texto);
        if (matches.length === 1) {
            agregarDesdeCard(matches[0], cantidadParaEsteEscaneo());
            consumirCantidadPendiente();
            buscarInput.value = "";
            filtrarProductos("");
        } else if (matches.length > 1) {
            abrirSelectorVariantes(matches, texto, cantidadParaEsteEscaneo());
            consumirCantidadPendiente();
            buscarInput.value = "";
            filtrarProductos("");
        } else {
            console.log(`[POS:buscador] sin coincidencia exacta — no se agrega`);
        }
    });

    document.querySelectorAll(".producto-item").forEach(card => {
        card.onclick = () => {
            console.log(`[POS:buscador] click en card → id=${card.dataset.id} nombre="${card.dataset.nombre}"`);
            agregarDesdeCard(card, cantidadParaEsteEscaneo());
            consumirCantidadPendiente();
        };
    });

    console.log(`[POS:buscador] initBuscador completo — ${document.querySelectorAll(".producto-item").length} cards`);
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
                stock_bodega: parseInt(item.dataset.stockBodega),
                subcategoria_id: item.dataset.subcategoria ? parseInt(item.dataset.subcategoria) : null,
                cat_padre_id:    item.dataset.catPadre     ? parseInt(item.dataset.catPadre)     : null,
                atributos:       item.dataset.atributos ? JSON.parse(item.dataset.atributos) : {},
            }));
        });
    });

    carritoLista.addEventListener("dragover", (e) => e.preventDefault());

    carritoLista.addEventListener("drop", (e) => {
        const id = parseInt(e.dataTransfer.getData("producto_id"));
        const nombre = e.dataTransfer.getData("producto_nombre");
        const precios = JSON.parse(e.dataTransfer.getData("precios"));

        agregarProducto(
            id, nombre,
            { men: precios.men, may: precios.may, doc: precios.doc },
            precios.stock_piso, precios.stock_bodega,
            precios.subcategoria_id, precios.cat_padre_id,
            precios.atributos || {},
        );
    });
}



// ============================================================
// 3. ESCANEO — input dedicado (siempre va al carrito)
// ============================================================

export function initEscaneo() {
    const scanInput = document.getElementById("scan-input");
    console.log(`[POS:buscador] initEscaneo — scan-input encontrado: ${!!scanInput}`);

    if (scanInput) {
        // Atajo *N en el propio scan-input
        scanInput.addEventListener("keydown", (e) => {
            // Si la tecla es parte del atajo y la consumimos, prevent y salir.
            // Excepción: Enter no se consume; cae al handler de abajo.
            if (atajoKeydown(e)) {
                if (e.key !== "Enter") e.preventDefault();
                return;
            }

            if (e.key !== "Enter") return;

            const texto = normalizar(scanInput.value.trim());
            console.log(`[POS:buscador] scan-input Enter → texto="${texto}" pendiente=${_cantPendiente}`);
            if (!texto) return;

            const cant = cantidadParaEsteEscaneo();

            const matches = buscarCardsPorCodigoExacto(texto);
            if (matches.length === 1) {
                agregarDesdeCard(matches[0], cant);
                consumirCantidadPendiente();
                scanInput.value = "";
                return;
            }
            if (matches.length > 1) {
                abrirSelectorVariantes(matches, texto, cant);
                consumirCantidadPendiente();
                scanInput.value = "";
                return;
            }

            // Fallback: incluye en nombre/sku
            const producto = buscarProductoPorTexto(texto);
            if (producto) {
                agregarDesdeCard(producto, cant);
                consumirCantidadPendiente();
                scanInput.value = "";
            } else {
                console.warn(`[POS:buscador] scan-input: PRODUCTO NO ENCONTRADO para "${texto}"`);
                alert("Producto no encontrado");
            }
        });
    }

    // ============================================================
    // FOCO PERMANENTE
    // ============================================================
    const esTouch = window.matchMedia("(pointer: coarse)").matches;

    document.addEventListener("click", (e) => {
        if (esTouch) return;
        if (e.target.id === "buscar-producto") return;
        if (e.target.id === "modal-variantes-buscar") return;
        if (e.target.id === "modal-variantes-cantidad") return;

        const modalAbierto =
            !document.getElementById("modal-pago")?.classList.contains("pos-modal--hidden") ||
            !document.getElementById("modal-resultado")?.classList.contains("pos-modal--hidden") ||
            !document.getElementById("modal-consulta-precios")?.classList.contains("pos-modal--hidden") ||
            !document.getElementById("modal-config-impresora")?.classList.contains("pos-modal--hidden") ||
            !document.getElementById("modal-variantes")?.classList.contains("pos-modal--hidden") ||
            document.getElementById("modal-servicio")?.style.display === "flex" ||
            document.getElementById("modal-regalo")?.style.display === "flex";

        if (modalAbierto) return;

        setTimeout(() => document.getElementById("scan-input")?.focus(), 0);
    });

    // ============================================================
    // 4. ESCANEO GLOBAL — Enter desde cualquier lugar menos el buscador
    // ============================================================

    let scanBuffer = "";
    let scanTimer = null;

    document.addEventListener("keydown", (e) => {
        const active = document.activeElement;

        if (active && active.id === "buscar-producto") return;
        if (active && active.id === "scan-input") return; // su propio handler ya lo maneja
        if (active && active.id === "modal-variantes-buscar") return;
        if (active && active.id === "modal-variantes-cantidad") return;

        // Atajo *N a nivel global
        if (atajoKeydown(e)) {
            if (e.key !== "Enter") e.preventDefault();
            return;
        }

        const modalAbierto = document.querySelector(
            "#modal-pago:not(.pos-modal--hidden), #modal-resultado:not(.pos-modal--hidden), #modal-consulta-precios:not(.pos-modal--hidden)"
        );
        if (modalAbierto) return;

        const modalServicio = document.getElementById("modal-servicio");
        if (modalServicio && modalServicio.style.display === "flex") return;

        if (e.key === "Enter") {
            e.preventDefault();
            const texto = normalizar(scanBuffer.trim());
            scanBuffer = "";

            if (!texto) return;

            const cant = cantidadParaEsteEscaneo();

            const matches = buscarCardsPorCodigoExacto(texto);
            if (matches.length === 1) {
                agregarDesdeCard(matches[0], cant);
                consumirCantidadPendiente();
            } else if (matches.length > 1) {
                abrirSelectorVariantes(matches, texto, cant);
                consumirCantidadPendiente();
            } else {
                console.warn(`[POS:buscador] SCAN GLOBAL: NO encontrado para "${texto}"`);
            }
            return;
        }

        if (e.key.length === 1 && !e.ctrlKey && !e.altKey && !e.metaKey) {
            e.preventDefault();
            scanBuffer += e.key;

            if (scanTimer) clearTimeout(scanTimer);
            scanTimer = setTimeout(() => { scanBuffer = ""; }, 500);
        }
    });

    initSelectorVariantes();
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

function buscarCardsPorCodigoExacto(texto) {
    return Array.from(document.querySelectorAll(".producto-item"))
        .filter(p =>
            normalizar(p.dataset.codigo || "") === texto ||
            normalizar(p.dataset.sku || "") === texto
        );
}

function agregarDesdeCard(card, cantidad = 1) {
    const id = parseInt(card.dataset.id);
    const nombre = card.dataset.nombre;

    const precios = {
        men: parseFloat(card.dataset.men),
        may: parseFloat(card.dataset.may),
        doc: parseFloat(card.dataset.doc)
    };

    const stock_piso    = parseInt(card.dataset.stockPiso    || card.dataset.stock_piso);
    const stock_bodega  = parseInt(card.dataset.stockBodega  || card.dataset.stock_bodega);
    const subcategoria_id = card.dataset.subcategoria  ? parseInt(card.dataset.subcategoria)  : null;
    const cat_padre_id    = card.dataset.catPadre      ? parseInt(card.dataset.catPadre)      : null;
    const atributos       = card.dataset.atributos     ? JSON.parse(card.dataset.atributos)   : {};

    const cant = Math.max(1, parseInt(cantidad) || 1);
    console.log(`[POS:buscador] agregarDesdeCard → id=${id} nombre="${nombre}" cant=${cant}`);

    for (let i = 0; i < cant; i++) {
        agregarProducto(id, nombre, precios, stock_piso, stock_bodega, subcategoria_id, cat_padre_id, atributos);
    }
}



// ============================================================
// 5. SELECTOR DE VARIANTES — modal con paginación e input cantidad
// ============================================================

const VARIANTES_POR_PAGINA = 12;
let _cardsActuales = [];
let _cardsFiltradas = [];
let _paginaActual = 0;

function abrirSelectorVariantes(cards, codigoScan, cantidadInicial = 1) {
    const modal = document.getElementById("modal-variantes");
    const grid  = document.getElementById("modal-variantes-grid");
    const sub   = document.getElementById("modal-variantes-sub");
    const inputFiltro = document.getElementById("modal-variantes-buscar");
    const inputCant   = document.getElementById("modal-variantes-cantidad");
    if (!modal || !grid || !inputFiltro) {
        console.warn("[POS:buscador] modal-variantes no encontrado en DOM — agregando primer match");
        if (cards.length) agregarDesdeCard(cards[0], cantidadInicial);
        return;
    }

    _cardsActuales = cards;
    _cardsFiltradas = cards.slice();
    _paginaActual = 0;

    if (sub) {
        sub.textContent = `Código ${codigoScan} → ${cards.length} variantes. Filtra o pícale a una.`;
    }
    if (inputCant) {
        inputCant.value = String(Math.max(1, parseInt(cantidadInicial) || 1));
    }

    renderPaginaActual();

    modal.classList.remove("pos-modal--hidden");
    inputFiltro.value = "";
    setTimeout(() => inputFiltro.focus(), 30);
}

function cerrarSelectorVariantes() {
    const modal = document.getElementById("modal-variantes");
    if (!modal) return;
    modal.classList.add("pos-modal--hidden");
    _cardsActuales  = [];
    _cardsFiltradas = [];
    _paginaActual   = 0;
    setTimeout(() => document.getElementById("scan-input")?.focus(), 50);
}

function leerCantidadDelModal() {
    const inputCant = document.getElementById("modal-variantes-cantidad");
    const v = parseInt(inputCant?.value);
    return Math.max(1, isNaN(v) ? 1 : v);
}

function renderPaginaActual() {
    const grid = document.getElementById("modal-variantes-grid");
    const paginacion = document.getElementById("modal-variantes-paginacion");
    const info = document.getElementById("modal-variantes-info");
    if (!grid) return;

    while (grid.firstChild) grid.removeChild(grid.firstChild);

    const total = _cardsFiltradas.length;
    const totalPaginas = Math.max(1, Math.ceil(total / VARIANTES_POR_PAGINA));
    if (_paginaActual >= totalPaginas) _paginaActual = totalPaginas - 1;
    if (_paginaActual < 0) _paginaActual = 0;

    if (total === 0) {
        const vacio = document.createElement("p");
        vacio.style.cssText = "padding:1rem;font-weight:700;color:#6b7280;grid-column:1/-1;text-align:center;";
        vacio.textContent = "Sin coincidencias con el filtro.";
        grid.appendChild(vacio);
        if (paginacion) paginacion.style.display = "none";
        return;
    }

    const inicio = _paginaActual * VARIANTES_POR_PAGINA;
    const fin    = Math.min(inicio + VARIANTES_POR_PAGINA, total);
    const slice  = _cardsFiltradas.slice(inicio, fin);

    const PALETA = ["#FFBE0B","#06D6A0","#3A86FF","#8338EC","#FF6B35","#FF006E"];
    const PALETA_HOVER = ["#f5a800","#00b88a","#1a6fe0","#6620c7","#e05200","#cc004e"];

    slice.forEach((card, idx) => {
        const colorBase  = PALETA[idx % PALETA.length];
        const colorHover = PALETA_HOVER[idx % PALETA_HOVER.length];
        const textoDark  = colorBase === "#FFBE0B" || colorBase === "#06D6A0";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.dataset.idx = String(idx);
        btn.style.cssText = [
            "display:flex",
            "flex-direction:column",
            "gap:.35rem",
            "padding:.5rem",
            `border:3px solid black`,
            `background:${colorBase}`,
            "box-shadow:4px 4px 0 0 black",
            "cursor:pointer",
            "text-align:left",
            "min-width:0",
            "min-height:200px",
            "overflow:hidden",
            "transition:transform .08s,box-shadow .08s",
        ].join(";");
        btn.onmouseenter = () => {
            btn.style.background = colorHover;
            btn.style.transform = "translate(-2px,-2px)";
            btn.style.boxShadow = "6px 6px 0 0 black";
        };
        btn.onmouseleave = () => {
            btn.style.background = colorBase;
            btn.style.transform = "";
            btn.style.boxShadow = "4px 4px 0 0 black";
        };

        // Foto — q_auto:low para thumbnail barato en Cloudinary
        const fotoBox = document.createElement("div");
        fotoBox.style.cssText = "width:100%;height:120px;border:2px solid black;background:#fff;display:flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;";
        const imgEl = card.querySelector("img");
        const srcOriginal = imgEl?.dataset?.src || imgEl?.src || "";
        const srcLigera = urlImagenLigera(srcOriginal, 240);
        if (srcLigera) {
            const img = document.createElement("img");
            img.src = srcLigera;
            img.loading = "lazy";
            img.alt = card.dataset.nombre || "";
            img.style.cssText = "width:100%;height:100%;object-fit:cover;";
            fotoBox.appendChild(img);
        } else {
            fotoBox.style.fontSize = "2rem";
            fotoBox.textContent = "📦";
        }
        btn.appendChild(fotoBox);

        // Nombre
        const colorTexto = textoDark ? "#000" : "#fff";
        const nombre = document.createElement("p");
        nombre.style.cssText = `font-weight:900;font-size:.8rem;line-height:1.15;color:${colorTexto};margin:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;`;
        nombre.textContent = card.dataset.nombre || "";
        btn.appendChild(nombre);

        // Atributos como pills individuales
        const atributos = card.dataset.atributos ? safeJsonParse(card.dataset.atributos) : null;
        if (atributos) {
            const pillsWrap = document.createElement("div");
            pillsWrap.style.cssText = "display:flex;flex-wrap:wrap;gap:3px;margin:0;";
            Object.entries(atributos)
                .filter(([_, v]) => v !== null && v !== undefined && String(v).trim() !== "" && String(v).toLowerCase() !== "n/a")
                .forEach(([k, v]) => {
                    const pill = document.createElement("span");
                    pill.style.cssText = "background:rgba(0,0,0,0.75);color:#fff;font-size:.58rem;font-weight:900;letter-spacing:.04em;padding:2px 5px;text-transform:uppercase;line-height:1.3;";
                    pill.textContent = `${k}: ${v}`;
                    pillsWrap.appendChild(pill);
                });
            if (pillsWrap.children.length) btn.appendChild(pillsWrap);
        }

        // Precio
        const precio = document.createElement("p");
        precio.style.cssText = `font-weight:900;font-size:.85rem;color:${colorTexto};margin:0 0 0 0;margin-top:auto;`;
        precio.textContent = `$${card.dataset.men}`;
        btn.appendChild(precio);

        btn.addEventListener("click", () => {
            const cant = leerCantidadDelModal();
            agregarDesdeCard(card, cant);
            cerrarSelectorVariantes();
        });
        grid.appendChild(btn);
    });

    if (paginacion) {
        if (totalPaginas > 1) {
            paginacion.style.display = "flex";
            if (info) info.textContent = `${_paginaActual + 1} / ${totalPaginas}`;
        } else {
            paginacion.style.display = "none";
        }
    }
}

function safeJsonParse(s) {
    try { return JSON.parse(s); } catch { return null; }
}

function filtrarVariantesEnModal(texto) {
    const q = normalizar(texto || "");
    if (!q) {
        _cardsFiltradas = _cardsActuales.slice();
    } else {
        _cardsFiltradas = _cardsActuales.filter(card => {
            const nombre = normalizar(card.dataset.nombre || "");
            if (nombre.includes(q)) return true;
            const atrJson = card.dataset.atributos || "";
            if (normalizar(atrJson).includes(q)) return true;
            return false;
        });
    }
    _paginaActual = 0;
    renderPaginaActual();
}

function initSelectorVariantes() {
    const modal = document.getElementById("modal-variantes");
    if (!modal) return;

    const input = document.getElementById("modal-variantes-buscar");
    const cerrarBtn = document.getElementById("cerrar-modal-variantes");
    const btnPrev = document.getElementById("modal-variantes-prev");
    const btnNext = document.getElementById("modal-variantes-next");
    const inputCant = document.getElementById("modal-variantes-cantidad");

    if (input) {
        input.addEventListener("input", () => filtrarVariantesEnModal(input.value));

        input.addEventListener("keydown", (e) => {
            if (e.key === "Escape") {
                e.preventDefault();
                cerrarSelectorVariantes();
                return;
            }
            if (e.key === "Enter") {
                e.preventDefault();
                const primerBtn = document.querySelector("#modal-variantes-grid button[data-idx]");
                if (primerBtn) primerBtn.click();
            }
        });
    }

    if (inputCant) {
        inputCant.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                input?.focus();
            }
        });
    }

    if (btnPrev) {
        btnPrev.addEventListener("click", () => {
            if (_paginaActual > 0) {
                _paginaActual--;
                renderPaginaActual();
            }
        });
    }
    if (btnNext) {
        btnNext.addEventListener("click", () => {
            const totalPaginas = Math.max(1, Math.ceil(_cardsFiltradas.length / VARIANTES_POR_PAGINA));
            if (_paginaActual < totalPaginas - 1) {
                _paginaActual++;
                renderPaginaActual();
            }
        });
    }

    if (cerrarBtn) {
        cerrarBtn.addEventListener("click", cerrarSelectorVariantes);
    }

    modal.addEventListener("click", (e) => {
        if (e.target === modal) cerrarSelectorVariantes();
    });

    document.addEventListener("keydown", (e) => {
        if (e.key !== "Escape") return;
        if (modal.classList.contains("pos-modal--hidden")) return;
        e.preventDefault();
        cerrarSelectorVariantes();
    });
}
