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

    // iOS no tiene BarcodeDetector nativo → JS puro, más lento. Se decide UNA
    // vez aquí porque lo usan tanto iniciar() como inyectarControles() — si se
    // declara dentro de iniciar(), inyectarControles() no la alcanza
    // (ReferenceError) y el catch lo confunde con "cámara falló".
    const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent)
        || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

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

    // Checksum EAN-13 completo — un código que lo pasa NO puede ser una
    // lectura chueca del decoder, así que basta UNA sola lectura.
    function _checksumEAN13(c) {
        if (!/^\d{13}$/.test(c)) return false;
        let suma = 0;
        for (let i = 0; i < 12; i++) {
            suma += parseInt(c[i], 10) * (i % 2 === 0 ? 1 : 3);
        }
        return ((10 - (suma % 10)) % 10) === parseInt(c[12], 10);
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

        // EAN-13/UPC-A con checksum válido → aceptar a la PRIMERA lectura
        // (mitad del tiempo de espera). El resto (Code128, QR, lecturas con
        // checksum roto) sigue necesitando 2 lecturas iguales seguidas.
        const necesarias = _checksumEAN13(codigo) ? 1 : LECTURAS_NECESARIAS;

        if (lecturasIguales < necesarias) {
            console.log(`[escaner] Lectura ${lecturasIguales}/${necesarias}: ${codigo} (esperando confirmación)`);
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

        // Enfoque continuo DIRECTO sobre el track de video — en caliente, sin
        // el applyVideoConstraints de la librería (ese detiene y reinicia el
        // stream: era el "doble arranque" visible antes de poder leer).
        function enfocarContinuo() {
            try {
                const video = reader.querySelector("video");
                const track = video && video.srcObject && video.srcObject.getVideoTracks()[0];
                if (track) track.applyConstraints({ advanced: [{ focusMode: "continuous" }] }).catch(() => {});
            } catch (_) {}
        }

        // Arranque simple: la librería extrae SOLO facingMode/deviceId del
        // primer parámetro y descarta cualquier otra clave — pasar más
        // constraints aquí no sirve de nada (verificado en el minificado).
        scanner.start({ facingMode: "environment" }, config, onEscaneado, () => {})
        .catch((errEnv) => {
            console.warn("[escaner] Cámara trasera falló:", errEnv, "— intentando frontal...");
            return scanner.start({ facingMode: "user" }, config, onEscaneado, () => {});
        })
        .then(() => {
            activo = true;
            console.log(`[escaner] Cámara OK (iOS=${isIOS}, fps=${config.fps})`);
            // Los extras (enfoque, linterna, zoom) jamás deben tumbar la
            // cámara: si algo truena aquí, se registra y el escaneo sigue.
            try {
                enfocarContinuo();
                inyectarControles();
            } catch (e) {
                console.warn("[escaner] Controles extra fallaron (la cámara sigue viva):", e);
            }
        })
        .catch((err) => {
            console.error("[escaner] Ambas cámaras fallaron:", err);
            mostrarError(mensajeErrorCamara(err));
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

    // Traduce el error real de getUserMedia — "sin acceso" a secas no dice si
    // fue permiso denegado, cámara ocupada o dispositivo sin cámara.
    function mensajeErrorCamara(e) {
        const n = e && e.name;
        if (n === "NotAllowedError")
            return "🚫 El navegador tiene BLOQUEADO el permiso de cámara para este sitio — actívalo en los ajustes del sitio y reintenta";
        if (n === "NotFoundError")
            return "❌ Este dispositivo no tiene cámara disponible";
        if (n === "NotReadableError")
            return "⚠️ La cámara está ocupada por otra app o pestaña — ciérrala y reintenta";
        return `❌ Sin acceso a cámara.\n${n || e || "error desconocido"}`;
    }

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
