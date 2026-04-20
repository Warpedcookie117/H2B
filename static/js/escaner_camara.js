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
    // ============================
    function onEscaneado(codigo) {
        console.log("[escaner] ✅ Código detectado:", codigo);
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
            fps: 15,
            qrbox: { width: 280, height: 100 },
            formatsToSupport: F ? [
                F.EAN_13, F.EAN_8,
                F.UPC_A,  F.UPC_E,
                F.CODE_128, F.CODE_39,
                F.QR_CODE,
            ] : undefined,
        };

        scanner.start({ facingMode: "environment" }, config, onEscaneado, () => {})
        .then(() => {
            activo = true;
            console.log("[escaner] Cámara trasera OK");
        })
        .catch((errEnv) => {
            console.warn("[escaner] Cámara trasera falló:", errEnv, "— intentando frontal...");
            scanner.start({ facingMode: "user" }, config, onEscaneado, () => {})
            .then(() => {
                activo = true;
                console.log("[escaner] Cámara frontal OK");
            })
            .catch((errUser) => {
                console.error("[escaner] Ambas cámaras fallaron:", errUser);
                mostrarError("❌ Sin acceso a cámara.\n" + errUser);
            });
        });
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
            console.log("[escaner] Cámara detenida.");
        }
    }
}
