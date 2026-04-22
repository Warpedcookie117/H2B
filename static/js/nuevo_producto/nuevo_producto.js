import { initProductoExistente } from "./producto_existente.js";
import { initCategorias }        from "./categorias.js";
import { initAtributos }         from "./atributos.js";
import { initBotonInventario }   from "./boton_inventario_nvproducto.js";
import { iniciarBarraProgreso }  from "./barra_progreso.js";

document.addEventListener("DOMContentLoaded", () => {

    const form = document.getElementById("form-producto");

    const codigoInput        = document.getElementById("id_codigo_barras");
    const nombreInput        = document.getElementById("id_nombre");
    const descripcionInput   = document.getElementById("id_descripcion");
    const mayoreoInput       = document.getElementById("id_precio_mayoreo");
    const menudeoInput       = document.getElementById("id_precio_menudeo");
    const docenaInput        = document.getElementById("id_precio_docena");
    const tipoCodigoInput    = document.getElementById("id_tipo_codigo");
    const duenioSelect       = document.getElementById("id_dueño");

    const categoriaPadreSelect = document.getElementById("id_categoria_padre");
    const subcategoriaSelect   = document.getElementById("id_subcategoria");

    const atributosContainer = document.getElementById("atributos-container");
    const ubicacionSelect    = document.getElementById("id_ubicacion");
    const submitBtn          = document.getElementById("submit-btn");

    // ============================
    // HELPERS DE UI
    // ============================
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
        document.querySelectorAll('.temporada-checkbox-group input[type="checkbox"]')
            .forEach(cb => {
                cb.checked  = temporadasDelProducto.includes(parseInt(cb.value));
                cb.disabled = true;
            });
    }

    function bloquearFoto() {
        const f = document.getElementById("id_foto_url");
        if (f) { f.style.pointerEvents = "none"; f.style.opacity = "0.5"; }
    }

    function mostrarFoto(url) {
        const circle      = document.getElementById("foto-circle");
        const placeholder = document.getElementById("foto-placeholder");
        if (!circle || !placeholder) return;
        if (url) {
            circle.src                = url;
            circle.style.display      = "block";
            placeholder.style.display = "none";
        } else {
            circle.style.display      = "none";
            placeholder.style.display = "flex";
        }
    }

    // ============================
    // 1. ATRIBUTOS
    // ============================
    const atributos = initAtributos({ atributosContainer });

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
        form, submitBtn, ubicacionSelect,
        codigoInput, nombreInput, descripcionInput,
        mayoreoInput, menudeoInput, docenaInput,
        tipoCodigoInput, duenioSelect,
        categoriaPadreSelect, subcategoriaSelect
    });

    // ============================
    // 4. PRODUCTO EXISTENTE (AJAX)
    // ============================
    initProductoExistente({
        form, submitBtn, codigoInput,
        nombreInput, descripcionInput,
        mayoreoInput, menudeoInput, docenaInput,
        tipoCodigoInput, duenioSelect,
        categoriaPadreSelect, subcategoriaSelect,
        atributosContainer, ubicacionSelect,

        onProductoEncontrado: (data) => {
            categorias.cargarSubcategorias(data.categoria_padre_id, data.subcategoria_id);
            atributos.renderAtributosReadOnly(data.atributos);

            setReadOnlyTrue([
                nombreInput, descripcionInput, mayoreoInput, menudeoInput,
                docenaInput, duenioSelect, categoriaPadreSelect,
                subcategoriaSelect, tipoCodigoInput
            ]);

            actualizarTemporadas(data.temporadas || []);
            bloquearFoto();
            mostrarFoto(data.foto_url);

            botonInventario.verificarInventario(data.producto_id, ubicacionSelect.value);
        },

        onProductoNoEncontrado: () => {
            // producto_existente.js maneja el desbloqueo directo
        },

        // ← Este callback limpia atributos y banner cuando se borra el código
        onLimpiar: () => {
            atributos.mostrarAtributosDeSubcategoria(""); // limpia atributos y oculta banner
        }
    });

    // ============================
    // 5. REGENERAR ATRIBUTOS EN RELOAD CON ERRORES
    // ============================
    const subIdInicial = subcategoriaSelect.value;
    if (subIdInicial) {
        atributos.mostrarAtributosDeSubcategoria(subIdInicial);
    }

    // ============================
    // 6. ESCÁNER DE CÁMARA
    // ============================
    initEscanerCamara((codigo) => {
        codigoInput.value = codigo;
        codigoInput.dispatchEvent(new Event("input", { bubbles: true }));
        codigoInput.dispatchEvent(
            new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true })
        );
    });

    // ============================
    // 7. FOCO AUTOMÁTICO AL CAMPO CÓDIGO
    // ============================
    codigoInput.focus();

    document.addEventListener("keydown", function (e) {
        const tag = document.activeElement.tagName.toLowerCase();
        if (tag === "input" || tag === "textarea" || tag === "select") return;
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        if ([
            "Tab", "Escape", "Enter",
            "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight",
            "F1","F2","F3","F4","F5","F6","F7","F8","F9","F10","F11","F12"
        ].includes(e.key)) return;
        codigoInput.focus();
    });

});

// ============================
// DEBUG: detectar quién borra el archivo
// ============================
const fotoInput = document.querySelector("#id_foto_url");
if (fotoInput) {
    let ultimoEstado = fotoInput.files.length;
    setInterval(() => {
        const actual = fotoInput.files.length;
        if (ultimoEstado === 1 && actual === 0) {
            console.warn("🔥 EL ARCHIVO SE BORRÓ 🔥");
            console.trace();
        }
        ultimoEstado = actual;
    }, 200);
}

import "./fuzzy.js";