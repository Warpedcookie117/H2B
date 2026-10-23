// compraste.js — Modal "¿Compraste algo?" del POS (app caja_chica)
//
// Vales (a quién y cuánto se le prestó) y gastos (qué se compró y cuánto
// costó). Los dos salen de la cajita de la responsable de servicios; el
// servidor (caja_chica/views/pos.py) valida y guarda, aquí solo se pinta.
//
// Nombres: se eligen de los ya registrados para no crear "Pablo" y "pabblo".
// Si se escribe uno nuevo parecido a uno registrado, el servidor responde 409
// con sugerencias y la cajera elige o confirma que es otra persona.
//
// Los nombres vienen de lo que escribe el personal → todo con textContent.

import { formatearMoneda, getCookie } from "../pos/core.js";

const URL_ESTADO = "/caja-chica/pos/estado/";
const URL_VALE   = "/caja-chica/pos/vales/";
const URL_GASTO  = "/caja-chica/pos/gastos/";
const MAX_SUGERENCIAS = 8;

const $ = (id) => document.getElementById(id);

let personas = [];          // [{id, nombre, clave}]
let personaId = null;       // la elegida de la lista (null: se escribió a mano)
let indiceActivo = -1;      // sugerencia resaltada con el teclado
let enviando = false;


// ============================================================
// 1. Servidor
// ============================================================

async function pedir(url, opciones = {}) {
    const resp = await fetch(url, {
        ...opciones,
        headers: { "Content-Type": "application/json", "X-CSRFToken": getCookie("csrftoken") },
    });
    let data = null;
    try { data = await resp.json(); } catch { /* sin JSON */ }
    return { status: resp.status, data: data || {} };
}

const mandar = (url, cuerpo) => pedir(url, { method: "POST", body: JSON.stringify(cuerpo) });


// ============================================================
// 2. Nombres: misma clave que el servidor (domain/nombres.clave_de)
// ============================================================

function clave(texto) {
    return String(texto || "")
        .normalize("NFD").replace(/[̀-ͯ]/g, "")
        .toLowerCase().replace(/[^a-zñ\s]/g, " ")
        .split(/\s+/).filter(Boolean).join(" ");
}

function sugerenciasPara(texto) {
    const q = clave(texto);
    const empiezan = [], contienen = [];
    personas.forEach(p => {
        if (!q || p.clave.startsWith(q)) empiezan.push(p);
        else if (p.clave.includes(q)) contienen.push(p);
    });
    return [...empiezan, ...contienen].slice(0, MAX_SUGERENCIAS);
}


// ============================================================
// 3. Pintar
// ============================================================

function el(tag, clase, texto) {
    const nodo = document.createElement(tag);
    if (clase) nodo.className = clase;
    if (texto != null) nodo.textContent = String(texto);
    return nodo;
}

function aviso(texto, tipo = "ok") {
    const p = $("cc-aviso");
    p.textContent = texto || "";
    p.className = `cc-aviso cc-aviso--${tipo}`;
    p.hidden = !texto;
}

function pintarCajita(duena) {
    const p = $("cc-cajita");
    p.textContent = duena ? `El dinero sale de la cajita de ${duena}.` : "";
    p.hidden = !duena;
}

function pintarHoy(lista) {
    const ul = $("cc-hoy-lista");
    if (!lista.length) {
        ul.replaceChildren(el("li", "cc-hoy__vacio", "Todavía no hay vales ni gastos."));
        return;
    }
    ul.replaceChildren(...lista.map(m => {
        const li = el("li", "cc-hoy__item");
        li.append(
            el("span", `cc-hoy__tipo cc-hoy__tipo--${m.tipo}`, m.tipo_texto),
            el("span", "cc-hoy__concepto", m.concepto),
            el("span", "cc-hoy__monto", `$${formatearMoneda(m.monto)}`),
            el("span", "cc-hoy__hora", m.hora),
        );
        return li;
    }));
}

function cerrarSugerencias() {
    $("cc-sugerencias").hidden = true;
    $("cc-nombre").setAttribute("aria-expanded", "false");
    indiceActivo = -1;
}

function pintarSugerencias() {
    const ul = $("cc-sugerencias");
    const lista = personaId === null ? sugerenciasPara($("cc-nombre").value) : [];
    if (!lista.length) { cerrarSugerencias(); return; }
    indiceActivo = Math.min(indiceActivo, lista.length - 1);
    ul.replaceChildren(...lista.map((p, i) => {
        const li = el("li", `cc-sugerencia${i === indiceActivo ? " cc-sugerencia--activa" : ""}`, p.nombre);
        li.setAttribute("role", "option");
        li.setAttribute("aria-selected", String(i === indiceActivo));
        // mousedown: antes de que el input pierda el foco y se cierre la lista
        li.addEventListener("mousedown", (e) => { e.preventDefault(); elegirPersona(p); });
        return li;
    }));
    ul.hidden = false;
    $("cc-nombre").setAttribute("aria-expanded", "true");
}

function pintarParecido(sugerencias) {
    const caja = $("cc-parecido");
    if (!sugerencias) { caja.hidden = true; return; }
    $("cc-parecido-opciones").replaceChildren(...sugerencias.map(s => {
        const b = el("button", "cc-parecido__opcion", `Sí, es ${s.nombre}`);
        b.type = "button";
        b.addEventListener("click", () => { elegirPersona(s); guardarVale(); });
        return b;
    }));
    caja.hidden = false;
}


// ============================================================
// 4. Acciones
// ============================================================

function elegirPersona(p) {
    personaId = p.id;
    $("cc-nombre").value = p.nombre;
    cerrarSugerencias();
    pintarParecido(null);
    $("cc-monto-vale").focus();
}

async function cargarEstado() {
    const { status, data } = await pedir(URL_ESTADO);
    if (status !== 200) {
        aviso(data.mensaje || "No se pudo abrir. Intenta de nuevo.", "error");
        return;
    }
    personas = (data.personas || []).map(p => ({ ...p, clave: clave(p.nombre) }));
    pintarCajita(data.duena);
    pintarHoy(data.sin_corte || []);
}

async function guardar(url, cuerpo, alTerminar) {
    if (enviando) return;
    enviando = true;
    try {
        const { status, data } = await mandar(url, cuerpo);
        if (status === 409 && data.status === "parecido") {
            aviso("");
            pintarParecido(data.sugerencias || []);
            return;
        }
        if (status !== 201) {
            aviso(data.mensaje || "No se pudo guardar. Intenta de nuevo.", "error");
            return;
        }
        aviso(data.mensaje, "ok");
        alTerminar();
        await cargarEstado();
    } catch (e) {
        console.error("[caja_chica] no se pudo guardar:", e);
        aviso("Sin conexión. No se guardó; intenta de nuevo.", "error");
    } finally {
        enviando = false;
    }
}

function limpiarVale() {
    personaId = null;
    $("cc-nombre").value = "";
    $("cc-monto-vale").value = "";
    pintarParecido(null);
}

function guardarVale(esOtraPersona = false) {
    const cuerpo = { monto: $("cc-monto-vale").value };
    if (personaId !== null) cuerpo.persona_id = personaId;
    else cuerpo.nombre = $("cc-nombre").value;
    if (esOtraPersona) cuerpo.es_otra_persona = true;
    return guardar(URL_VALE, cuerpo, limpiarVale);
}

function guardarGasto() {
    return guardar(URL_GASTO, {
        descripcion: $("cc-descripcion").value,
        monto: $("cc-monto-gasto").value,
    }, () => { $("cc-descripcion").value = ""; $("cc-monto-gasto").value = ""; });
}

function cambiarPestana(cual) {
    document.querySelectorAll("[data-cc-tab]").forEach(tab => {
        const activa = tab.dataset.ccTab === cual;
        tab.classList.toggle("cc-tab--activa", activa);
        tab.setAttribute("aria-selected", String(activa));
    });
    $("cc-form-vale").hidden = cual !== "vale";
    $("cc-form-gasto").hidden = cual !== "gasto";
    aviso("");
    (cual === "vale" ? $("cc-nombre") : $("cc-descripcion")).focus();
}

function abrir() {
    limpiarVale();
    $("cc-descripcion").value = "";
    $("cc-monto-gasto").value = "";
    aviso("");
    $("modal-compraste").classList.remove("pos-modal--hidden");
    cambiarPestana("vale");
    cargarEstado();
}

function cerrar() {
    cerrarSugerencias();
    $("modal-compraste").classList.add("pos-modal--hidden");
    setTimeout(() => $("scan-input")?.focus(), 0);
}


// ============================================================
// 5. Arranque
// ============================================================

function init() {
    const modal = $("modal-compraste");
    const boton = $("btn-compraste");
    if (!modal || !boton) return;

    boton.addEventListener("click", abrir);
    $("cc-cerrar").addEventListener("click", cerrar);
    modal.addEventListener("click", (e) => { if (e.target === modal) cerrar(); });

    // Las teclas del modal no le llegan al lector de códigos del POS
    // (buscador_productos.js escucha el teclado de toda la página).
    modal.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Escape" && $("cc-sugerencias").hidden) { e.preventDefault(); cerrar(); }
    });

    document.querySelectorAll("[data-cc-tab]").forEach(tab =>
        tab.addEventListener("click", () => cambiarPestana(tab.dataset.ccTab)));

    const nombre = $("cc-nombre");
    nombre.addEventListener("input", () => { personaId = null; indiceActivo = -1; pintarParecido(null); pintarSugerencias(); });
    nombre.addEventListener("focus", pintarSugerencias);
    nombre.addEventListener("blur", cerrarSugerencias);
    nombre.addEventListener("keydown", (e) => {
        const abierta = !$("cc-sugerencias").hidden;
        const lista = sugerenciasPara(nombre.value);
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            if (!abierta) { pintarSugerencias(); return; }
            const paso = e.key === "ArrowDown" ? 1 : -1;
            indiceActivo = (indiceActivo + paso + lista.length) % lista.length;
            pintarSugerencias();
        } else if (e.key === "Enter" && abierta && indiceActivo >= 0) {
            e.preventDefault();
            elegirPersona(lista[indiceActivo]);
        } else if (e.key === "Escape" && abierta) {
            e.preventDefault();
            cerrarSugerencias();
        }
    });

    $("cc-form-vale").addEventListener("submit", (e) => { e.preventDefault(); guardarVale(); });
    $("cc-otra-persona").addEventListener("click", () => guardarVale(true));
    $("cc-form-gasto").addEventListener("submit", (e) => { e.preventDefault(); guardarGasto(); });
}

if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
else init();
