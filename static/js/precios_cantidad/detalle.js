// ============================================================
// PRECIOS POR CANTIDAD en el detalle del producto.
// Las dueñas los cambian y guardan aquí mismo (es una Lista de precios de un
// solo producto: mismo endpoint, mismas reglas). Los demás solo los ven.
// ============================================================
import { crearEditor, copiarFilas, erroresDe, limpiarFilas } from "./tarjeta.js";

const seccion = document.getElementById("precios-cantidad-detalle");

if (seccion) {
    const puedeEditar = seccion.dataset.puedeEditar === "1";
    const contenedor = document.getElementById("pcd-editor");
    const errores = document.getElementById("pcd-errores");
    const boton = document.getElementById("pcd-guardar");
    const mensaje = document.getElementById("pcd-mensaje");

    let originales = copiarFilas(JSON.parse(document.getElementById("pcd-datos").textContent));
    let filas = copiarFilas(originales);
    let editor = null;

    const firma = (lista) => JSON.stringify(limpiarFilas(lista).map(f => [f.tipo, f.piezas, Number(f.precio)]).sort());

    function decir(texto, ok = true) {
        if (!mensaje) return;
        mensaje.textContent = texto;
        mensaje.className = `text-xs font-black ${ok ? "text-[#047857]" : "text-[#B5005A]"}`;
        mensaje.classList.toggle("hidden", !texto);
    }

    function pintarErrores(lista) {
        errores.innerHTML = "";
        lista.forEach(e => { const li = document.createElement("li"); li.textContent = e; errores.append(li); });
        errores.classList.toggle("hidden", !lista.length);
    }

    function montar() {
        editor = crearEditor(contenedor, {
            filas,
            menudeo: () => seccion.dataset.menudeo,
            soloLeer: !puedeEditar,
            onCambio: (nuevas) => {
                filas = nuevas;
                const lista = erroresDe(filas);
                pintarErrores(lista);
                decir("");
                if (boton) boton.disabled = lista.length > 0 || firma(filas) === firma(originales);
            },
        });
    }

    contenedor.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });

    boton?.addEventListener("click", async () => {
        boton.disabled = true;
        const productoId = Number(seccion.dataset.productoId);
        let datos = {}, ok = false;
        try {
            const r = await fetch(seccion.dataset.urlGuardar, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]").value,
                },
                body: JSON.stringify({ renglones: [{
                    producto_id: productoId,
                    originales: limpiarFilas(originales),
                    presentaciones: limpiarFilas(filas),
                }] }),
            });
            datos = await r.json().catch(() => ({}));
            ok = r.ok && datos.success;
        } catch {
            datos = { errors: ["No se pudo guardar. Revisa el internet y vuelve a intentar."] };
        }

        if (!ok) {
            const porProducto = (datos.por_producto || {})[String(productoId)];
            pintarErrores(porProducto || datos.errors || ["No se pudo guardar."]);
            boton.disabled = false;
            return;
        }
        const guardado = (datos.productos || [])[0];
        originales = copiarFilas(guardado ? guardado.presentaciones : limpiarFilas(filas));
        filas = copiarFilas(originales);
        montar();
        boton.disabled = true;
        decir("Listo, se guardaron.");
    });

    montar();
}
