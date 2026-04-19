// ============================
// ESCÁNER DE CÁMARA — html5-qr-code
// Funciona en celular (cámara trasera) y en PC (webcam)
// ============================

import { Html5Qrcode } from "https://cdn.jsdelivr.net/npm/html5-qr-code/+esm";

export function initEscanerCamara({ codigoInput }) {

    const btnAbrir  = document.getElementById("btn-escanear-camara");
    const modal     = document.getElementById("modal-camara");
    const btnCerrar = document.getElementById("btn-cerrar-camara");

    if (!btnAbrir || !modal || !btnCerrar) return;

    let scanner = null;
    let activo  = false;

    // ============================
    // ABRIR MODAL
    // ============================
    btnAbrir.addEventListener("click", () => {
        modal.showModal();
        iniciar();
    });

    // ============================
    // CERRAR — botón ✕
    // ============================
    btnCerrar.addEventListener("click", cerrarModal);

    // ============================
    // CERRAR — click en el backdrop
    // ============================
    modal.addEventListener("click", (e) => {
        if (e.target === modal) cerrarModal();
    });

    // ============================
    // CERRAR MODAL
    // ============================
    function cerrarModal() {
        detener().then(() => modal.close());
    }

    // ============================
    // CALLBACK: código escaneado
    // ============================
    function onEscaneado(codigo) {
        console.log("[escaner] Código detectado:", codigo);
        codigoInput.value = codigo;

        detener().then(() => {
            modal.close();
            // Simula Enter para que producto_existente.js dispare la búsqueda
            codigoInput.dispatchEvent(
                new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })
            );
        });
    }

    // ============================
    // INICIAR CÁMARA
    // ============================
    function iniciar() {
        if (activo) return;

        const esLocalhost = location.hostname === "localhost" || location.hostname === "127.0.0.1";
        const esHttps     = location.protocol === "https:";

        if (!esLocalhost && !esHttps) {
            mostrarEstado("📵 Cámara bloqueada en HTTP.\nFunciona en la versión en línea (HTTPS).", "error");
            return;
        }

        mostrarEstado("⏳ Iniciando cámara...", "info");

        // Limpiar y arrancar
        document.getElementById("camara-reader").innerHTML = "";

        scanner = new Html5Qrcode("camara-reader");

        const config = { fps: 10, qrbox: { width: 250, height: 120 } };

        // Intenta cámara trasera (celular) — si falla, usa cualquier cámara (PC)
        scanner.start(
            { facingMode: "environment" },
            config,
            onEscaneado,
            () => {} // callback por frame sin código — ignorar
        )
        .then(() => {
            activo = true;
            mostrarEstado("✅ Cámara lista. Apunta al código.", "ok");
            setTimeout(() => {
                document.getElementById("camara-reader").querySelector("div[style]")?.remove();
            }, 1500);
        })
        .catch(() => {
            mostrarEstado("⏳ Intentando cámara frontal...", "info");
            scanner.start(
                { facingMode: "user" },
                config,
                onEscaneado,
                () => {}
            )
            .then(() => {
                activo = true;
                mostrarEstado("✅ Cámara lista. Apunta al código.", "ok");
            })
            .catch((err) => {
                mostrarEstado(`❌ Sin acceso a cámara.\nError: ${err}`, "error");
            });
        });
    }

    // ============================
    // MOSTRAR ESTADO EN EL MODAL
    // ============================
    function mostrarEstado(msg, tipo = "info") {
        const reader = document.getElementById("camara-reader");
        if (!reader) return;
        const bg = tipo === "error" ? "#FF006E" : tipo === "ok" ? "#06D6A0" : "#FFEE88";
        const color = tipo === "error" ? "#fff" : "#111";
        reader.innerHTML = `
            <div style="padding:1.5rem;text-align:center;font-weight:700;font-size:0.85rem;
                        color:${color};background:${bg};border:3px solid black;white-space:pre-line;">
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
            } catch (_) { /* ignorar errores al detener */ }
            scanner = null;
            activo  = false;
            console.log("[escaner] Cámara detenida.");
        }
    }
}
