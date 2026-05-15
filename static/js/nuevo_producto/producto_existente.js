// ============================
// PRODUCTO EXISTENTE (AJAX)
// ============================

// Cloudinary: reescribe la URL para servir una versión ligera (w pequeño +
// q_auto:low + f_auto) ideal para thumbs del selector de variantes.
function urlImagenLigera(url, w = 120) {
    if (!url || typeof url !== "string") return url;
    if (!url.includes("/image/upload/")) return url;
    const trans = `w_${w},c_limit,q_auto:low,f_auto`;
    const match = url.match(/\/image\/upload\/([^/]+)\//);
    if (match && (match[1].includes(",") || match[1].includes("_"))) {
        return url.replace(/\/image\/upload\/[^/]+\//, `/image/upload/${trans}/`);
    }
    return url.replace("/image/upload/", `/image/upload/${trans}/`);
}

//
// Flujo:
// 1. Usuario escanea/teclea un código de barras y pulsa Enter.
// 2. AJAX devuelve { existe, variantes: [...] }.
// 3. Si N==0 → flujo "producto nuevo" (no se prellena nada).
// 4. Si N>=1 → se muestra un selector con todas las variantes y la
//    opción "Registrar como variante nueva".
//      - Click en variante existente → onProductoEncontrado(data) →
//        prellenar TODO y bloquear (igual que el flujo viejo).
//      - Click en "Registrar variante nueva" → onVarianteNueva(plantilla)
//        → prellenar pero dejar editable.

export function initProductoExistente({
    form,
    codigoInput,
    submitBtn,
    nombreInput,
    mayoreoInput,
    menudeoInput,
    docenaInput,
    tipoCodigoInput,
    duenioSelect,
    categoriaPadreSelect,
    subcategoriaSelect,
    atributosContainer,
    ubicacionSelect,
    onProductoEncontrado,
    onVarianteNueva,
    onProductoNoEncontrado,
    onLimpiar,
}) {

    let buscando              = false;
    let limpiando             = false;
    let esperandoNuevoEscaneo = false;

    // Teclas de edición manual — no deben tratarse como inicio de nuevo escaneo
    const TECLAS_EDICION = [
        "Backspace", "Delete", "ArrowLeft", "ArrowRight",
        "ArrowUp", "ArrowDown", "Home", "End"
    ];

    // ============================
    // MENSAJE
    // ============================
    function mostrarMensaje(msg, tipo = "info") {
        let box = document.getElementById("msg-producto-existente");
        if (!box) {
            box = document.createElement("div");
            box.id = "msg-producto-existente";
            codigoInput.closest(".space-y-1")?.insertAdjacentElement("afterend", box);
        }
        const colores = {
            info:    "bg-[#FFBE0B] text-black",
            success: "bg-[#06D6A0] text-black",
            error:   "bg-[#FF006E] text-white",
        };
        box.className = `border-4 border-black shadow-[4px_4px_0_0_black] px-6 py-3
                         font-black uppercase tracking-widest text-sm mb-4
                         ${colores[tipo] || colores.info}`;
        box.textContent = msg;
        setTimeout(() => { if (box) box.remove(); }, 2500);
    }

    // ============================
    // LIMPIAR Y DESBLOQUEAR
    // ============================
    function limpiarYDesbloquear() {
        limpiando = true;

        document.getElementById("id_producto_id")?.remove();
        document.getElementById("selector-variantes")?.remove();
        document.getElementById("link-variante-nueva")?.remove();
        form.dataset.modoVariante = "";

        nombreInput.value      = "";
        mayoreoInput.value     = "";
        menudeoInput.value     = "";
        docenaInput.value      = "";
        tipoCodigoInput.value  = "";

        [nombreInput, mayoreoInput,
         menudeoInput, docenaInput, tipoCodigoInput].forEach(el => {
            el.removeAttribute("readonly");
            el.classList.remove("bg-gray-100");
        });

        duenioSelect.disabled = false;
        duenioSelect.value    = "";
        duenioSelect.classList.remove("bg-gray-100");

        categoriaPadreSelect.disabled = false;
        categoriaPadreSelect.value    = "";
        categoriaPadreSelect.classList.remove("bg-gray-100");

        subcategoriaSelect.disabled  = false;
        subcategoriaSelect.innerHTML = "<option value=''>---------</option>";
        subcategoriaSelect.classList.remove("bg-gray-100");

        document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]')
            .forEach(cb => { cb.checked = false; cb.disabled = false; });

        const circle      = document.getElementById("foto-circle");
        const placeholder = document.getElementById("foto-placeholder");
        if (circle)      { circle.src = ""; circle.style.display = "none"; }
        if (placeholder) placeholder.style.display = "flex";

        const fotoInput = document.getElementById("id_foto_url");
        if (fotoInput) {
            fotoInput.style.pointerEvents = "auto";
            fotoInput.style.opacity       = "1";
        }

        submitBtn.textContent = "Continuar para seleccionar etiqueta";
        submitBtn.classList.remove("bg-[#06D6A0]", "bg-[#FF006E]");
        submitBtn.classList.add("bg-[#3A86FF]");

        if (onLimpiar) onLimpiar();

        limpiando = false;
    }

    // ============================
    // KEYDOWN
    // ============================
    codigoInput.addEventListener("keydown", (e) => {

        if (e.key === "Enter") {
            e.preventDefault();
            const codigo = codigoInput.value.trim();
            if (!codigo) return;
            buscarYCompletar(codigo);
            esperandoNuevoEscaneo = true;
            return;
        }

        // Backspace y teclas de edición → NO son nuevo escaneo
        if (TECLAS_EDICION.includes(e.key)) return;

        // Cualquier otro carácter después de una búsqueda → nuevo escaneo
        if (esperandoNuevoEscaneo) {
            codigoInput.value     = "";
            esperandoNuevoEscaneo = false;
        }
    });

    // ============================
    // INPUT → si había producto cargado, limpiar todo
    // ============================
    codigoInput.addEventListener("input", () => {
        if (buscando || limpiando) return;
        const hayProducto = !!document.getElementById("id_producto_id");
        const haySelector = !!document.getElementById("selector-variantes");
        const modoVariante = form.dataset.modoVariante;
        if (!hayProducto && !haySelector && !modoVariante) return;
        limpiarYDesbloquear();
    });

    // ============================
    // SELECTOR DE VARIANTES
    // ============================
    function resumenAtributos(variante) {
        const valores = (variante.atributos || [])
            .filter(a => a.valor && String(a.valor).trim() !== "")
            .map(a => `${a.nombre}: ${a.valor}`);
        return valores.length ? valores.join(" · ") : "Sin atributos";
    }

    function renderSelectorVariantes(variantes) {
        document.getElementById("selector-variantes")?.remove();

        const wrapper = document.createElement("div");
        wrapper.id = "selector-variantes";
        wrapper.className = "border-4 border-black shadow-[4px_4px_0_0_black] bg-white p-4 space-y-3";

        const titulo = document.createElement("p");
        titulo.className = "font-black uppercase tracking-widest text-sm text-black";
        const n = variantes.length;
        titulo.textContent = n === 1
            ? "1 producto ya usa este código:"
            : `${n} productos ya usan este código:`;
        wrapper.appendChild(titulo);

        const subtitulo = document.createElement("p");
        subtitulo.className = "text-xs font-bold text-gray-700";
        subtitulo.textContent = "Pícale a uno para agregar inventario, o registra una variante nueva 👇";
        wrapper.appendChild(subtitulo);

        const lista = document.createElement("div");
        lista.className = "grid gap-2";
        wrapper.appendChild(lista);

        variantes.forEach(v => {
            const card = document.createElement("button");
            card.type = "button";
            card.className =
                "flex items-center gap-3 w-full text-left border-4 border-black " +
                "bg-[#FFBE0B] hover:bg-[#06D6A0] active:translate-x-[2px] active:translate-y-[2px] " +
                "shadow-[4px_4px_0_0_black] px-3 py-2";

            const fotoBox = document.createElement("div");
            fotoBox.className = "w-12 h-12 border-2 border-black bg-white flex items-center justify-center overflow-hidden flex-none";
            if (v.foto_url) {
                const img = document.createElement("img");
                img.src = urlImagenLigera(v.foto_url, 100);
                img.loading = "lazy";
                img.alt = v.nombre;
                img.className = "w-full h-full object-cover";
                fotoBox.appendChild(img);
            } else {
                fotoBox.textContent = "📦";
            }

            const info = document.createElement("div");
            info.className = "flex-1 min-w-0";
            const nombre = document.createElement("p");
            nombre.className = "font-black text-sm text-black truncate";
            nombre.textContent = v.nombre;
            const detalle = document.createElement("p");
            detalle.className = "text-[11px] font-bold text-black/80 truncate";
            detalle.textContent = resumenAtributos(v);
            const precio = document.createElement("p");
            precio.className = "text-[11px] font-bold text-black/80";
            precio.textContent = `Men $${v.precio_menudeo} · May $${v.precio_mayoreo}`;
            info.appendChild(nombre);
            info.appendChild(detalle);
            info.appendChild(precio);

            card.appendChild(fotoBox);
            card.appendChild(info);

            card.addEventListener("click", () => seleccionarVarianteExistente(v));
            lista.appendChild(card);
        });

        // Botón "+ Nueva variante"
        const nuevoBtn = document.createElement("button");
        nuevoBtn.type = "button";
        nuevoBtn.className =
            "w-full border-4 border-black bg-[#FF006E] hover:bg-[#8338EC] " +
            "text-white font-black uppercase tracking-widest text-sm " +
            "shadow-[4px_4px_0_0_black] px-3 py-3";
        nuevoBtn.textContent = "⊕ Registrar como variante nueva";
        nuevoBtn.addEventListener("click", () => seleccionarVarianteNueva(variantes[0], variantes));
        wrapper.appendChild(nuevoBtn);

        codigoInput.closest(".space-y-1")?.insertAdjacentElement("afterend", wrapper);
    }

    function seleccionarVarianteExistente(data) {
        // Llenar todos los campos como hoy
        nombreInput.value      = data.nombre        || "";
        mayoreoInput.value     = data.precio_mayoreo ?? "";
        menudeoInput.value     = data.precio_menudeo ?? "";
        docenaInput.value      = data.precio_docena  ?? "";
        tipoCodigoInput.value  = data.tipo_codigo    ?? "";

        if (data.duenio_id)
            duenioSelect.value = String(data.duenio_id);
        if (data.categoria_padre_id)
            categoriaPadreSelect.value = String(data.categoria_padre_id);

        let hiddenId = document.getElementById("id_producto_id");
        if (!hiddenId) {
            hiddenId      = document.createElement("input");
            hiddenId.type = "hidden";
            hiddenId.id   = "id_producto_id";
            hiddenId.name = "producto_id";
            form.appendChild(hiddenId);
        }
        hiddenId.value = data.producto_id;

        // Marcar que NO estamos en flujo "variante nueva"
        form.dataset.modoVariante = "existente";

        submitBtn.textContent = "Actualizar producto";
        submitBtn.classList.remove("bg-[#FF006E]", "bg-[#3A86FF]");
        submitBtn.classList.add("bg-[#06D6A0]");

        document.getElementById("selector-variantes")?.remove();

        mostrarMensaje("¡Producto encontrado! 🎯", "success");
        onProductoEncontrado(data);
    }

    // ============================
    // LINK secundario para registrar variante cuando hay solo 1 match
    // ============================
    function mostrarLinkVarianteNueva(plantilla, todasLasVariantes) {
        document.getElementById("link-variante-nueva")?.remove();

        const btn = document.createElement("button");
        btn.type = "button";
        btn.id = "link-variante-nueva";
        btn.className =
            "w-full border-4 border-black bg-[#FFBE0B] hover:bg-[#FF006E] hover:text-white " +
            "text-black font-black uppercase tracking-widest text-xs " +
            "shadow-[4px_4px_0_0_black] px-3 py-2 mb-2";
        btn.textContent = "¿Quieres agregar una variante con este mismo código de barras?";

        btn.addEventListener("click", () => {
            seleccionarVarianteNueva(plantilla, todasLasVariantes);
        });

        codigoInput.closest(".space-y-1")?.insertAdjacentElement("afterend", btn);
    }

    function seleccionarVarianteNueva(plantilla, todasLasVariantes) {
        // Quitar id de producto existente (se va a registrar uno nuevo)
        document.getElementById("id_producto_id")?.remove();
        document.getElementById("link-variante-nueva")?.remove();

        // Marcar el modo
        form.dataset.modoVariante = "nueva";

        // Desbloquear todos los campos (pueden estar readonly si venimos del flujo N=1
        // donde seleccionarVarianteExistente los bloqueó primero)
        [nombreInput, mayoreoInput, menudeoInput, docenaInput, tipoCodigoInput].forEach(el => {
            el.removeAttribute("readonly");
            el.classList.remove("bg-gray-100");
        });
        [duenioSelect, categoriaPadreSelect, subcategoriaSelect].forEach(el => {
            el.disabled = false;
            el.classList.remove("bg-gray-100");
        });

        // Prellenar los campos con la primera variante como base
        nombreInput.value      = plantilla.nombre        || "";
        mayoreoInput.value     = plantilla.precio_mayoreo ?? "";
        menudeoInput.value     = plantilla.precio_menudeo ?? "";
        docenaInput.value      = plantilla.precio_docena  ?? "";
        tipoCodigoInput.value  = plantilla.tipo_codigo    ?? "";

        if (plantilla.duenio_id)
            duenioSelect.value = String(plantilla.duenio_id);
        if (plantilla.categoria_padre_id)
            categoriaPadreSelect.value = String(plantilla.categoria_padre_id);

        document.getElementById("selector-variantes")?.remove();

        mostrarMensaje("Cambia el nombre y/o atributos para diferenciar la variante ✏️", "info");

        // Resaltar el campo nombre para que el usuario lo edite de inmediato
        nombreInput.focus();
        nombreInput.select();

        // Delegar al caller — ahí se cargan subcategorías y atributos editables
        onVarianteNueva(plantilla, todasLasVariantes);
    }

    // ============================
    // BUSCAR
    // ============================
    async function buscarYCompletar(codigo) {
        if (!codigo || buscando) return;

        buscando = true;
        codigoInput.classList.add("opacity-50");

        try {
            const resp = await fetch(
                `/inventario/buscar_producto/?codigo=${encodeURIComponent(codigo)}`,
                { headers: { "X-Requested-With": "XMLHttpRequest" } }
            );

            if (!resp.ok) { mostrarMensaje("Error en el servidor.", "error"); return; }

            const data = await resp.json();
            const variantes = Array.isArray(data.variantes) ? data.variantes : [];

            if (!data.existe || variantes.length === 0) {
                mostrarMensaje("No encontré ese código. Si es nuevo, llena los campos. 👇", "info");
                onProductoNoEncontrado();
                return;
            }

            if (variantes.length === 1) {
                // Caso común: 1 sola coincidencia → flujo directo "agregar
                // inventario" y un link secundario por si la cajera quiere
                // registrar una variante distinta con el mismo código.
                seleccionarVarianteExistente(variantes[0]);
                mostrarLinkVarianteNueva(variantes[0], variantes);
                return;
            }

            // Múltiples variantes con este código → selector completo
            renderSelectorVariantes(variantes);

        } catch (err) {
            mostrarMensaje("Error inesperado.", "error");
            console.error(err);
        } finally {
            codigoInput.classList.remove("opacity-50");
            buscando = false;
        }
    }
}
