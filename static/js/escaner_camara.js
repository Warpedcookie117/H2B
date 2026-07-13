// ============================
// ESCÁNER DE CÁMARA — compartido entre vistas
// Expone window.initEscanerCamara(onDetectado)
// Html5Qrcode global desde /static/js/html5-qrcode.min.js
// ============================

function initEscanerCamara(onDetectado) {

    const btnAbrir  = document.getElementById("btn-escanear-camara");
    const modal     = document.getElementById("modal-camara");
    const btnCerrar = document.getElementById("btn-cerrar-camara");
    const reader    = document.getElementById("camara-reader");

    if (!btnAbrir || !modal || !btnCerrar || !reader) return;

    let scanner = null;
    let activo  = false;

    // ============================
    // ABRIR / CERRAR MODAL
    // ============================
    btnAbrir.addEventListener("click", () => {
        modal.showModal();
        iniciar();
    });

    btnCerrar.addEventListener("click", cerrarModal);

    modal.addEventListener("click", (e) => {
        if (e.target === modal) cerrarModal();
    });

    function cerrarModal() {
        detener().then(() => modal.close());
    }

    // ============================
    // CALLBACK: código escaneado
    // Buffer de confirmación: el mismo código debe leerse 2 veces seguidas
    // antes de aceptarlo. Suma ~130ms en Android (15fps) o ~250ms en iOS (8fps)
    // pero filtra los falsos positivos del decoder cuando ve un código parcial.
    // ============================
    let ultimoCodigoLeido = null;
    let lecturasIguales = 0;
    const LECTURAS_NECESARIAS = 2;

    // Valida checksum UPC-A (12 dígitos). El algoritmo es idéntico al de
    // EAN-13 cuando se prepende un "0" — eso permite tratar UPC-A como
    // EAN-13 con leading zero según el estándar GS1 (GTIN-13).
    function _checksumUPCA(codigo12) {
        const conPrefijo = "0" + codigo12;
        const base = conPrefijo.slice(0, -1);
        const checkReal = parseInt(conPrefijo.slice(-1), 10);
        let suma = 0;
        for (let i = 0; i < base.length; i++) {
            const n = parseInt(base[i], 10);
            suma += (i % 2 === 0) ? n : n * 3;
        }
        const checkCalc = (10 - (suma % 10)) % 10;
        return checkCalc === checkReal;
    }

    function onEscaneado(codigo) {
        // Normalización GTIN-13 en el momento del escaneo: si las barras
        // codifican UPC-A (12 dígitos con checksum válido), prepende el "0"
        // que la etiqueta SÍ muestra impreso pero las barras no codifican.
        // Esto hace que el input muestre el código completo tal como el
        // usuario lo ve en la etiqueta.
        if (/^\d{12}$/.test(codigo) && _checksumUPCA(codigo)) {
            console.log(`[escaner] UPC-A detectado → normalizado a EAN-13: 0${codigo}`);
            codigo = "0" + codigo;
        }

        if (codigo === ultimoCodigoLeido) {
            lecturasIguales++;
        } else {
            ultimoCodigoLeido = codigo;
            lecturasIguales = 1;
        }

        if (lecturasIguales < LECTURAS_NECESARIAS) {
            console.log(`[escaner] Lectura ${lecturasIguales}/${LECTURAS_NECESARIAS}: ${codigo} (esperando confirmación)`);
            return;
        }

        console.log(`[escaner] ✅ Confirmado tras ${lecturasIguales} lecturas:`, codigo);
        detener().then(() => {
            modal.close();
            onDetectado(codigo);
        });
    }

    // ============================
    // INICIAR CÁMARA
    // ============================
    function iniciar() {
        if (activo) return;

        const Lib = window.__Html5QrcodeLibrary__?.Html5Qrcode;
        if (!Lib) {
            mostrarError("❌ Librería no cargó. Recarga la página.");
            console.error("[escaner] window.__Html5QrcodeLibrary__ es undefined");
            return;
        }

        const esLocalhost = location.hostname === "localhost" || location.hostname === "127.0.0.1";
        const esHttps     = location.protocol === "https:";
        if (!esLocalhost && !esHttps) {
            mostrarError("📵 Cámara solo disponible en HTTPS.");
            console.warn("[escaner] Bloqueado: protocolo es", location.protocol);
            return;
        }

        console.log("[escaner] Iniciando con cámara trasera...");

        reader.innerHTML = "";
        scanner = new Lib("camara-reader");

        // iOS no tiene BarcodeDetector nativo → usa JS puro → más lento.
        // Bajamos fps y pedimos 720p para que el decodificador procese menos píxeles.
        const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
            || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

        const F = window.__Html5QrcodeLibrary__?.Html5QrcodeSupportedFormats;
        const config = {
            fps: isIOS ? 8 : 15,
            qrbox: { width: 310, height: 150 },
            disableFlip: true, // cámara trasera: sin espejo, evita el doble intento de decode por cuadro
            formatsToSupport: F ? [
                F.EAN_13, F.EAN_8,
                F.UPC_A,  F.UPC_E,
                F.CODE_128, F.CODE_39,
                F.QR_CODE,
            ] : undefined,
            experimentalFeatures: { useBarCodeDetectorIfSupported: true },
        };

        // Arranque simple, sin advanced constraints en la negociación inicial
        // (reintentar .start() con constraints distintas sobre la MISMA instancia
        // dejaba el scanner en un estado roto en algunos navegadores — por eso
        // "sin acceso a la cámara"). El enfoque continuo se pide APARTE, después,
        // ya con la cámara abierta — eso nunca puede tumbar el acceso.
        scanner.start({ facingMode: "environment" }, config, onEscaneado, () => {})
        .then(() => {
            activo = true;
            console.log(`[escaner] Cámara trasera OK (iOS=${isIOS}, fps=${config.fps})`);
            if (!isIOS) scanner.applyVideoConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
            inyectarControles();
        })
        .catch((errEnv) => {
            console.warn("[escaner] Cámara trasera falló:", errEnv, "— intentando frontal...");
            scanner.start({ facingMode: "user" }, config, onEscaneado, () => {})
            .then(() => {
                activo = true;
                console.log("[escaner] Cámara frontal OK");
                inyectarControles();
            })
            .catch((errUser) => {
                console.error("[escaner] Ambas cámaras fallaron:", errUser);
                mostrarError("❌ Sin acceso a cámara.\n" + errUser);
            });
        });
    }

    // ============================
    // CONTROLES: LINTERNA + ZOOM ETIQUETA PEQUEÑA
    // Se inyectan después del reader para no tocar los templates.
    // ============================
    let torchActivo = false;
    let zoomActivo  = false;

    function inyectarControles() {
        // torch y zoom no están disponibles en iOS Safari — no mostrar botones.
        if (isIOS) return;

        document.getElementById("escaner-controles")?.remove();

        const bar = document.createElement("div");
        bar.id = "escaner-controles";
        bar.style.cssText = "display:flex;gap:.5rem;margin-top:.5rem;";

        // Botón linterna
        const btnTorch = document.createElement("button");
        btnTorch.type = "button";
        btnTorch.textContent = "🔦 Linterna";
        btnTorch.style.cssText = _estiloBtn("#FFBE0B", "#000");
        btnTorch.addEventListener("click", () => {
            torchActivo = !torchActivo;
            scanner?.applyVideoConstraints({ advanced: [{ torch: torchActivo }] })
                .catch(() => { torchActivo = false; });
            btnTorch.textContent  = torchActivo ? "🔦 Linterna ON" : "🔦 Linterna";
            btnTorch.style.background = torchActivo ? "#06D6A0" : "#FFBE0B";
        });

        // Botón zoom ×2 — para etiquetas muy pequeñas como las de 5mm
        const btnZoom = document.createElement("button");
        btnZoom.type = "button";
        btnZoom.textContent = "🔍 Etiqueta pequeña";
        btnZoom.style.cssText = _estiloBtn("#3A86FF", "#fff");
        btnZoom.addEventListener("click", () => {
            zoomActivo = !zoomActivo;
            // zoom:2 acerca el video ×2 — duplica los píxeles por barra del código
            scanner?.applyVideoConstraints({ advanced: [{ zoom: zoomActivo ? 2 : 1 }] })
                .catch(() => { zoomActivo = false; });
            btnZoom.textContent   = zoomActivo ? "🔍 Zoom ×2 ON" : "🔍 Etiqueta pequeña";
            btnZoom.style.background = zoomActivo ? "#FF006E" : "#3A86FF";
        });

        bar.appendChild(btnTorch);
        bar.appendChild(btnZoom);
        reader.insertAdjacentElement("afterend", bar);
    }

    function _estiloBtn(bg, color) {
        return [
            `background:${bg}`,
            `color:${color}`,
            "flex:1",
            "border:3px solid black",
            "box-shadow:3px 3px 0 0 black",
            "font-weight:900",
            "font-size:.72rem",
            "text-transform:uppercase",
            "letter-spacing:.05em",
            "padding:.35rem .5rem",
            "cursor:pointer",
        ].join(";");
    }

    // ============================
    // ERROR VISIBLE (solo errores fatales)
    // ============================
    function mostrarError(msg) {
        reader.innerHTML = `
            <div style="padding:1.5rem;text-align:center;font-weight:700;font-size:0.85rem;
                        color:#fff;background:#FF006E;border:3px solid black;white-space:pre-line;">
                ${msg}
            </div>`;
    }

    // ============================
    // DETENER CÁMARA
    // ============================
    async function detener() {
        if (scanner && activo) {
            try {
                await scanner.stop();
                scanner.clear();
            } catch (_) {}
            scanner = null;
            activo  = false;
            torchActivo = false;
            zoomActivo  = false;
            ultimoCodigoLeido = null;
            lecturasIguales = 0;
            document.getElementById("escaner-controles")?.remove();
            console.log("[escaner] Cámara detenida.");
        }
    }
}
