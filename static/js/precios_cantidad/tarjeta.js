// ============================================================
// PRECIOS POR CANTIDAD — editor de una tarjeta (Media docena, Decena, Caja)
//
// Lo usan el alta del producto, la Lista de precios y el detalle. Solo pinta
// y junta las filas; las reglas de verdad están en el servidor
// (inventario/services/presentacion_service.py), que es el que valida al guardar.
//
// Forma de una fila: { tipo: "caja", piezas: 24, precio: "550" }
// ============================================================

// color: el mismo del botón en el POS (static/css/pos.css, .pos-pres--*)
export const TIPOS = [
    { tipo: "media_docena", nombre: "Media docena", piezas: 6,    color: "bg-[#FB5607] text-white" },
    { tipo: "decena",       nombre: "Decena",       piezas: 10,   color: "bg-[#00BBF9] text-black" },
    { tipo: "caja",         nombre: "Caja",         piezas: null, color: "bg-[#06D6A0] text-black" },   // la dueña escribe las piezas
];
const POR_TIPO = Object.fromEntries(TIPOS.map(t => [t.tipo, t]));
export const PIEZAS_MINIMAS_CAJA = 2;

function dinero(n) {
    return "$" + Number(n).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function numero(valor) {
    const n = parseFloat(String(valor ?? "").replace(",", "."));
    return Number.isFinite(n) ? n : null;
}

/** Filas tal como se mandan al servidor (sin las que quedaron sin precio). */
export function limpiarFilas(filas) {
    return filas
        .filter(f => String(f.precio ?? "").trim() !== "")
        .map(f => ({
            tipo: f.tipo,
            piezas: POR_TIPO[f.tipo]?.piezas ?? (parseInt(f.piezas, 10) || null),
            precio: String(f.precio).trim(),
        }));
}

/** Copia de las filas de un producto (sin id), para copiar a otro. */
export function copiarFilas(presentaciones) {
    return (presentaciones || []).map(p => ({ tipo: p.tipo, piezas: p.piezas, precio: p.precio }));
}

/** "Caja de 24 a $550 · Media docena a $150", para resúmenes de una línea. */
export function resumen(presentaciones) {
    return (presentaciones || [])
        .map(p => `${p.tipo === "caja" ? `Caja de ${p.piezas}` : POR_TIPO[p.tipo]?.nombre} a ${dinero(p.precio)}`)
        .join(" · ");
}

/** Errores que se pueden ver antes de mandar (el servidor revisa todo otra vez). */
export function erroresDe(filas) {
    const errores = [];
    const vistas = new Set();
    for (const f of filas) {
        if (String(f.precio ?? "").trim() === "") continue;
        const t = POR_TIPO[f.tipo];
        const precio = numero(f.precio);
        if (precio === null || precio <= 0) errores.push(`${t.nombre}: el precio tiene que ser mayor a $0.`);
        const piezas = t.piezas ?? parseInt(f.piezas, 10);
        if (t.piezas === null && !(piezas >= PIEZAS_MINIMAS_CAJA)) {
            errores.push(`Caja: escribe cuántas piezas trae (${PIEZAS_MINIMAS_CAJA} o más).`);
        }
        const clave = `${f.tipo}-${piezas}`;
        if (vistas.has(clave)) errores.push(`${t.tipo === "caja" ? `Caja de ${piezas}` : t.nombre} está dos veces.`);
        vistas.add(clave);
    }
    return [...new Set(errores)];
}

/**
 * Pinta el editor dentro de `contenedor`.
 *   filas:     filas iniciales
 *   menudeo:   () => precio de menudeo actual (para "sale a" y el aviso), o null
 *   onCambio:  (filas) => void, cada vez que algo cambia
 *   soloLeer:  true para enseñarlos sin poder editar
 * Regresa { getFilas, setFilas, refrescar }.
 */
export function crearEditor(contenedor, { filas = [], menudeo = () => null, onCambio = () => {}, soloLeer = false } = {}) {
    let estado = filas.map(f => ({ ...f }));

    const lista = document.createElement("div");
    lista.className = "space-y-2";

    const botones = document.createElement("div");
    botones.className = "flex flex-wrap items-center gap-2";

    contenedor.innerHTML = "";
    contenedor.append(lista);
    if (!soloLeer) contenedor.append(botones);

    function avisar() { onCambio(estado.map(f => ({ ...f }))); }

    function pintarBotones() {
        botones.innerHTML = '<span class="text-xs font-black text-black/70">Agregar precio por:</span>';
        for (const t of TIPOS) {
            const yaEsta = t.piezas !== null && estado.some(f => f.tipo === t.tipo);
            const b = document.createElement("button");
            b.type = "button";
            b.textContent = t.nombre;
            b.disabled = yaEsta;
            b.className = `btn-90s border-2 border-black shadow-[2px_2px_0_0_black] ${t.color} ` +
                          "font-black text-xs uppercase tracking-wide px-3 py-1.5 " +
                          "disabled:opacity-30 disabled:cursor-not-allowed disabled:shadow-none";
            b.addEventListener("click", () => {
                estado.push({ tipo: t.tipo, piezas: t.piezas ?? "", precio: "" });
                pintar();
                avisar();
                const inputs = lista.querySelectorAll("input");
                // Caja: primero las piezas; las demás: el precio.
                inputs[inputs.length - (t.piezas === null ? 2 : 1)]?.focus();
            });
            botones.append(b);
        }
    }

    function textoAyuda(f) {
        const t = POR_TIPO[f.tipo];
        const piezas = t.piezas ?? parseInt(f.piezas, 10);
        const precio = numero(f.precio);
        if (!(piezas >= 1) || precio === null || precio <= 0) return { ayuda: "", aviso: "" };
        const ayuda = `Cada pieza sale a ${dinero(precio / piezas)}`;
        const men = numero(menudeo());
        const sueltas = men ? men * piezas : null;
        const aviso = sueltas && precio > sueltas
            ? `Ojo: así sale más caro. ${piezas} piezas sueltas cuestan ${dinero(sueltas)}.`
            : "";
        return { ayuda, aviso };
    }

    function pintarAyuda(fila, f) {
        const { ayuda, aviso } = textoAyuda(f);
        fila.querySelector("[data-ayuda]").textContent = ayuda;
        const a = fila.querySelector("[data-aviso]");
        a.textContent = aviso;
        a.classList.toggle("hidden", !aviso);
    }

    function pintar() {
        lista.innerHTML = "";
        if (!estado.length) {
            const vacio = document.createElement("p");
            vacio.className = "text-xs font-bold text-black/50";
            vacio.textContent = soloLeer
                ? "No se vende por caja ni por media docena."
                : "Todavía no tiene precio por caja ni por media docena.";
            lista.append(vacio);
        }

        estado.forEach((f, i) => {
            const t = POR_TIPO[f.tipo];
            const fila = document.createElement("div");
            fila.className = "border-2 border-black bg-white px-2 py-2";

            const linea = document.createElement("div");
            linea.className = "flex flex-wrap items-center gap-2";

            const nombre = document.createElement("span");
            nombre.className = `font-black text-sm border-2 border-black px-2 py-0.5 ${t.color}`;
            nombre.textContent = t.piezas === null ? "Caja de" : t.nombre;
            linea.append(nombre);

            if (soloLeer) {
                const texto = document.createElement("span");
                texto.className = "font-black text-sm";
                texto.textContent = (t.piezas === null ? `${f.piezas} piezas ` : "") + `a ${dinero(f.precio)}`;
                linea.append(texto);
            } else {
                if (t.piezas === null) {
                    const piezas = document.createElement("input");
                    piezas.type = "number";
                    piezas.min = String(PIEZAS_MINIMAS_CAJA);
                    piezas.step = "1";
                    piezas.inputMode = "numeric";
                    piezas.placeholder = "Piezas";
                    piezas.value = f.piezas ?? "";
                    piezas.style.fontSize = "16px";
                    piezas.className = "w-20 border-2 border-black px-2 py-1 font-black text-center";
                    piezas.addEventListener("input", () => { f.piezas = piezas.value; pintarAyuda(fila, f); avisar(); });
                    const pz = document.createElement("span");
                    pz.className = "text-sm font-black";
                    pz.textContent = "piezas";
                    linea.append(piezas, pz);
                }

                const signo = document.createElement("span");
                signo.className = "font-black text-sm";
                signo.textContent = "a $";
                const precio = document.createElement("input");
                precio.type = "number";
                precio.min = "0";
                precio.step = "0.5";
                precio.inputMode = "decimal";
                precio.placeholder = "Precio";
                precio.value = f.precio ?? "";
                precio.style.fontSize = "16px";
                precio.className = "w-24 border-2 border-black px-2 py-1 font-black text-center";
                precio.addEventListener("input", () => { f.precio = precio.value; pintarAyuda(fila, f); avisar(); });
                linea.append(signo, precio);
            }

            const ayuda = document.createElement("span");
            ayuda.dataset.ayuda = "";
            ayuda.className = "text-xs font-bold text-black/60";
            linea.append(ayuda);

            if (!soloLeer) {
                const quitar = document.createElement("button");
                quitar.type = "button";
                quitar.textContent = "Quitar";
                quitar.className = "ml-auto border-2 border-black bg-white text-black font-black text-[11px] uppercase px-2 py-1";
                quitar.addEventListener("click", () => { estado.splice(i, 1); pintar(); avisar(); });
                linea.append(quitar);
            }

            const aviso = document.createElement("p");
            aviso.dataset.aviso = "";
            aviso.className = "hidden mt-1 text-xs font-bold text-[#B5005A]";

            fila.append(linea, aviso);
            lista.append(fila);
            pintarAyuda(fila, f);
        });

        if (!soloLeer) pintarBotones();
    }

    pintar();

    return {
        getFilas: () => estado.map(f => ({ ...f })),
        setFilas(nuevas) { estado = (nuevas || []).map(f => ({ ...f })); pintar(); avisar(); },
        /** Vuelve a calcular "sale a" y el aviso (p. ej. si cambió el menudeo). */
        refrescar() { lista.querySelectorAll(":scope > div").forEach((fila, i) => estado[i] && pintarAyuda(fila, estado[i])); },
    };
}
