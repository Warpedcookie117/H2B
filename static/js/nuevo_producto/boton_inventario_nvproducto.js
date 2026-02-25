// ============================================
// BOTÓN + INVENTARIO (nuevo producto / existente)
// ============================================
//
// Responsabilidad ÚNICA:
// - Verificar inventario por producto + ubicación
// - Cambiar el texto del botón
// - Cambiar la acción del formulario
// - Activar/desactivar campos del producto
//

export function initBotonInventario({
    form,
    submitBtn,
    ubicacionSelect,

    // CAMPOS DEL PRODUCTO
    codigoInput,
    nombreInput,
    descripcionInput,
    mayoreoInput,
    menudeoInput,
    docenaInput,
    tipoCodigoInput,
    duenioSelect,
    categoriaPadreSelect,
    subcategoriaSelect
}) {

    // ============================
    // DESACTIVAR CAMPOS DEL PRODUCTO
    // ============================
    function desactivarCamposProducto() {
        const campos = [
            codigoInput,
            nombreInput,
            descripcionInput,
            mayoreoInput,
            menudeoInput,
            docenaInput,
            tipoCodigoInput,
            duenioSelect,
            categoriaPadreSelect,
            subcategoriaSelect
        ];

        campos.forEach(campo => {
            campo.disabled = true;
            campo.removeAttribute("name");
        });
    }

    // ============================
    // ACTIVAR CAMPOS DEL PRODUCTO
    // ============================
    function activarCamposProducto() {
        codigoInput.disabled = false;
        codigoInput.name = "codigo_barras";

        nombreInput.disabled = false;
        nombreInput.name = "nombre";

        descripcionInput.disabled = false;
        descripcionInput.name = "descripcion";

        mayoreoInput.disabled = false;
        mayoreoInput.name = "precio_mayoreo";

        menudeoInput.disabled = false;
        menudeoInput.name = "precio_menudeo";

        docenaInput.disabled = false;
        docenaInput.name = "precio_docena";

        tipoCodigoInput.disabled = false;
        tipoCodigoInput.name = "tipo_codigo";

        duenioSelect.disabled = false;
        duenioSelect.name = "dueño";

        categoriaPadreSelect.disabled = false;
        categoriaPadreSelect.name = "categoria_padre";

        subcategoriaSelect.disabled = false;
        subcategoriaSelect.name = "subcategoria";
    }

    // ============================
    // CAMBIO DE UBICACIÓN
    // ============================
    ubicacionSelect?.addEventListener("change", () => {
        const productoId = document.getElementById("id_producto_id")?.value;
        if (productoId) {
            verificarInventario(productoId, ubicacionSelect.value);
        }
    });

    // ============================
    // FUNCIÓN PRINCIPAL
    // ============================
    async function verificarInventario(productoId, ubicacionId) {
        if (!productoId || !ubicacionId) return;

        try {
            const url = `/inventario/verificar_estado_producto/?producto=${productoId}&ubicacion=${ubicacionId}`;
            const resp = await fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } });

            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data = await resp.json();

            const { producto_existe, inventario_existe } = data;

            // ============================
            // ESTADO 1: PRODUCTO NO EXISTE
            // ============================
            if (!producto_existe) {
                form.action = `/inventario/nuevo_producto/`;
                submitBtn.textContent = "Registrar producto";

                submitBtn.classList.replace("bg-green-600", "bg-red-600");
                submitBtn.classList.replace("hover:bg-green-700", "hover:bg-red-700");

                activarCamposProducto();
                return;
            }

            // ============================
            // ESTADO 2: PRODUCTO EXISTE PERO INVENTARIO NO
            // ============================
            if (producto_existe && !inventario_existe) {
                const cantidad = document.querySelector("#id_cantidad_inicial")?.value || "";
                form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;

                submitBtn.textContent = "Crear inventario en esta ubicación";

                submitBtn.classList.replace("bg-red-600", "bg-green-600");
                submitBtn.classList.replace("hover:bg-red-700", "hover:bg-green-700");

                desactivarCamposProducto();
                return;
            }

            // ============================
            // ESTADO 3: INVENTARIO EXISTE
            // ============================
            if (producto_existe && inventario_existe) {
                const cantidad = document.querySelector("#id_cantidad_inicial")?.value || "";
                form.action = `/inventario/agregar_inventario/${productoId}/${ubicacionId}/`;

                submitBtn.textContent = "Agregar inventario";

                submitBtn.classList.replace("bg-red-600", "bg-green-600");
                submitBtn.classList.replace("hover:bg-red-700", "hover:bg-green-700");

                desactivarCamposProducto();
                return;
            }

        } catch (err) {
            console.error("Error verificando inventario:", err);
        }
    }

    // ============================
    // INTERCEPTAR SUBMIT PARA PASAR CANTIDAD
    // ============================
    submitBtn.addEventListener("click", (e) => {
        if (form.action.includes("/inventario/agregar_inventario/")) {
            e.preventDefault();

            const cantidad = document.querySelector("#id_cantidad_inicial")?.value || "";
            const url = form.action + `?cantidad_inicial=${cantidad}`;

            window.location.href = url;
        }
    });

    return {
        verificarInventario
    };
}