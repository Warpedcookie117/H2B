// ============================
// BUSCADOR + ESCÁNER — inventario_ubicacion
// ============================

const buscador      = document.getElementById("buscadorProductos");
const sinResultados = document.getElementById("sinResultados");

if (!buscador) {
    console.warn("⚠️ No existe #buscadorProductos en inventario_ubicacion.");
} else {

    // Restaurar valor desde URL al cargar la página
    const params = new URLSearchParams(window.location.search);
    const qActual = params.get("q") || "";
    if (qActual) buscador.value = qActual;

    buscador.focus();

    let esperandoNuevoEscaneo = false;
    let debounceTimer = null;

    function buscarEnServidor(q) {
        const p = new URLSearchParams(window.location.search);
        if (q) {
            p.set("q", q);
        } else {
            p.delete("q");
        }
        p.delete("page");
        window.location.search = p.toString();
    }

    // ============================
    // KEYDOWN — Enter dispara búsqueda inmediata
    // ============================
    buscador.addEventListener("keydown", function (e) {

        if (e.key === "Enter") {
            e.preventDefault();
            clearTimeout(debounceTimer);
            buscarEnServidor(buscador.value.trim());
            esperandoNuevoEscaneo = true;
            return;
        }

        // Primer carácter después de Enter → limpiar para nuevo escaneo
        if (esperandoNuevoEscaneo) {
            buscador.value = "";
            esperandoNuevoEscaneo = false;
        }
    });

    // ============================
    // TECLAS GLOBALES → foco al buscador
    // ============================
    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if (["Tab", "Escape", "Enter",
             "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
             "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"
        ].includes(e.key)) return;

        buscador.value = "";
        esperandoNuevoEscaneo = false;
        buscador.focus();
    });

    // ============================
    // INPUT — debounce 400ms → búsqueda en servidor
    // ============================
    buscador.addEventListener("input", function () {
        clearTimeout(debounceTimer);
        const texto = this.value.trim();
        debounceTimer = setTimeout(() => {
            buscarEnServidor(texto);
        }, 400);
    });

    // ============================
    // ESCÁNER DE CÁMARA
    // ============================
    if (typeof initEscanerCamara === "function") {
        initEscanerCamara((codigo) => {
            buscador.value = codigo;
            clearTimeout(debounceTimer);
            buscarEnServidor(codigo);
        });
    }

}
