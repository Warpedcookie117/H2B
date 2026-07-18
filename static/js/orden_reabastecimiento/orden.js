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
    //           palomeado, vaciar, error, color}]
    let items = [];

    // Paleta 90s del resto de la app — acento de color por renglón, asignado
    // UNA vez al crear el renglón (no recalculado por posición, para que no
    // "brinquen" de color al borrar otros renglones de la lista).
    const CARD_COLORS = ["#FFBE0B", "#FF006E", "#3A86FF", "#8338EC", "#06D6A0", "#CCFF00"];
    let colorSeq = 0;
    function siguienteColor() {
        return CARD_COLORS[(colorSeq++) % CARD_COLORS.length];
    }

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
        const contador = $("reab-contador");

        if (contador.textContent !== String(items.length)) {
            contador.textContent = items.length;
            contador.classList.remove("reab-pop");
            void contador.offsetWidth; // reflow: reinicia la animación
            contador.classList.add("reab-pop");
        }
        btn.disabled = items.length === 0;
        $("reab-btn-pdf").disabled = items.length === 0;
        vacio.classList.toggle("hidden", items.length > 0);

        lista.innerHTML = "";
        items.forEach(item => lista.appendChild(renderRenglon(item)));
    }

    function renderRenglon(item) {
        if (!item.color) item.color = siguienteColor(); // borradores viejos sin color asignado

        const div = document.createElement("div");
        div.dataset.rid = item.id;
        div.className = `border-4 border-black shadow-[4px_4px_0_0_black] bg-white p-3 space-y-2 ${item.palomeado ? "opacity-60" : ""}`;
        div.style.borderTop = `8px solid ${item.color}`;
        div.style.backgroundColor = `${item.color}14`; // ~8% opacidad — tinte sutil, texto sigue legible

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
                <p class="mt-1 text-[11px] font-mono font-semibold truncate ${item.codigo ? "text-gray-600" : "text-gray-400 italic"}">
                    ${item.codigo ? escapeHtml(item.codigo) : "sin código"}
                </p>
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
            <p class="font-bold text-[11px] leading-snug" data-campo="warn-texto">${textoAdvertencia(item)}</p>
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

        return div;
    }

    function escapeHtml(s) {
        return String(s ?? "").replace(/[&<>"']/g, c => ({
            "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
        }[c]));
    }

    // Mensaje del banner de advertencia — en cristiano, para quien sea.
    // Dos casos: el producto NI EXISTE registrado en bodega, o pides más
    // de lo que el sistema tiene anotado.
    function textoAdvertencia(item) {
        const faltan = item.cantidad - item.stockBodega;
        if (item.stockBodega <= 0) {
            return `⚠️ Pides <b>${item.cantidad}</b> pero este producto NI EXISTE en la bodega
                    (según el sistema 🙄). Al confirmar se corrige solito, a tu nombre.
                    Ojo: si SÍ hay en bodega, cuéntalas y pícale a <b>➕ AGREGAR INV.</b> —
                    pa' que no la cuenten doble.`;
        }
        return `⚠️ Pides <b>${item.cantidad}</b> y solo hay <b>${item.stockBodega}</b> anotadas, pa.
                Al confirmar, el sistema corrige el <b>+${faltan}</b> solito, a tu nombre.
                ¿Encontraste más? Cuéntalas y pícale a <b>➕ AGREGAR INV.</b>`;
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
                txt.innerHTML = textoAdvertencia(item);
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
            color:       siguienteColor(),
        });
        guardar(); render();
        toast(`Agregado: ${prod.nombre}`);
    }

    // Un término, dos intentos: primero como CÓDIGO exacto (escaneo/pistola);
    // si no coincide, como NOMBRE (sugerencias). El empleado no tiene que
    // saber cuál es cuál — el sistema resuelve solo.
    async function buscarProducto(termino) {
        try {
            const r = await fetch(`${CTX.urls.buscarCodigo}?codigo=${encodeURIComponent(termino)}`);
            const data = await r.json();

            if (!data.existe || !data.variantes?.length) {
                // No es un código registrado → intentarlo como nombre
                const encontrados = await buscarPorNombre(termino);
                if (!encontrados) toast(`No encontré nada con "${termino}"`, "error");
                return;
            }

            const codigo = termino;
            inputCodigo.value = "";
            ocultarSugerencias();

            if (data.variantes.length === 1) {
                agregarProducto(data.variantes[0], codigo);
                return;
            }

            // Varias variantes con el mismo código → elegir
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
                    agregarProducto(v, codigo);
                };
                body.appendChild(opcion);
            });
            $("reab-modal-variantes").classList.remove("hidden");

        } catch (e) {
            console.error("[reab] buscarProducto:", e);
            toast("Error buscando el producto", "error");
        }
    }

    // ============================================================
    // CAPTURA UNIFICADA — un solo campo para código O nombre.
    // Pistola física: "teclea" el código y remata con Enter — fallbacks
    // keyup (Android Chrome a veces no dispara keydown con Enter) y
    // change (pistolas Bluetooth que terminan con Tab/blur).
    // ============================================================

    const inputCodigo = $("reab-input-codigo");
    const dropNombre  = $("reab-nombre-resultados");
    let nombreTimer = null;

    function ocultarSugerencias() {
        dropNombre.classList.add("hidden");
    }

    function procesarEntrada() {
        const termino = inputCodigo.value.trim();
        if (!termino) return;
        clearTimeout(nombreTimer);
        buscarProducto(termino);
    }

    inputCodigo.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); procesarEntrada(); }
    });
    inputCodigo.addEventListener("keyup", (e) => {
        if (e.key === "Enter" || e.keyCode === 13) procesarEntrada();
    });
    // Pistolas que rematan con Tab/blur: solo si las sugerencias están
    // cerradas — si están abiertas, el usuario está tecleando un nombre y
    // el blur de picarle a una sugerencia no debe disparar otra búsqueda.
    inputCodigo.addEventListener("change", () => {
        if (dropNombre.classList.contains("hidden")) procesarEntrada();
    });

    // Sugerencias por nombre en vivo mientras teclea (debounce 350ms).
    // La pistola teclea tan rápido que el debounce nunca alcanza a disparar.
    inputCodigo.addEventListener("input", () => {
        clearTimeout(nombreTimer);
        const q = inputCodigo.value.trim();
        if (q.length < 2) { ocultarSugerencias(); return; }
        nombreTimer = setTimeout(() => buscarPorNombre(q), 350);
    });

    // Teclas globales → foco al campo: la pistola funciona desde cualquier
    // parte de la página sin picarle al campo primero. NO roba el foco si ya
    // estás en otro campo (cantidades, modales) — mismo patrón que el POS.
    document.addEventListener("keydown", (e) => {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab", "Escape", "Enter",
             "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
             "F1", "F2", "F3", "F4", "F5", "F6",
             "F7", "F8", "F9", "F10", "F11", "F12"].includes(e.key)) return;
        inputCodigo.value = "";
        ocultarSugerencias();
        inputCodigo.focus();
    });

    // Busca por nombre, pinta las sugerencias y devuelve cuántas encontró
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
                        ocultarSugerencias();
                        inputCodigo.value = "";
                        agregarProducto(
                            { producto_id: res.id, nombre: res.nombre, foto_url: res.foto_url },
                            res.codigo_barras || ""
                        );
                    };
                    dropNombre.appendChild(b);
                });
            }
            dropNombre.classList.remove("hidden");
            return resultados.length;
        } catch (e) {
            console.warn("[reab] buscarPorNombre:", e);
            return 0;
        }
    }

    document.addEventListener("click", (e) => {
        if (!dropNombre.contains(e.target) && e.target !== inputCodigo) {
            ocultarSugerencias();
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

    function checksumEAN13(c) {
        if (!/^\d{13}$/.test(c)) return false;
        let suma = 0;
        for (let i = 0; i < 12; i++) {
            suma += parseInt(c[i], 10) * (i % 2 === 0 ? 1 : 3);
        }
        return ((10 - (suma % 10)) % 10) === parseInt(c[12], 10);
    }

    // Traduce el error real de getUserMedia — "sin acceso" a secas no dice si
    // fue permiso denegado, cámara ocupada o dispositivo sin cámara. Con el
    // nombre del error, el arreglo es directo en vez de adivinar.
    function mensajeErrorCamara(e) {
        const n = e && e.name;
        if (n === "NotAllowedError")
            return "🚫 El navegador tiene BLOQUEADO el permiso de cámara para este sitio — actívalo en los ajustes del sitio y reintenta";
        if (n === "NotFoundError")
            return "❌ Este dispositivo no tiene cámara disponible";
        if (n === "NotReadableError")
            return "⚠️ La cámara está ocupada por otra app o pestaña — ciérrala y reintenta";
        return `❌ Sin acceso a la cámara (${n || e || "error desconocido"})`;
    }

    // Enfoque continuo directo sobre el track de getUserMedia. NO usa el
    // applyVideoConstraints de html5-qrcode: ese reinicia el stream completo
    // y provoca el "doble arranque" (cámara inicia → reinicia → recién lee).
    function enfocarContinuo(contenedorId) {
        try {
            const video = document.querySelector(`#${contenedorId} video`);
            const track = video && video.srcObject && video.srcObject.getVideoTracks()[0];
            if (track) track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
        } catch (_) {}
    }

    function onLectura(codigo) {
        // Normalización UPC-A → EAN-13 (mismo criterio que el escáner global)
        if (/^\d{12}$/.test(codigo) && checksumUPCA(codigo)) codigo = "0" + codigo;

        // Anti-falsos-positivos: los EAN-13/UPC-A con dígito verificador
        // VÁLIDO se aceptan a la PRIMERA lectura (el checksum ya garantiza
        // que no fue lectura chueca) — el resto necesita 2 lecturas iguales.
        const necesarias = checksumEAN13(codigo) ? 1 : LECTURAS_NECESARIAS;
        if (codigo === ultimoCodigoLeido) lecturasIguales++;
        else { ultimoCodigoLeido = codigo; lecturasIguales = 1; }
        if (lecturasIguales < necesarias) return;

        // Cooldown: el mismo código dentro de la ventana se ignora
        // (la cámara sigue viendo el código ~1s después del bip)
        const ahora = Date.now();
        if ((ahora - (cooldown.get(codigo) || 0)) < COOLDOWN_MS) return;
        cooldown.set(codigo, ahora);
        lecturasIguales = 0;

        vibrar();
        flashCamara();

        // El código leído "cae" en el campo de captura — mismo campo,
        // mismo camino, tanto si lo tecleas como si lo escaneas.
        inputCodigo.value = codigo;
        buscarProducto(codigo);
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
            disableFlip: true, // cámara trasera: sin espejo, decode más rápido por cuadro
            formatsToSupport: F ? [
                F.EAN_13, F.EAN_8, F.UPC_A, F.UPC_E,
                F.CODE_128, F.CODE_39, F.QR_CODE,
            ] : undefined,
            experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        };

        // Arranque simple: la librería extrae SOLO facingMode/deviceId del
        // primer parámetro y descarta cualquier otra clave (verificado en el
        // código minificado) — no tiene caso pasar más constraints aquí.
        try {
            await scanner.start({ facingMode: "environment" }, config, onLectura, () => {});
        } catch (_) {
            try {
                await scanner.start({ facingMode: "user" }, config, onLectura, () => {});
            } catch (e2) {
                toast(mensajeErrorCamara(e2), "error");
                $("reab-camara-box").classList.add("hidden");
                scanner = null;
                return;
            }
        }

        // Enfoque continuo DIRECTO sobre el track de video — en caliente, sin
        // pasar por applyVideoConstraints de la librería (esa detiene y
        // reinicia el stream: era el "doble arranque" visible antes de poder
        // leer). Si el navegador no soporta focusMode, lo ignora y ya.
        enfocarContinuo("reab-camara");

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
    // COMPARTIR PDF — lista de surtido (foto + nombre + código + cantidad).
    // Solo genera el PDF; NO toca inventario ni ejecuta la orden.
    // ============================================================

    $("reab-btn-pdf").addEventListener("click", async () => {
        if (!items.length) return;

        const btn = $("reab-btn-pdf");
        const textoOriginal = btn.textContent;
        btn.disabled = true;
        btn.textContent = "Generando PDF…";

        try {
            const payload = {
                piso_id:   CTX.pisoId,
                bodega_id: CTX.bodegaId,
                renglones: items.map(i => ({ producto_id: i.id, cantidad: i.cantidad })),
            };

            const r = await fetch(CTX.urls.pdf, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCSRF(),
                },
                body: JSON.stringify(payload),
            });

            if (!r.ok) {
                toast("No se pudo generar el PDF", "error");
                return;
            }

            const blob = await r.blob();
            const nombreArchivo = `lista_surtido_${Date.now()}.pdf`;
            const archivo = new File([blob], nombreArchivo, { type: "application/pdf" });

            // Web Share API con archivo → hoja nativa de compartir (WhatsApp, etc.)
            // Si el navegador no lo soporta, se descarga el PDF como respaldo.
            if (navigator.canShare && navigator.canShare({ files: [archivo] })) {
                await navigator.share({
                    files: [archivo],
                    title: "Lista de surtido",
                    text: `${CTX.bodegaNombre} → ${CTX.pisoNombre}`,
                });
            } else {
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = nombreArchivo;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 10000);
            }
        } catch (e) {
            // El usuario cancelando la hoja de compartir también cae aquí (AbortError) — no es un error real.
            if (e.name !== "AbortError") {
                console.error("[reab] compartir PDF:", e);
                toast("Error al compartir el PDF", "error");
            }
        } finally {
            btn.disabled = items.length === 0;
            btn.textContent = textoOriginal;
        }
    });

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
    };

    // ============================================================
    // INIT — restaurar borrador + refrescar stocks + WS
    // ============================================================

    (async function init() {
        try {
            const raw = localStorage.getItem(LS_KEY);
            if (raw) items = JSON.parse(raw) || [];
        } catch (_) { items = []; }

        colorSeq = items.length; // continúa la secuencia de colores tras restaurar
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
