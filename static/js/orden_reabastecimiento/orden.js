// ============================================================
// ORDEN DE REABASTECIMIENTO — bodega interna → piso
// Móvil-first: escáner continuo, stock en vivo (WS), borrador
// en localStorage, confirmación con resumen y resultado por renglón.
// ============================================================

(function () {
    const CTX = window.REAB_CTX;
    if (!CTX) { console.error("[reab] Falta REAB_CTX"); return; }

    const LS_KEY = `reab_orden_v1_${CTX.bodegaId}`;

    // Estado: [{id, nombre, foto, codigo, cantidad, stockBodega, stockPiso,
    //           palomeado, vaciar, error}]
    let items = [];

    // ============================================================
    // HELPERS
    // ============================================================

    const $ = (id) => document.getElementById(id);

    function getCSRF() {
        return document.querySelector("[name=csrfmiddlewaretoken]").value;
    }

    function uuid() {
        return (crypto.randomUUID) ? crypto.randomUUID()
            : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    }

    function guardar() {
        try { localStorage.setItem(LS_KEY, JSON.stringify(items)); } catch (_) {}
    }

    function toast(msg, tipo = "ok") {
        const cont = $("reab-toast");
        const bg = tipo === "ok" ? "#06D6A0" : (tipo === "warn" ? "#FFBE0B" : "#FF006E");
        const color = tipo === "error" ? "white" : "black";
        cont.innerHTML = `
            <div style="border:4px solid black;box-shadow:4px 4px 0 0 black;background:${bg};color:${color};
                        font-weight:900;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;
                        padding:0.6rem 1rem;">${msg}</div>`;
        cont.classList.remove("hidden");
        clearTimeout(cont._t);
        cont._t = setTimeout(() => cont.classList.add("hidden"), 3500);
    }

    function vibrar() {
        try { navigator.vibrate && navigator.vibrate(60); } catch (_) {}
    }

    // ============================================================
    // RENDER
    // ============================================================

    function render() {
        const lista = $("reab-lista");
        const vacio = $("reab-vacio");
        const btn   = $("reab-btn-confirmar");

        $("reab-contador").textContent = items.length;
        btn.disabled = items.length === 0;
        vacio.classList.toggle("hidden", items.length > 0);

        lista.innerHTML = "";
        items.forEach(item => lista.appendChild(renderRenglon(item)));
    }

    function renderRenglon(item) {
        const div = document.createElement("div");
        div.dataset.rid = item.id;
        div.className = `border-4 border-black shadow-[4px_4px_0_0_black] bg-white p-3 space-y-2 ${item.palomeado ? "opacity-60" : ""}`;

        const foto = item.foto || CTX.noImage;
        const faltan = item.cantidad - item.stockBodega;
        const sinStock = item.stockBodega <= 0;

        div.innerHTML = `
        <div class="flex items-start gap-2">
            <img src="${foto}" loading="lazy"
                 class="w-14 h-14 object-contain border-2 border-black bg-white shrink-0"
                 onerror="this.src='${CTX.noImage}'">
            <div class="flex-1 min-w-0">
                <p class="font-black text-xs uppercase leading-tight break-words">${escapeHtml(item.nombre)}</p>
                <input data-campo="codigo" value="${escapeHtml(item.codigo || "")}"
                       placeholder="sin código"
                       style="font-size:16px;"
                       inputmode="numeric" autocomplete="off"
                       class="mt-1 w-full border-2 border-black px-1.5 py-0.5 text-[11px] font-semibold text-gray-600 outline-none">
            </div>
            <button data-accion="palomear" title="Recolectado"
                    class="shrink-0 w-10 h-10 border-4 border-black font-black text-lg
                           ${item.palomeado ? "bg-[#06D6A0] text-black" : "bg-white text-gray-300"}">✓</button>
        </div>

        <div class="flex items-center gap-2">
            <span class="font-black text-[10px] uppercase tracking-widest text-gray-500">Pido:</span>
            <button data-accion="menos" class="w-10 h-10 border-4 border-black bg-white font-black text-xl leading-none">−</button>
            <input data-campo="cantidad" type="number" min="1" value="${item.cantidad}"
                   style="font-size:16px;" inputmode="numeric"
                   class="w-16 border-4 border-black text-center font-black text-lg py-1 outline-none">
            <button data-accion="mas" class="w-10 h-10 border-4 border-black bg-white font-black text-xl leading-none">+</button>
            <button data-accion="borrar" class="ml-auto w-10 h-10 border-4 border-black bg-[#FF006E] text-white font-black">🗑</button>
        </div>

        <div data-zona="stock"
             class="border-2 border-black px-2 py-1.5 flex justify-between items-center gap-2
                    font-black text-[11px] uppercase tracking-wide
                    ${sinStock ? "bg-[#FF006E] text-white" : "bg-[#06D6A0] text-black"}">
            <span class="truncate">📦 ${escapeHtml(CTX.bodegaNombre)}</span>
            <span class="shrink-0"><span data-campo="stock">${item.stockBodega}</span> pzas
                <span class="reab-dot" title="en vivo">●</span></span>
        </div>

        <div data-zona="warn" class="${faltan > 0 ? "" : "hidden"} border-2 border-black bg-[#FFBE0B] px-2 py-1.5">
            <p class="font-black text-[10px] uppercase leading-snug" data-campo="warn-texto">
                ⚠️ Pides ${item.cantidad} y hay ${item.stockBodega} registradas — al confirmar
                se corregirá bodega <b>+${Math.max(faltan, 0)}</b> a tu nombre.
            </p>
        </div>

        ${item.error ? `
        <div class="border-2 border-black bg-[#FF006E] text-white px-2 py-1.5">
            <p class="font-black text-[10px] uppercase leading-snug">❌ ${escapeHtml(item.error)}</p>
        </div>` : ""}

        <div class="flex items-center gap-2">
            <button data-accion="agregar-inv"
                    class="btn-90s border-2 border-black bg-[#3A86FF] text-white font-black
                           text-[10px] uppercase tracking-wide px-2 py-1.5 whitespace-nowrap">
                ➕ Agregar inv.
            </button>
            <label class="ml-auto flex items-center gap-1.5 font-black text-[10px] uppercase
                          ${item.vaciar ? "text-black" : "text-gray-400"} cursor-pointer select-none">
                <input type="checkbox" data-campo="vaciar" ${item.vaciar ? "checked" : ""}
                       class="w-5 h-5 border-2 border-black accent-black">
                🧹 Ya no quedó nada
            </label>
        </div>`;

        // ---- Eventos del renglón ----
        div.querySelector('[data-accion="palomear"]').onclick = () => {
            item.palomeado = !item.palomeado; guardar(); render();
        };
        div.querySelector('[data-accion="menos"]').onclick = () => {
            if (item.cantidad > 1) { item.cantidad--; guardar(); render(); }
        };
        div.querySelector('[data-accion="mas"]').onclick = () => {
            item.cantidad++; guardar(); render();
        };
        div.querySelector('[data-accion="borrar"]').onclick = () => {
            items = items.filter(i => i.id !== item.id); guardar(); render();
        };
        div.querySelector('[data-campo="cantidad"]').onchange = (e) => {
            const v = parseInt(e.target.value);
            item.cantidad = (isNaN(v) || v < 1) ? 1 : v;
            guardar(); render();
        };
        div.querySelector('[data-campo="vaciar"]').onchange = (e) => {
            item.vaciar = e.target.checked; guardar(); render();
        };
        div.querySelector('[data-accion="agregar-inv"]').onclick = () => abrirModalAgregar(item);
        div.querySelector('[data-campo="codigo"]').onchange = (e) => {
            const nuevo = e.target.value.trim();
            if (nuevo && nuevo !== item.codigo) reasignarCodigo(item, nuevo);
        };

        return div;
    }

    function escapeHtml(s) {
        return String(s ?? "").replace(/[&<>"']/g, c => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[c]));
    }

    // Actualización quirúrgica del stock (WS) — no re-renderiza (no roba el foco)
    function actualizarStockUI(item) {
        const div = document.querySelector(`[data-rid="${item.id}"]`);
        if (!div) return;

        const zonaStock = div.querySelector('[data-zona="stock"]');
        const spanStock = div.querySelector('[data-campo="stock"]');
        if (spanStock) spanStock.textContent = item.stockBodega;
        if (zonaStock) {
            zonaStock.classList.toggle("bg-[#FF006E]", item.stockBodega <= 0);
            zonaStock.classList.toggle("text-white",   item.stockBodega <= 0);
            zonaStock.classList.toggle("bg-[#06D6A0]", item.stockBodega > 0);
            zonaStock.classList.toggle("text-black",   item.stockBodega > 0);
        }

        const faltan = item.cantidad - item.stockBodega;
        const warn = div.querySelector('[data-zona="warn"]');
        if (warn) {
            warn.classList.toggle("hidden", faltan <= 0);
            const txt = warn.querySelector('[data-campo="warn-texto"]');
            if (txt && faltan > 0) {
                txt.innerHTML = `⚠️ Pides ${item.cantidad} y hay ${item.stockBodega} registradas — al confirmar
                                 se corregirá bodega <b>+${faltan}</b> a tu nombre.`;
            }
        }
    }

    // ============================================================
    // AGREGAR PRODUCTOS — por código / por nombre
    // ============================================================

    async function fetchStocks(productoIds) {
        try {
            const r = await fetch(`${CTX.urls.stockGlobal}?ids=${productoIds.join(",")}`);
            return await r.json(); // {pid: {uid: qty}}
        } catch (_) { return {}; }
    }

    async function agregarProducto(prod, codigo) {
        // prod: {producto_id, nombre, foto_url}
        const existente = items.find(i => i.id === prod.producto_id);
        if (existente) {
            existente.cantidad++;
            guardar(); render();
            toast(`+1 ${existente.nombre} (van ${existente.cantidad})`);
            return;
        }

        const stocks = await fetchStocks([prod.producto_id]);
        const porUb = stocks[String(prod.producto_id)] || {};

        items.unshift({
            id:          prod.producto_id,
            nombre:      prod.nombre,
            foto:        prod.foto_url || null,
            codigo:      codigo || "",
            cantidad:    1,
            stockBodega: porUb[String(CTX.bodegaId)] ?? 0,
            stockPiso:   porUb[String(CTX.pisoId)] ?? 0,
            palomeado:   false,
            vaciar:      false,
            error:       "",
        });
        guardar(); render();
        toast(`Agregado: ${prod.nombre}`);
    }

    // pickerMode: null | {tipo:"add", codigo} | {tipo:"replace", rid, codigo}
    let pickerMode = null;

    async function buscarPorCodigo(codigo, modo) {
        try {
            const r = await fetch(`${CTX.urls.buscarCodigo}?codigo=${encodeURIComponent(codigo)}`);
            const data = await r.json();

            if (!data.existe || !data.variantes?.length) {
                toast(`No encontré el código ${codigo}`, "error");
                if (modo?.tipo === "replace") render(); // revierte el input
                return;
            }

            if (data.variantes.length === 1) {
                resolverVariante(data.variantes[0], codigo, modo);
                return;
            }

            // Varias variantes con el mismo código → elegir
            pickerMode = modo || { tipo: "add", codigo };
            pickerMode.codigo = codigo;
            const body = $("reab-variantes-body");
            body.innerHTML = "";
            data.variantes.forEach(v => {
                const atributos = (v.atributos || [])
                    .filter(a => a.valor)
                    .map(a => `${a.nombre}: ${a.valor}`)
                    .join(" · ");
                const opcion = document.createElement("button");
                opcion.type = "button";
                opcion.className = "btn-90s w-full border-4 border-black bg-white p-2 flex items-center gap-2 text-left";
                opcion.innerHTML = `
                    <img src="${v.foto_url || CTX.noImage}" class="w-12 h-12 object-contain border-2 border-black shrink-0"
                         onerror="this.src='${CTX.noImage}'">
                    <span class="min-w-0">
                        <span class="block font-black text-xs uppercase leading-tight">${escapeHtml(v.nombre)}</span>
                        ${atributos ? `<span class="block text-[10px] font-bold text-[#8338EC] leading-tight">${escapeHtml(atributos)}</span>` : ""}
                    </span>`;
                opcion.onclick = () => {
                    $("reab-modal-variantes").classList.add("hidden");
                    resolverVariante(v, pickerMode.codigo, pickerMode);
                    pickerMode = null;
                };
                body.appendChild(opcion);
            });
            $("reab-modal-variantes").classList.remove("hidden");

        } catch (e) {
            console.error("[reab] buscarPorCodigo:", e);
            toast("Error buscando el código", "error");
        }
    }

    async function resolverVariante(v, codigo, modo) {
        if (modo?.tipo === "replace") {
            const item = items.find(i => i.id === modo.rid);
            if (!item) return;
            if (items.some(i => i.id === v.producto_id && i.id !== item.id)) {
                toast("Ese producto ya está en la lista", "warn");
                render();
                return;
            }
            const stocks = await fetchStocks([v.producto_id]);
            const porUb = stocks[String(v.producto_id)] || {};
            item.id          = v.producto_id;
            item.nombre      = v.nombre;
            item.foto        = v.foto_url || null;
            item.codigo      = codigo;
            item.stockBodega = porUb[String(CTX.bodegaId)] ?? 0;
            item.stockPiso   = porUb[String(CTX.pisoId)] ?? 0;
            item.error       = "";
            guardar(); render();
            toast(`Renglón reasignado: ${v.nombre}`);
        } else {
            agregarProducto(v, codigo);
        }
    }

    function reasignarCodigo(item, codigoNuevo) {
        buscarPorCodigo(codigoNuevo, { tipo: "replace", rid: item.id });
    }

    // ---- Input manual de código ----
    $("reab-input-codigo").addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        const codigo = e.target.value.trim();
        if (!codigo) return;
        e.target.value = "";
        buscarPorCodigo(codigo, { tipo: "add" });
    });

    // ---- Búsqueda por nombre (fallback sin código) ----
    let nombreTimer = null;
    const inputNombre = $("reab-input-nombre");
    const dropNombre  = $("reab-nombre-resultados");

    inputNombre.addEventListener("input", () => {
        clearTimeout(nombreTimer);
        const q = inputNombre.value.trim();
        if (q.length < 2) { dropNombre.classList.add("hidden"); return; }
        nombreTimer = setTimeout(() => buscarPorNombre(q), 350);
    });

    async function buscarPorNombre(q) {
        try {
            // Primero en bodega (de ahí se surte); si nada, en piso.
            let r = await fetch(`${CTX.urls.buscarNombre}?q=${encodeURIComponent(q)}&ubicacion=${CTX.bodegaId}`);
            let data = await r.json();
            let resultados = data.resultados || [];

            if (!resultados.length) {
                r = await fetch(`${CTX.urls.buscarNombre}?q=${encodeURIComponent(q)}&ubicacion=${CTX.pisoId}`);
                data = await r.json();
                resultados = data.resultados || [];
            }

            dropNombre.innerHTML = "";
            if (!resultados.length) {
                dropNombre.innerHTML = `<p class="p-3 font-bold text-xs text-gray-400 uppercase text-center">Sin resultados</p>`;
            } else {
                resultados.slice(0, 12).forEach(res => {
                    const b = document.createElement("button");
                    b.type = "button";
                    b.className = "w-full text-left px-3 py-2 border-b-2 border-black/10 font-bold text-xs uppercase hover:bg-[#FFBE0B]";
                    b.textContent = res.nombre;
                    b.onclick = () => {
                        dropNombre.classList.add("hidden");
                        inputNombre.value = "";
                        agregarProducto({ producto_id: res.id, nombre: res.nombre, foto_url: res.foto_url }, "");
                    };
                    dropNombre.appendChild(b);
                });
            }
            dropNombre.classList.remove("hidden");
        } catch (e) {
            console.warn("[reab] buscarPorNombre:", e);
        }
    }

    document.addEventListener("click", (e) => {
        if (!dropNombre.contains(e.target) && e.target !== inputNombre) {
            dropNombre.classList.add("hidden");
        }
    });

    // ============================================================
    // ESCÁNER CONTINUO — cámara global, cooldown por código
    // ============================================================

    let scanner = null;
    let escaneando = false;
    let ultimoCodigoLeido = null;
    let lecturasIguales = 0;
    const LECTURAS_NECESARIAS = 2;
    const COOLDOWN_MS = 2200;
    const cooldown = new Map(); // codigo → timestamp última aceptación

    function checksumUPCA(codigo12) {
        const conPrefijo = "0" + codigo12;
        const base = conPrefijo.slice(0, -1);
        const checkReal = parseInt(conPrefijo.slice(-1), 10);
        let suma = 0;
        for (let i = 0; i < base.length; i++) {
            const n = parseInt(base[i], 10);
            suma += (i % 2 === 0) ? n : n * 3;
        }
        return ((10 - (suma % 10)) % 10) === checkReal;
    }

    function onLectura(codigo) {
        // Normalización UPC-A → EAN-13 (mismo criterio que el escáner global)
        if (/^\d{12}$/.test(codigo) && checksumUPCA(codigo)) codigo = "0" + codigo;

        // Confirmación: 2 lecturas iguales seguidas (filtra falsos positivos)
        if (codigo === ultimoCodigoLeido) lecturasIguales++;
        else { ultimoCodigoLeido = codigo; lecturasIguales = 1; }
        if (lecturasIguales < LECTURAS_NECESARIAS) return;

        // Cooldown: el mismo código dentro de la ventana se ignora
        // (la cámara sigue viendo el código ~1s después del bip)
        const ahora = Date.now();
        if ((ahora - (cooldown.get(codigo) || 0)) < COOLDOWN_MS) return;
        cooldown.set(codigo, ahora);
        lecturasIguales = 0;

        vibrar();
        flashCamara();
        buscarPorCodigo(codigo, { tipo: "add" });
    }

    function flashCamara() {
        const box = $("reab-camara");
        box.style.outline = "6px solid #06D6A0";
        setTimeout(() => { box.style.outline = ""; }, 250);
    }

    async function toggleCamara() {
        if (escaneando) { await detenerCamara(); return; }

        const Lib = window.__Html5QrcodeLibrary__?.Html5Qrcode;
        if (!Lib) { toast("La librería de cámara no cargó. Recarga.", "error"); return; }

        const esLocal = ["localhost", "127.0.0.1"].includes(location.hostname);
        if (!esLocal && location.protocol !== "https:") {
            toast("📵 La cámara solo funciona en HTTPS", "error");
            return;
        }

        $("reab-camara-box").classList.remove("hidden");
        $("reab-camara").innerHTML = "";
        scanner = new Lib("reab-camara");

        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
            || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
        const F = window.__Html5QrcodeLibrary__?.Html5QrcodeSupportedFormats;
        const config = {
            fps: isIOS ? 8 : 15,
            qrbox: { width: 310, height: 150 },
            formatsToSupport: F ? [
                F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E,
                F.CODE_128, F.CODE_39, F.QR_CODE,
            ] : undefined,
            experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        };

        try {
            await scanner.start({ facingMode: "environment" }, config, onLectura, () => {});
        } catch (_) {
            try {
                await scanner.start({ facingMode: "user" }, config, onLectura, () => {});
            } catch (e2) {
                toast("❌ Sin acceso a la cámara", "error");
                $("reab-camara-box").classList.add("hidden");
                scanner = null;
                return;
            }
        }

        escaneando = true;
        $("reab-btn-camara").textContent = "⏹ Detener";
        inyectarControlesCamara(isIOS);
    }

    async function detenerCamara() {
        if (scanner && escaneando) {
            try { await scanner.stop(); scanner.clear(); } catch (_) {}
        }
        scanner = null;
        escaneando = false;
        ultimoCodigoLeido = null;
        lecturasIguales = 0;
        $("reab-camara-box").classList.add("hidden");
        $("reab-btn-camara").textContent = "📷 Escanear";
        document.getElementById("reab-escaner-controles")?.remove();
    }

    // Linterna + zoom ×2 (etiquetas chicas) — no disponibles en iOS Safari
    function inyectarControlesCamara(isIOS) {
        if (isIOS) return;
        document.getElementById("reab-escaner-controles")?.remove();

        const bar = document.createElement("div");
        bar.id = "reab-escaner-controles";
        bar.style.cssText = "display:flex;gap:.5rem;margin-top:.4rem;";
        const estilo = (bg, color) =>
            `background:${bg};color:${color};flex:1;border:3px solid black;box-shadow:3px 3px 0 0 black;` +
            `font-weight:900;font-size:.68rem;text-transform:uppercase;letter-spacing:.05em;padding:.35rem .5rem;cursor:pointer;`;

        let torch = false, zoom = false;

        const btnTorch = document.createElement("button");
        btnTorch.type = "button";
        btnTorch.textContent = "🔦 Linterna";
        btnTorch.style.cssText = estilo("#FFBE0B", "#000");
        btnTorch.onclick = () => {
            torch = !torch;
            scanner?.applyVideoConstraints({ advanced: [{ torch }] }).catch(() => { torch = false; });
            btnTorch.textContent = torch ? "🔦 ON" : "🔦 Linterna";
        };

        const btnZoom = document.createElement("button");
        btnZoom.type = "button";
        btnZoom.textContent = "🔍 Etiqueta chica";
        btnZoom.style.cssText = estilo("#3A86FF", "#fff");
        btnZoom.onclick = () => {
            zoom = !zoom;
            scanner?.applyVideoConstraints({ advanced: [{ zoom: zoom ? 2 : 1 }] }).catch(() => { zoom = false; });
            btnZoom.textContent = zoom ? "🔍 ×2 ON" : "🔍 Etiqueta chica";
        };

        bar.appendChild(btnTorch);
        bar.appendChild(btnZoom);
        $("reab-camara").insertAdjacentElement("afterend", bar);
    }

    $("reab-btn-camara").addEventListener("click", toggleCamara);

    // ============================================================
    // WEBSOCKET — stock de bodega interna en vivo
    // ============================================================

    function conectarWS() {
        const proto = location.protocol === "https:" ? "wss:" : "ws:";
        const ws = new WebSocket(`${proto}//${location.host}/ws/inventario/${CTX.bodegaId}/`);

        ws.onmessage = (e) => {
            const msg = JSON.parse(e.data);

            if (msg.tipo === "producto_update") {
                const item = items.find(i => i.id === parseInt(msg.producto_id));
                if (item && msg.nombre) { item.nombre = msg.nombre; guardar(); render(); }
                return;
            }

            // stock_update
            if (parseInt(msg.ubicacion_id) !== CTX.bodegaId) return;
            const item = items.find(i => i.id === parseInt(msg.producto_id));
            if (!item) return;
            item.stockBodega = msg.cantidad_actual;
            guardar();
            actualizarStockUI(item);  // quirúrgico: no roba el foco
            console.log(`[reab] WS stock → id=${item.id} bodega=${item.stockBodega}`);
        };

        ws.onclose = () => setTimeout(conectarWS, 5000);
    }

    // ============================================================
    // MODAL: AGREGAR INVENTARIO A BODEGA INTERNA
    // ============================================================

    let itemAgregar = null;

    function abrirModalAgregar(item) {
        itemAgregar = item;
        $("reab-agregar-nombre").textContent = item.nombre;
        $("reab-agregar-cantidad").value = 1;
        $("reab-modal-agregar").classList.remove("hidden");
    }

    $("reab-agregar-cerrar").onclick = () => $("reab-modal-agregar").classList.add("hidden");

    $("reab-agregar-guardar").onclick = async () => {
        if (!itemAgregar) return;
        const cantidad = parseInt($("reab-agregar-cantidad").value);
        if (isNaN(cantidad) || cantidad < 1) { toast("Cantidad inválida", "error"); return; }

        const btn = $("reab-agregar-guardar");
        btn.disabled = true;

        try {
            const fd = new FormData();
            fd.append("cantidad", cantidad);
            fd.append("csrfmiddlewaretoken", getCSRF());
            fd.append("idempotency_key", uuid());

            const r = await fetch(`${CTX.urls.agregarBase}${itemAgregar.id}/${CTX.bodegaId}/`, {
                method: "POST",
                headers: { "X-Requested-With": "XMLHttpRequest" },
                body: fd,
            });
            const data = await r.json();

            if (data.success) {
                itemAgregar.stockBodega = data.cantidad_actual;
                guardar();
                actualizarStockUI(itemAgregar);
                $("reab-modal-agregar").classList.add("hidden");
                toast(`✅ Bodega actualizada: ${data.cantidad_actual} pzas`);
            } else {
                toast((data.errors || ["Error al agregar"]).join(" "), "error");
            }
        } catch (e) {
            toast("Error de red al agregar", "error");
        } finally {
            btn.disabled = false;
        }
    };

    // ============================================================
    // CONFIRMAR ORDEN — resumen → ejecutar → resultados
    // ============================================================

    $("reab-btn-confirmar").addEventListener("click", () => {
        if (!items.length) return;

        const piezas = items.reduce((a, i) => a + i.cantidad, 0);
        const ajustes = items.filter(i => i.cantidad > i.stockBodega);
        const vaciados = items.filter(i => i.vaciar);
        const sinPalomear = items.filter(i => !i.palomeado).length;

        let html = `
            <p class="font-black text-sm uppercase">${items.length} renglones · ${piezas} piezas</p>
            <p class="font-bold text-[11px] text-gray-500 uppercase">
                ${CTX.bodegaNombre} → ${CTX.pisoNombre}
            </p>`;

        if (sinPalomear > 0) {
            html += `<p class="border-2 border-black bg-gray-100 px-2 py-1 font-bold text-[10px] uppercase">
                📝 ${sinPalomear} renglón(es) sin palomear — se transfieren igual.</p>`;
        }
        ajustes.forEach(i => {
            html += `<p class="border-2 border-black bg-[#FFBE0B] px-2 py-1 font-bold text-[10px] uppercase">
                ⚠️ ${escapeHtml(i.nombre)}: corregirá bodega +${i.cantidad - i.stockBodega}</p>`;
        });
        vaciados.forEach(i => {
            html += `<p class="border-2 border-black bg-[#CCFF00] px-2 py-1 font-bold text-[10px] uppercase">
                🧹 ${escapeHtml(i.nombre)}: bodega quedará en 0</p>`;
        });

        $("reab-resumen-body").innerHTML = html;
        $("reab-modal-resumen").classList.remove("hidden");
    });

    $("reab-resumen-cancelar").onclick = () => $("reab-modal-resumen").classList.add("hidden");

    $("reab-resumen-confirmar").onclick = async () => {
        const btn = $("reab-resumen-confirmar");
        btn.disabled = true;
        btn.textContent = "Procesando…";

        try {
            const payload = {
                piso_id:   CTX.pisoId,
                bodega_id: CTX.bodegaId,
                renglones: items.map(i => ({
                    producto_id:   i.id,
                    cantidad:      i.cantidad,
                    vaciar_bodega: i.vaciar,
                })),
                idempotency_key: uuid(),
            };

            const r = await fetch(CTX.urls.confirmar, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRF(),
                },
                body: JSON.stringify(payload),
            });
            const data = await r.json();

            $("reab-modal-resumen").classList.add("hidden");

            if (!data.success) {
                toast((data.errors || ["Error al confirmar"]).join(" "), "error");
                return;
            }

            // Quitar los exitosos; marcar error en los fallidos
            const fallidosPorId = {};
            (data.resultados || []).forEach(res => {
                if (!res.ok) fallidosPorId[res.producto_id] = res.error || "Error desconocido";
            });

            items = items.filter(i => {
                if (fallidosPorId[i.id] !== undefined) {
                    i.error = fallidosPorId[i.id];
                    return true;
                }
                return false;
            });
            guardar(); render();

            if (data.exitosos === data.total) {
                toast(`🎉 Orden completa: ${data.exitosos} producto(s) ya están en piso`);
                try { localStorage.removeItem(LS_KEY); } catch (_) {}
            } else {
                toast(`${data.exitosos}/${data.total} transferidos — revisa los marcados en rojo`, "warn");
            }

        } catch (e) {
            console.error("[reab] confirmar:", e);
            toast("Error de red al confirmar. La lista sigue guardada.", "error");
        } finally {
            btn.disabled = false;
            btn.textContent = "🚀 Ejecutar";
        }
    };

    // ---- Cerrar modales con click en el fondo ----
    ["reab-modal-resumen", "reab-modal-variantes", "reab-modal-agregar"].forEach(id => {
        $(id).addEventListener("click", (e) => {
            if (e.target === $(id)) $(id).classList.add("hidden");
        });
    });
    $("reab-variantes-cerrar").onclick = () => {
        $("reab-modal-variantes").classList.add("hidden");
        pickerMode = null;
        render();
    };

    // ============================================================
    // INIT — restaurar borrador + refrescar stocks + WS
    // ============================================================

    (async function init() {
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (raw) items = JSON.parse(raw) || [];
        } catch (_) { items = []; }

        render();

        if (items.length) {
            // Refrescar stocks del borrador (pudieron cambiar mientras tanto)
            const stocks = await fetchStocks(items.map(i => i.id));
            items.forEach(i => {
                const porUb = stocks[String(i.id)] || {};
                i.stockBodega = porUb[String(CTX.bodegaId)] ?? 0;
                i.stockPiso   = porUb[String(CTX.pisoId)] ?? 0;
            });
            guardar(); render();
            toast(`Borrador restaurado: ${items.length} renglón(es)`, "warn");
        }

        conectarWS();
        console.log("[reab] init OK — bodega:", CTX.bodegaId, "piso:", CTX.pisoId);
    })();

})();
