// ============================================================
// LISTA DE PRECIOS — precios por cantidad de muchos productos (solo dueñas)
//
// Como la orden de reabastecimiento: se escanea, cada producto sale con sus
// precios, se ponen los nuevos y al final se guarda todo junto en una sola
// operación (todo o nada). El borrador vive en localStorage para no perder
// la lista si se cierra la pestaña. El servidor
// (inventario/views/presentaciones.py) valida todo otra vez.
// ============================================================
import { crearEditor, copiarFilas, erroresDe, limpiarFilas } from "../precios_cantidad/tarjeta.js";

const CTX = window.LISTA_PRECIOS_CTX;
const LS_KEY = `lista_precios_v1_${CTX.empleadoId}`;
const $ = (id) => document.getElementById(id);

// Estado: [{ producto, originales, filas, errores }]
//   producto:   lo que mandó el servidor (nombre, foto, precios normales…)
//   originales: sus precios por cantidad cuando se escaneó (para no pisar
//               cambios de otra persona)
let items = [];
let idempotencyKey = nuevaLlave();

function nuevaLlave() {
    return (crypto.randomUUID?.() || `${Date.now()}-${Math.random()}`);
}

function csrf() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function dinero(n) {
    if (n === "" || n === null || n === undefined) return "-";
    return "$" + Number(n).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ---------- Borrador ----------
function guardarBorrador() {
    try {
        localStorage.setItem(LS_KEY, JSON.stringify(items.map(({ producto, originales, filas }) =>
            ({ producto, originales, filas }))));
    } catch { /* sin borrador se puede seguir */ }
}

function cargarBorrador() {
    try {
        const datos = JSON.parse(localStorage.getItem(LS_KEY) || "[]");
        if (Array.isArray(datos)) items = datos.map(d => ({ ...d, errores: [] }));
    } catch { items = []; }
}

function borrarBorrador() {
    try { localStorage.removeItem(LS_KEY); } catch { /* nada */ }
}

// ---------- Cambios ----------
const clave = (f) => `${f.tipo}-${f.piezas}`;

/** {nuevos, cambiados, quitados} de un producto, comparando con como estaba. */
function cambiosDe(item) {
    const antes = new Map(limpiarFilas(item.originales).map(f => [clave(f), Number(f.precio)]));
    const ahora = new Map(limpiarFilas(item.filas).map(f => [clave(f), Number(f.precio)]));
    let nuevos = 0, cambiados = 0, quitados = 0;
    for (const [k, precio] of ahora) {
        if (!antes.has(k)) nuevos++;
        else if (antes.get(k) !== precio) cambiados++;
    }
    for (const k of antes.keys()) if (!ahora.has(k)) quitados++;
    return { nuevos, cambiados, quitados };
}

const tieneCambios = (item) => Object.values(cambiosDe(item)).some(Boolean);

// ---------- Pintar ----------
function mensaje(texto, ok = true) {
    const m = $("lp-mensaje");
    m.textContent = texto;
    m.className = `mt-2 text-xs font-black ${ok ? "text-[#047857]" : "text-[#B5005A]"}`;
    m.classList.toggle("hidden", !texto);
}

function actualizarBoton() {
    const conCambios = items.filter(tieneCambios).length;
    $("lp-contador").textContent = conCambios;
    $("lp-revisar").disabled = conCambios === 0;
    $("lp-vacia").classList.toggle("hidden", items.length > 0);
    $("lp-vaciar").classList.toggle("hidden", items.length === 0);
}

function pintarErrores(card, item) {
    const caja = card.querySelector("[data-errores]");
    const lista = [...(item.errores || []), ...erroresDe(item.filas)];
    caja.innerHTML = "";
    lista.forEach(e => { const li = document.createElement("li"); li.textContent = e; caja.append(li); });
    caja.classList.toggle("hidden", !lista.length);
    card.classList.toggle("border-[#B5005A]", !!(item.errores || []).length);
}

function pintarTarjeta(item, i) {
    const p = item.producto;
    const card = document.createElement("div");
    card.dataset.productoId = p.producto_id;
    card.className = "border-4 border-black shadow-[4px_4px_0_0_black] bg-white p-3 space-y-3";

    const cabeza = document.createElement("div");
    cabeza.className = "flex gap-3 items-start";
    const img = document.createElement("img");
    img.src = p.foto_url || CTX.noImage;
    img.alt = "";
    img.className = "w-14 h-14 object-cover border-2 border-black shrink-0";
    img.onerror = () => { img.src = CTX.noImage; };
    const info = document.createElement("div");
    info.className = "min-w-0 flex-1";
    const nombre = document.createElement("p");
    nombre.className = "font-black text-sm uppercase leading-tight";
    nombre.textContent = p.nombre;
    const detalle = document.createElement("p");
    detalle.className = "text-xs font-bold text-black/60";
    detalle.textContent = p.detalle || "";
    const normales = document.createElement("p");
    normales.className = "text-xs font-black mt-1 flex flex-wrap gap-x-3";
    [["Menudeo", p.precio_menudeo], ["Mayoreo", p.precio_mayoreo], ["Docena", p.precio_docena]]
        .filter(([, precio]) => precio !== "" && precio !== null && precio !== undefined)
        .forEach(([etiqueta, precio]) => {
        const s = document.createElement("span");
        s.className = "whitespace-nowrap";
        s.textContent = `${etiqueta} ${dinero(precio)}`;
        normales.append(s);
    });
    info.append(nombre, detalle, normales);
    const quitar = document.createElement("button");
    quitar.type = "button";
    quitar.textContent = "Quitar de la lista";
    quitar.className = "border-2 border-black bg-white font-black text-[10px] uppercase px-2 py-1 shrink-0";
    quitar.addEventListener("click", () => {
        items.splice(i, 1);
        guardarBorrador();
        pintar();
    });
    cabeza.append(img, info, quitar);

    const editorBox = document.createElement("div");
    const errores = document.createElement("ul");
    errores.dataset.errores = "";
    errores.className = "hidden text-xs font-black text-[#B5005A] space-y-1";

    crearEditor(editorBox, {
        filas: item.filas,
        menudeo: () => p.precio_menudeo,
        onCambio: (filas) => {
            item.filas = filas;
            item.errores = [];
            pintarErrores(card, item);
            guardarBorrador();
            actualizarBoton();
        },
    });
    editorBox.addEventListener("keydown", (e) => { if (e.key === "Enter") e.preventDefault(); });

    card.append(cabeza, editorBox, errores);

    if (i > 0) {
        const copiar = document.createElement("button");
        copiar.type = "button";
        copiar.textContent = "Copiar precios del anterior";
        copiar.className = "btn-90s border-2 border-black shadow-[2px_2px_0_0_black] bg-[#3A86FF] text-white " +
                           "font-black text-xs uppercase tracking-wide px-3 py-1.5";
        copiar.addEventListener("click", () => {
            item.filas = copiarFilas(limpiarFilas(items[i - 1].filas));
            item.errores = [];
            guardarBorrador();
            pintar();
        });
        card.append(copiar);
    }

    pintarErrores(card, item);
    return card;
}

function pintar() {
    const lista = $("lp-lista");
    lista.innerHTML = "";
    items.forEach((item, i) => lista.append(pintarTarjeta(item, i)));
    actualizarBoton();
}

function resaltar(productoId) {
    const card = document.querySelector(`#lp-lista [data-producto-id="${productoId}"]`);
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("ring-4", "ring-[#FF006E]");
    setTimeout(() => card.classList.remove("ring-4", "ring-[#FF006E]"), 1500);
}

// ---------- Agregar ----------
function agregar(producto) {
    $("lp-resultados").classList.add("hidden");
    $("lp-buscar").value = "";
    if (items.some(it => it.producto.producto_id === producto.producto_id)) {
        mensaje(`${producto.nombre} ya está en la lista.`);
        resaltar(producto.producto_id);
        return;
    }
    const filas = copiarFilas(producto.presentaciones);
    items.push({ producto, originales: filas, filas: copiarFilas(filas), errores: [] });
    guardarBorrador();
    pintar();
    mensaje("");
    resaltar(producto.producto_id);
}

function mostrarOpciones(productos) {
    const caja = $("lp-resultados");
    caja.innerHTML = "";
    productos.forEach(p => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "w-full text-left px-3 py-2 border-b-2 border-black/10 hover:bg-[#FFF7E0]";
        const n = document.createElement("span");
        n.className = "block font-black text-sm";
        n.textContent = p.nombre;
        const d = document.createElement("span");
        d.className = "block text-xs font-bold text-black/60";
        d.textContent = [p.detalle, p.codigo_barras].filter(Boolean).join(" · ");
        b.append(n, d);
        b.addEventListener("click", () => agregar(p));
        caja.append(b);
    });
    caja.classList.remove("hidden");
}

let pedido = null;
async function buscar(q, { escaneo = false } = {}) {
    q = q.trim();
    if (q.length < 2) { $("lp-resultados").classList.add("hidden"); return; }
    pedido?.abort();
    pedido = new AbortController();
    let datos;
    try {
        const r = await fetch(`${CTX.urls.buscar}?q=${encodeURIComponent(q)}`, { signal: pedido.signal });
        datos = await r.json();
        if (!r.ok) { mensaje(datos.errors?.[0] || "No se pudo buscar.", false); return; }
    } catch (e) {
        if (e.name !== "AbortError") mensaje("No se pudo buscar. Revisa el internet.", false);
        return;
    }
    const productos = datos.productos || [];
    if (!productos.length) {
        $("lp-resultados").classList.add("hidden");
        mensaje(escaneo ? "No encontré ese código." : "No encontré ese producto.", false);
        return;
    }
    // Un código con un solo producto entra directo; si son variantes, se escoge.
    if (escaneo && datos.por_codigo && productos.length === 1) {
        agregar(productos[0]);
        return;
    }
    mensaje(datos.por_codigo ? "Ese código tiene varias variantes. ¿Cuál es?" : "");
    mostrarOpciones(productos);
}

// ---------- Guardar ----------
function abrirResumen() {
    const conCambios = items.filter(tieneCambios);
    const total = { nuevos: 0, cambiados: 0, quitados: 0 };
    conCambios.forEach(it => {
        const c = cambiosDe(it);
        for (const k in total) total[k] += c[k];
    });
    const conErrores = conCambios.filter(it => erroresDe(it.filas).length);
    const cuerpo = $("lp-modal-cuerpo");
    cuerpo.innerHTML = "";
    const s = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
    const lineas = [`Vas a cambiar precios de ${s(conCambios.length, "producto", "productos")}:`];
    if (total.nuevos)    lineas.push(`${s(total.nuevos, "precio nuevo", "precios nuevos")}`);
    if (total.cambiados) lineas.push(`${s(total.cambiados, "precio que cambia", "precios que cambian")}`);
    if (total.quitados)  lineas.push(`${s(total.quitados, "precio que se quita", "precios que se quitan")}`);
    lineas.forEach(t => { const p = document.createElement("p"); p.textContent = t; cuerpo.append(p); });
    if (conErrores.length) {
        const p = document.createElement("p");
        p.className = "text-[#B5005A] font-black";
        p.textContent = `Corrige ${conErrores.length} producto${conErrores.length === 1 ? "" : "s"} marcado${conErrores.length === 1 ? "" : "s"} en rojo antes de guardar.`;
        cuerpo.append(p);
    }
    $("lp-modal-guardar").disabled = conErrores.length > 0;
    $("lp-modal").classList.remove("hidden");
}

async function guardar() {
    const btn = $("lp-modal-guardar");
    btn.disabled = true;
    btn.textContent = "Guardando...";
    const renglones = items.filter(tieneCambios).map(it => ({
        producto_id: it.producto.producto_id,
        originales: limpiarFilas(it.originales),
        presentaciones: limpiarFilas(it.filas),
    }));

    let datos = {}, ok = false;
    try {
        const r = await fetch(CTX.urls.guardar, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
            body: JSON.stringify({ renglones, idempotency_key: idempotencyKey }),
        });
        datos = await r.json().catch(() => ({}));
        ok = r.ok && datos.success;
    } catch {
        datos = { errors: ["No se pudo guardar. Revisa el internet y vuelve a intentar."] };
    }
    btn.textContent = "Guardar";
    btn.disabled = false;
    $("lp-modal").classList.add("hidden");

    if (!ok) {
        const porProducto = datos.por_producto || {};
        items.forEach(it => { it.errores = porProducto[String(it.producto.producto_id)] || []; });
        pintar();
        mensaje((datos.errors || ["No se pudo guardar."])[0], false);
        const primero = Object.keys(porProducto)[0];
        if (primero) resaltar(primero);
        return;
    }

    const r = datos.resumen;
    items = [];
    idempotencyKey = nuevaLlave();
    borrarBorrador();
    pintar();
    mensaje(`Listo, ya quedaron los precios de ${r.productos} producto${r.productos === 1 ? "" : "s"}.`);
    window.scrollTo({ top: 0, behavior: "smooth" });
}

// ---------- Eventos ----------
const input = $("lp-buscar");
let espera = null;
input.addEventListener("input", () => {
    clearTimeout(espera);
    espera = setTimeout(() => buscar(input.value), 350);
});
input.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    e.preventDefault();
    clearTimeout(espera);
    buscar(input.value, { escaneo: true });
});
document.addEventListener("click", (e) => {
    if (!e.target.closest("#lp-resultados") && e.target !== input) $("lp-resultados").classList.add("hidden");
});

$("lp-revisar").addEventListener("click", abrirResumen);
$("lp-modal-regresar").addEventListener("click", () => $("lp-modal").classList.add("hidden"));
$("lp-modal-guardar").addEventListener("click", guardar);
$("lp-vaciar").addEventListener("click", () => {
    if (!confirm("¿Vaciar la lista? Lo que no guardaste se pierde.")) return;
    items = [];
    borrarBorrador();
    pintar();
    mensaje("");
});

if (typeof initEscanerCamara === "function") {
    initEscanerCamara((codigo) => {
        input.value = codigo;
        buscar(codigo, { escaneo: true });
    });
}

cargarBorrador();
pintar();
if (items.length) mensaje("Se recuperó la lista que no habías guardado.");
input.focus();
