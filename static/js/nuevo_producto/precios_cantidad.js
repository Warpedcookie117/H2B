// ============================================================
// PRECIOS POR CANTIDAD en el alta (solo dueñas: si no es dueña, la
// sección #precios-cantidad no existe y esto no hace nada).
//
// - El editor (tarjeta.js) llena el campo oculto presentaciones_json.
// - "¿Otro producto tiene el precio...?": escanea otro producto y copia SOLO
//   sus precios por cantidad (menudeo, mayoreo y docena no se tocan).
// - "Usar los del último que registraste".
// - Variante nueva: trae los de la variante base, editables.
// - Producto que ya existe (agregar inventario): se enseñan sin editar.
// ============================================================
import { crearEditor, copiarFilas, erroresDe, limpiarFilas, resumen } from "../precios_cantidad/tarjeta.js";

export function initPreciosCantidad({ menudeoInput }) {
    const seccion = document.getElementById("precios-cantidad");
    if (!seccion) return null;

    const oculto      = document.getElementById("id_presentaciones_json");
    const errores     = document.getElementById("pc-errores");
    const copiarBox   = document.getElementById("pc-copiar-box");
    const copiarInput = document.getElementById("pc-copiar");
    const resultados  = document.getElementById("pc-copiar-resultados");
    const mensaje     = document.getElementById("pc-copiar-mensaje");
    const contenedor  = document.getElementById("pc-editor");

    const menudeo = () => menudeoInput?.value;

    // Al recargar con errores del servidor, el campo oculto trae lo que ya se había puesto.
    let iniciales = [];
    try { iniciales = JSON.parse(oculto.value || "[]"); } catch { iniciales = []; }

    let editor = null;
    let soloLectura = false;
    function editable(filas) {
        soloLectura = false;
        editor = crearEditor(contenedor, { filas, menudeo, onCambio: sincronizar });
        copiarBox.classList.remove("hidden");
        sincronizar(editor.getFilas());
    }

    function sincronizar(filas) {
        oculto.value = JSON.stringify(limpiarFilas(filas));
        const lista = erroresDe(filas);
        errores.innerHTML = "";
        lista.forEach(e => { const li = document.createElement("li"); li.textContent = e; errores.append(li); });
        errores.classList.toggle("hidden", !lista.length);
    }

    function decir(texto, ok = true) {
        mensaje.textContent = texto;
        mensaje.className = `text-xs font-bold ${ok ? "text-[#047857]" : "text-[#B5005A]"}`;
        mensaje.classList.toggle("hidden", !texto);
    }

    function usarDe(producto) {
        if (!producto.presentaciones?.length) {
            decir(`${producto.nombre} no tiene precio por caja ni por media docena.`, false);
            return;
        }
        editor.setFilas(copiarFilas(producto.presentaciones));
        resultados.innerHTML = "";
        copiarInput.value = "";
        decir(`Listo, copié los precios de ${producto.nombre}. Puedes cambiarlos.`);
    }

    // ---------- Copiar de otro producto ----------
    let pedido = null;
    async function buscar(q) {
        q = q.trim();
        resultados.innerHTML = "";
        if (q.length < 2) { decir(""); return; }
        pedido?.abort();
        pedido = new AbortController();
        let datos;
        try {
            const r = await fetch(`${seccion.dataset.urlBuscar}?q=${encodeURIComponent(q)}`, { signal: pedido.signal });
            datos = await r.json();
        } catch (e) {
            if (e.name !== "AbortError") decir("No se pudo buscar. Revisa el internet.", false);
            return;
        }
        const productos = datos.productos || [];
        if (!productos.length) { decir("No encontré ese producto.", false); return; }
        decir("");

        // Un solo producto con ese código: se copia directo.
        if (productos.length === 1 && datos.por_codigo) {
            usarDe(productos[0]);
            return;
        }
        productos.forEach(p => {
            const b = document.createElement("button");
            b.type = "button";
            b.className = "w-full text-left border-2 border-black bg-white px-2 py-1.5 text-xs font-bold " +
                          "disabled:opacity-50 disabled:cursor-not-allowed";
            b.disabled = !p.presentaciones.length;
            const nombre = document.createElement("span");
            nombre.className = "font-black";
            nombre.textContent = p.nombre + (p.detalle ? ` · ${p.detalle}` : "");
            const precios = document.createElement("span");
            precios.className = "block text-black/60";
            precios.textContent = p.presentaciones.length ? resumen(p.presentaciones) : "No tiene precio por caja";
            b.append(nombre, precios);
            b.addEventListener("click", () => usarDe(p));
            resultados.append(b);
        });
    }

    let espera = null;
    copiarInput.addEventListener("input", () => {
        clearTimeout(espera);
        espera = setTimeout(() => buscar(copiarInput.value), 350);
    });
    // Enter (la pistola lo manda al final del código) busca ya y NO manda el formulario.
    copiarInput.addEventListener("keydown", (e) => {
        if (e.key !== "Enter") return;
        e.preventDefault();
        clearTimeout(espera);
        buscar(copiarInput.value);
    });
    // Un Enter en las piezas o el precio tampoco debe registrar el producto.
    contenedor.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });

    menudeoInput?.addEventListener("input", () => editor?.refrescar());

    // ---------- Último que registraste ----------
    fetch(seccion.dataset.urlUltimo)
        .then(r => r.json())
        .then(({ producto }) => {
            if (!producto) return;
            document.getElementById("pc-ultimo-texto").textContent =
                `${producto.nombre} (${resumen(producto.presentaciones)})`;
            document.getElementById("pc-ultimo").classList.remove("hidden");
            document.getElementById("pc-ultimo-usar").addEventListener("click", () => usarDe(producto));
        })
        .catch(() => { /* sin el atajo se puede seguir igual */ });

    editable(iniciales);

    return {
        /** Variante nueva: trae los precios por cantidad de la variante base, editables. */
        deVariante(plantilla) {
            editable(copiarFilas(plantilla.presentaciones));
        },
        /** Producto que ya existe (solo se le agrega inventario): se enseñan sin editar y no se mandan. */
        deExistente(producto) {
            soloLectura = true;
            crearEditor(contenedor, { filas: copiarFilas(producto.presentaciones), menudeo, soloLeer: true });
            copiarBox.classList.add("hidden");
            oculto.value = "";
            errores.classList.add("hidden");
        },
        /** Se borró el código: si enseñaba los de un producto existente, vuelve a quedar vacío y editable. */
        limpiar() {
            if (!soloLectura) return;
            editable([]);
            decir("");
        },
    };
}
