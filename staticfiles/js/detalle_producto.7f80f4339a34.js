// ============================================================
// detalle_producto.js
// - Auto-oculta mensajes
// - Carga el código de barras como base64
// - Toggle del panel de costo
// - Cascade Categoría padre → Subcategoría
// - Re-renderiza inputs de atributos según la sub seleccionada
// ============================================================

document.addEventListener("DOMContentLoaded", () => {

    // ── Mensajes ──────────────────────────────────────────
    const msgContainer = document.getElementById("msg-container");
    if (msgContainer) {
        setTimeout(() => { msgContainer.style.opacity = "0"; }, 3000);
        setTimeout(() => { msgContainer.remove(); }, 3500);
    }

    // ── Código de barras ──────────────────────────────────
    const img = document.getElementById("codigo-img");
    const codigoUrl = img?.dataset.url;
    if (img && codigoUrl) {
        fetch(codigoUrl)
            .then(res => res.json())
            .then(data => {
                if (data.imagen) img.src = `data:image/png;base64,${data.imagen}`;
            })
            .catch(err => console.error("Error cargando código:", err));
    }

    // ── Cascade categoría padre → sub + atributos dinámicos ──
    initCategoriaSubAtributos();

    // ── Cambio de código de barras con confirmación de variante ──
    initCambioCodigoBarras();
});


// ============================================================
// Toggle panel costo (se llama desde onclick="toggleCosto()")
// ============================================================
window.toggleCosto = function () {
    const panel = document.getElementById("panelCosto");
    const icon  = document.getElementById("iconCosto");
    if (!panel || !icon) return;
    const abierto = !panel.classList.contains("hidden");
    panel.classList.toggle("hidden");
    icon.textContent = abierto ? "▼" : "▲";
};


// ============================================================
// Cascade y atributos dinámicos (solo corre si puede_editar
// renderizó los selects en el template)
// ============================================================
function initCategoriaSubAtributos() {
    const selPadre  = document.getElementById("sel-categoria-padre");
    const selSub    = document.getElementById("sel-subcategoria");
    const container = document.getElementById("atributos-container");
    if (!selPadre || !selSub || !container) return;

    // valores actuales del producto (para conservar lo escrito si el usuario
    // regresa a la sub original sin haber guardado todavía)
    const valoresActuales = {};
    document.querySelectorAll("#atributos-actuales div").forEach(d => {
        valoresActuales[d.dataset.id] = d.dataset.valor || "";
    });

    // Snapshot del formulario al cargar la página (para "Restaurar valores originales").
    // Solo guardamos campos que existen al inicio — los inputs de atributos dinámicos
    // se reconstruyen vía renderAtributos() con valoresActuales.
    const padreOriginalId = selPadre.value;
    const subOriginalId   = selSub.value;
    const formEl = selPadre.closest("form");
    const snapshotInputs = new Map();
    if (formEl) {
        formEl.querySelectorAll("input[name], select[name], textarea[name]").forEach(el => {
            // Excluir los inputs de atributos (se restauran vía renderAtributos)
            if (el.name && el.name.startsWith("attr_")) return;
            snapshotInputs.set(el, el.value);
        });
    }

    // filtrar opciones del select de subs según la padre seleccionada
    function filtrarSubs() {
        const padreId = selPadre.value;
        let primeraVisible    = null;
        let haySeleccionVisible = false;

        Array.from(selSub.options).forEach(opt => {
            const visible = opt.dataset.padre === padreId;
            opt.hidden    = !visible;
            opt.disabled  = !visible;
            if (visible && primeraVisible === null) primeraVisible = opt;
            if (visible && opt.selected) haySeleccionVisible = true;
        });

        if (!haySeleccionVisible && primeraVisible) {
            primeraVisible.selected = true;
            renderAtributos(primeraVisible.value);
        }
    }

    // pintar inputs de atributos para la sub indicada
    function renderAtributos(subId) {
        while (container.firstChild) container.removeChild(container.firstChild);

        const atributos = Array.from(document.querySelectorAll("#atributos-data div"))
            .filter(d => String(d.dataset.categoria) === String(subId));

        if (atributos.length === 0) {
            const p = document.createElement("p");
            p.className = "border-4 border-dashed border-gray-300 p-6 text-center text-gray-400 font-bold text-sm";
            p.textContent = "Esta subcategoría no tiene atributos configurados.";
            container.appendChild(p);
            return;
        }

        atributos.forEach(a => {
            const wrap = document.createElement("div");
            wrap.className = "border-4 border-black shadow-[3px_3px_0_0_black] bg-[#F0FFF4] " +
                             "p-4 flex items-center justify-between gap-4 flex-wrap";

            const label = document.createElement("span");
            label.className = "font-black text-black uppercase tracking-wide text-sm";
            label.textContent = a.dataset.nombre;

            const input = document.createElement("input");
            input.type      = "text";
            input.name      = `attr_${a.dataset.nombre}`;
            input.className = "field-90s w-48";
            input.value     = valoresActuales[a.dataset.id] || "";
            input.setAttribute("autocomplete", "off");

            if ((a.dataset.tipo || "").toLowerCase() === "numero") {
                input.addEventListener("input", () => {
                    input.value = input.value.replace(/[^0-9.]/g, "");
                    if (input.value.startsWith(".")) input.value = "";
                });
            }

            wrap.appendChild(label);
            wrap.appendChild(input);
            container.appendChild(wrap);
        });
    }

    selPadre.addEventListener("change", filtrarSubs);
    selSub.addEventListener("change", () => renderAtributos(selSub.value));

    // Botón "Restaurar valores originales"
    const btnRestaurar = document.getElementById("btn-restaurar");
    if (btnRestaurar) {
        btnRestaurar.addEventListener("click", () => {
            // 1) Restaurar todos los campos del snapshot (nombre, descripción, precios, dueño…)
            snapshotInputs.forEach((val, el) => {
                if (el.isConnected) el.value = val;
            });
            // 2) Restaurar padre + sub a los originales y re-renderizar atributos
            selPadre.value = padreOriginalId;
            filtrarSubs();
            selSub.value = subOriginalId;
            renderAtributos(subOriginalId);

            // 3) Feedback visual breve
            btnRestaurar.textContent = "✓ Restaurado";
            setTimeout(() => {
                btnRestaurar.textContent = "↶ Restaurar valores originales";
            }, 1200);
        });
    }

    // estado inicial
    filtrarSubs();
}


// ============================================================
// Cambio de código de barras — mini-form inline en la card del código.
// Solo aparece si el usuario es dueño (el template renderiza los botones).
// Flujo:
//   1. Click "Editar" → muestra input + Guardar/Cancelar.
//   2. Guardar → POST AJAX a /inventario/api/producto/<id>/cambiar-codigo-barras/.
//   3. Si OK: actualiza texto, tipo y regenera la imagen del barcode in-place.
//   4. Si conflicto (mismo / otra categoría): abre modal correspondiente.
//      Modal de "misma categoría" reintenta con confirmar_variante=true.
// ============================================================
function initCambioCodigoBarras() {
    const card = document.getElementById("card-codigo-barras");
    const btnEditar = document.getElementById("btn-editar-codigo");
    if (!card || !btnEditar) return;

    const lectura      = document.getElementById("codigo-lectura");
    const edicion      = document.getElementById("codigo-edicion");
    const input        = document.getElementById("input-codigo-barras");
    const codigoTexto  = document.getElementById("codigo-texto");
    const codigoTipo   = document.getElementById("codigo-tipo");
    const errorBox     = document.getElementById("codigo-error");
    const btnCancelar  = document.getElementById("btn-cancelar-codigo");
    const btnGuardar   = document.getElementById("btn-guardar-codigo");
    const img          = document.getElementById("codigo-img");

    const urlCambiar = card.dataset.urlCambiar;

    // Modal (compartido para confirmar variante o bloquear)
    const modal        = document.getElementById("modal-cambio-codigo");
    const modalLista   = document.getElementById("modal-cambio-codigo-lista");
    const modalMsg     = document.getElementById("modal-cambio-codigo-mensaje");
    const modalTit     = document.getElementById("modal-cambio-codigo-titulo");
    const modalHeader  = document.getElementById("modal-cambio-codigo-header");
    const modalPreg    = document.getElementById("modal-cambio-codigo-pregunta");
    const btnModalCanc = document.getElementById("modal-cambio-codigo-cancelar");
    const btnModalConf = document.getElementById("modal-cambio-codigo-confirmar");

    function getCsrf() {
        const m = document.cookie.match(/csrftoken=([^;]+)/);
        if (m) return m[1];
        const el = document.querySelector('input[name="csrfmiddlewaretoken"]');
        return el ? el.value : "";
    }

    function entrarEdicion() {
        lectura.classList.add("hidden");
        edicion.classList.remove("hidden");
        input.value = input.dataset.original;
        errorBox.classList.add("hidden");
        errorBox.textContent = "";
        input.focus();
        input.select();
    }

    function salirEdicion() {
        lectura.classList.remove("hidden");
        edicion.classList.add("hidden");
        errorBox.classList.add("hidden");
        errorBox.textContent = "";
    }

    function mostrarError(msg) {
        errorBox.textContent = msg;
        errorBox.classList.remove("hidden");
    }

    function aplicarActualizacion(data) {
        codigoTexto.textContent = data.codigo;
        codigoTipo.textContent  = `Tipo: ${data.tipo_codigo}`;
        input.dataset.original  = data.codigo;
        input.value             = data.codigo;

        // Regenerar la imagen del barcode in-place
        if (img && img.dataset.url) {
            fetch(img.dataset.url)
                .then(r => r.json())
                .then(d => {
                    if (d.imagen) img.src = `data:image/png;base64,${d.imagen}`;
                })
                .catch(() => {});
        }
        salirEdicion();
    }

    function cerrarModal() {
        if (!modal) return;
        modal.classList.add("hidden");
        document.body.style.overflow = "";
    }

    function renderListaVariantes(variantes) {
        if (!modalLista) return;
        while (modalLista.firstChild) modalLista.removeChild(modalLista.firstChild);
        variantes.forEach(v => {
            const li = document.createElement("li");
            li.className = "border-2 border-black bg-[#F0FFF4] px-3 py-2 text-sm flex items-center justify-between gap-3 flex-wrap";
            const txt = document.createElement("span");
            txt.className = "font-black text-black";
            txt.textContent = `${v.nombre} (ID #${v.producto_id})`;
            const cat = document.createElement("span");
            cat.className = "text-[11px] font-bold text-gray-600";
            cat.textContent = v.subcategoria_nombre || "Sin categoría";
            li.appendChild(txt);
            li.appendChild(cat);
            modalLista.appendChild(li);
        });
    }

    function abrirModalBloqueo(nuevo, variantes, mensajeBackend) {
        if (!modal) return;
        modalHeader.classList.remove("bg-[#FFBE0B]");
        modalHeader.classList.add("bg-[#FF006E]");
        modalTit.classList.add("text-white");
        modalTit.textContent = "🚫 El código pertenece a otra categoría";
        modalMsg.innerHTML = (mensajeBackend ||
            `El código <strong>${nuevo}</strong> ya pertenece a un producto de otra categoría. ` +
            `Intenta registrar otro código.<br><br>` +
            `Recuerda que vas a tener que reetiquetar los productos.`
        ).replaceAll(nuevo, `<strong>${nuevo}</strong>`);
        renderListaVariantes(variantes || []);
        modalPreg.classList.add("hidden");
        btnModalConf.classList.add("hidden");
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
    }

    function abrirModalConfirmacion(nuevo, variantes) {
        if (!modal) return;
        modalHeader.classList.remove("bg-[#FF006E]");
        modalHeader.classList.add("bg-[#FFBE0B]");
        modalTit.classList.remove("text-white");
        modalTit.textContent = "⚠️ Este código ya existe";
        modalMsg.innerHTML =
            `El código <strong>${nuevo}</strong> ya pertenece a estos productos de la <strong>misma categoría</strong>:`;
        renderListaVariantes(variantes || []);
        modalPreg.classList.remove("hidden");
        btnModalConf.classList.remove("hidden");
        modal.classList.remove("hidden");
        document.body.style.overflow = "hidden";
    }

    async function guardar(confirmarVariante = false) {
        const nuevo = input.value.trim();
        const original = (input.dataset.original || "").trim();
        if (!nuevo) {
            mostrarError("El código no puede estar vacío.");
            return;
        }
        if (nuevo === original) {
            salirEdicion();
            return;
        }

        btnGuardar.disabled = true;
        errorBox.classList.add("hidden");

        try {
            const resp = await fetch(urlCambiar, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": getCsrf(),
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({
                    codigo: nuevo,
                    confirmar_variante: !!confirmarVariante
                })
            });
            const data = await resp.json();

            if (resp.ok && data.ok) {
                aplicarActualizacion(data);
                return;
            }

            if (data && data.tipo === "necesita_confirmacion") {
                abrirModalConfirmacion(nuevo, data.variantes || []);
                return;
            }
            if (data && data.tipo === "otra_categoria") {
                abrirModalBloqueo(nuevo, data.variantes || [], data.error);
                return;
            }
            mostrarError((data && data.error) || "No se pudo actualizar el código.");
        } catch (err) {
            console.error("Error guardando código:", err);
            mostrarError("Error de conexión. Intenta de nuevo.");
        } finally {
            btnGuardar.disabled = false;
        }
    }

    btnEditar.addEventListener("click", entrarEdicion);
    btnCancelar?.addEventListener("click", salirEdicion);
    btnGuardar?.addEventListener("click", () => guardar(false));
    input?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") { e.preventDefault(); guardar(false); }
        if (e.key === "Escape") { e.preventDefault(); salirEdicion(); }
    });

    btnModalCanc?.addEventListener("click", cerrarModal);
    btnModalConf?.addEventListener("click", () => {
        cerrarModal();
        guardar(true);
    });
    modal?.addEventListener("click", (e) => {
        if (e.target === modal) cerrarModal();
    });
}
