import { initProductoExistente } from "./producto_existente.js";
import { initCategorias } from "./categorias.js";
import { initAtributos } from "./atributos.js";
import { initBotonInventario } from "./boton_inventario_nvproducto.js";

document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("form-producto");

    const codigoInput = document.getElementById("id_codigo_barras");
    const nombreInput = document.getElementById("id_nombre");
    const descripcionInput = document.getElementById("id_descripcion");
    const mayoreoInput = document.getElementById("id_precio_mayoreo");
    const menudeoInput = document.getElementById("id_precio_menudeo");
    const docenaInput = document.getElementById("id_precio_docena");
    const tipoCodigoInput = document.getElementById("id_tipo_codigo");
    const duenioSelect = document.getElementById("id_dueño");

    const categoriaPadreSelect = document.getElementById("id_categoria_padre");
    const subcategoriaSelect = document.getElementById("id_subcategoria");

    const atributosContainer = document.getElementById("atributos-container");

    const ubicacionSelect = document.getElementById("id_ubicacion");
    const submitBtn = document.getElementById("submit-btn");

    function setReadOnlyTrue(elements) {
        elements.forEach((el) => {
            if (!el) return;

            if (el.tagName === "SELECT") {
                el.disabled = true;
                el.classList.add("bg-gray-100");
            } else {
                el.setAttribute("readonly", "true");
                el.classList.add("bg-gray-100");
            }
        });
    }

    function actualizarTemporadas(temporadasDelProducto) {
        const checkboxes = document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]');

        checkboxes.forEach(cb => {
            const id = parseInt(cb.value);
            cb.checked = temporadasDelProducto.includes(id);
            cb.disabled = true;
        });
    }

    function limpiarTemporadas() {
        const checkboxes = document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]');

        checkboxes.forEach(cb => {
            cb.checked = false;
            cb.disabled = false;
        });
    }

    function bloquearFoto() {
        const fotoInput = document.getElementById("id_foto_url");
        if (fotoInput) fotoInput.disabled = true;
    }

    function habilitarFoto() {
        const fotoInput = document.getElementById("id_foto_url");
        if (fotoInput) fotoInput.disabled = false;
    }

    function mostrarFoto(url) {
        const cont = document.getElementById("preview-foto");
        if (!cont) return;

        if (url) {
            cont.innerHTML = `
                <img src="${url}"
                     class="w-32 h-32 object-cover rounded border mb-2">
            `;
        } else {
            cont.innerHTML = "";
        }
    }

    function limpiarFoto() {
        const cont = document.getElementById("preview-foto");
        if (cont) cont.innerHTML = "";
    }

    // ============================
    // 1. ATRIBUTOS
    // ============================
    const atributos = initAtributos({
        atributosContainer
    });

    // ============================
    // 2. CATEGORÍAS
    // ============================
    const categorias = initCategorias({
        categoriaPadreSelect,
        subcategoriaSelect,

        onSubcategoriaCargada: (subId) => {
            atributos.mostrarAtributosDeSubcategoria(subId);
        }
    });

    // ============================
    // 3. BOTÓN + INVENTARIO
    // ============================
    const botonInventario = initBotonInventario({
        form,
        submitBtn,
        ubicacionSelect
    });

    // ============================
    // 4. PRODUCTO EXISTENTE (AJAX)
    // ============================
    initProductoExistente({
        form,
        submitBtn,
        codigoInput,
        nombreInput,
        descripcionInput,
        mayoreoInput,
        menudeoInput,
        docenaInput,
        tipoCodigoInput,
        duenioSelect,
        categoriaPadreSelect,
        subcategoriaSelect,
        atributosContainer,
        ubicacionSelect,

        onProductoEncontrado: (data) => {

            categorias.cargarSubcategorias(data.categoria_padre_id, data.subcategoria_id);

            atributos.renderAtributosReadOnly(data.atributos);

            setReadOnlyTrue([
                nombreInput,
                descripcionInput,
                mayoreoInput,
                menudeoInput,
                docenaInput,
                duenioSelect,
                categoriaPadreSelect,
                subcategoriaSelect,
                tipoCodigoInput
            ]);

            actualizarTemporadas(data.temporadas || []);
            bloquearFoto();
            mostrarFoto(data.foto_url);

            botonInventario.verificarInventario(data.producto_id, ubicacionSelect.value);
        },

        onProductoNoEncontrado: () => {
            activarCamposProducto();
            limpiarTemporadas();
            habilitarFoto();
            limpiarFoto();

            form.action = "/inventario/nuevo_producto/";

            submitBtn.textContent = "Registrar producto";
            submitBtn.classList.replace("bg-green-600", "bg-red-600");
            submitBtn.classList.replace("hover:bg-green-700", "hover:bg-red-700");

            const subId = subcategoriaSelect.value;
            if (subId) {
                atributos.mostrarAtributosDeSubcategoria(subId);
            }
        }
    });

    // ============================
    // 5. REGENERAR ATRIBUTOS EN RELOAD CON ERRORES
    // ============================
    const subIdInicial = subcategoriaSelect.value;
    if (subIdInicial) {
        atributos.mostrarAtributosDeSubcategoria(subIdInicial);
    }

});