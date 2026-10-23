// reparto.js — Le dice a la cajera a qué caja (y a qué Clip) va el dinero
//
// Hay varias dueñas en la tienda; cada una tiene su caja de efectivo y su
// Clip. La que más vendió en la cuenta (la "receptora") recibe el billete, de
// su caja sale la feria y cobra TODA la tarjeta en su Clip. Aquí se le dice a
// la cajera cómo acomodar el dinero: lo recibido, de qué caja tomar la feria
// y cuánto efectivo le pone de esa caja a cada otra dueña (también si pagaron
// con tarjeta: se paga en el momento, nadie queda debiendo).
// El backend ya calcula todo (llave `reparto_efectivo` de la respuesta del
// cobro, contrato versión 2) y este módulo SOLO lo pinta: aquí no se hacen
// cuentas.
//
// Los nombres de las dueñas vienen de la BD → todo se construye con
// createElement + textContent, nunca con innerHTML.

import { formatearMoneda } from "./core.js";

console.log("[POS:reparto] Módulo cargado");

const PREFIJO = "pos-resultado-reparto";

// Versión del contrato que sabe pintar este módulo. Respuestas de otra
// versión (p. ej. v1 cacheada) → se oculta el bloque.
const VERSION = 2;

// Casos que sabe pintar este módulo
const CASOS = ["varias", "una", "sin_efectivo", "sin_duena"];

const SIN_NOMBRE = "(sin nombre)";


// ============================================================
// 1. Helpers defensivos (el JSON puede venir incompleto)
// ============================================================

// Número seguro: lo que no sea un número finito cuenta como 0
function _num(valor) {
    const n = Number(valor);
    return Number.isFinite(n) ? n : 0;
}

// ¿Vale la pena mostrarlo? Lo que redondea a $0.00 no se menciona
function _hayMonto(valor) {
    return _num(valor) >= 0.005;
}

// "$1,234.50" — mismo formato que el resto del modal de resultado
function _dinero(valor) {
    return `$${formatearMoneda(_num(valor))}`;
}

function _nombre(valor) {
    return (typeof valor === "string" || typeof valor === "number")
        ? String(valor).trim()
        : "";
}

// Crea un elemento con su clase BEM y (opcional) su texto
function _el(tag, sufijo, texto) {
    const el = document.createElement(tag);
    if (sufijo) el.className = `${PREFIJO}__${sufijo}`;
    if (texto !== undefined && texto !== null) el.textContent = String(texto);
    return el;
}

// Nombre de la dueña en negritas (resaltado en CSS)
function _duena(nombre) {
    return _el("strong", "duena", nombre);
}

// Monto destacado (monoespaciado, no se parte en dos renglones)
function _monto(valor) {
    return _el("span", "monto", _dinero(valor));
}

// Mete textos sueltos y nodos (negritas, montos) dentro de `el`
function _llenar(el, partes) {
    partes.forEach(parte => {
        if (parte === null || parte === undefined || parte === "") return;
        el.append(typeof parte === "string" ? document.createTextNode(parte) : parte);
    });
    return el;
}

// Arma un párrafo mezclando textos sueltos y nodos (negritas, montos)
function _parrafo(sufijo, partes) {
    return _llenar(_el("p", sufijo), partes);
}

// Solo los renglones de una lista que traen un monto que mostrar
function _filtrar(lista, campo, etiqueta) {
    if (!Array.isArray(lista)) return [];
    return lista.filter(item => {
        const ok = item && typeof item === "object" && _hayMonto(item[campo]);
        if (!ok) console.warn(`[POS:reparto] renglón de '${etiqueta}' ignorado:`, item);
        return ok;
    });
}

const _listaPasar   = (pasar)    => _filtrar(pasar, "efectivo", "pasar");


// ============================================================
// 2. Piezas del bloque
// ============================================================

// Franja de color de cada dueña en su card, para reconocerla de un vistazo
// (el cuerpo de la card sigue verde = efectivo). Se amarra al PRIMER nombre:
// "Anais Fabiola" → anais, "Ana Fabiola" → ana. Cualquier otra dueña recibe
// un color de COLORES_OTRAS sacado de su id, así siempre le toca el mismo.
const COLOR_POR_NOMBRE = {
    anais:   "#FF006E",   // rosa
    ana:     "#D62828",   // rojizo (Fabiola)
    fabiola: "#D62828",
    yareli:  "#3A86FF",   // azul
    yare:    "#3A86FF",
};
const COLORES_OTRAS = ["#8338EC", "#FF9F1C", "#8D5524", "#4A4E69"];   // morado, ámbar, café, pizarra

function _colorDuena(item) {
    const primero = _nombre(item.nombre).normalize("NFD").replace(/[̀-ͯ]/g, "")
        .toLowerCase().split(/\s+/)[0] || "";
    if (COLOR_POR_NOMBRE[primero]) return COLOR_POR_NOMBRE[primero];
    const semilla = Number.isInteger(item.empleado_id)
        ? item.empleado_id
        : [...primero].reduce((s, c) => s + c.charCodeAt(0), 0);
    return COLORES_OTRAS[Math.abs(semilla) % COLORES_OTRAS.length];
}

// Card con su clase BEM y su variante (p. ej. pago--efectivo)
function _card(sufijo, variante, partes) {
    const div = _el("div", sufijo);
    if (variante) div.classList.add(`${PREFIJO}__${sufijo}--${variante}`);
    return _llenar(div, partes);
}

// [ Recibí en efectivo $500.00 ]  [ Tarjeta: $70.00 Todo fue al Clip de Anais ]
function _pintarPagos(cont, r, clip, nombreClip) {
    const efectivo = _hayMonto(r.recibido);
    if (!efectivo && !clip) return;
    const fila = _el("div", "pagos");
    if (efectivo) {
        fila.append(_card("pago", "efectivo", [
            _el("span", "texto", "Recibí en efectivo"),
            _el("span", "cifra", _dinero(r.recibido)),
        ]));
    }
    if (clip) {
        fila.append(_card("pago", "tarjeta", [
            _el("span", "texto", "Tarjeta:"),
            _el("span", "cifra", _dinero(clip.monto)),
            _llenar(_el("span", "texto"), ["Todo fue al Clip de ", _duena(nombreClip)]),
        ]));
    }
    cont.append(fila);
}

// La feria es de $290.00. Tómala de la caja de Anais   ← la que más vendió
function _pintarFeria(cont, r, receptora) {
    if (!_hayMonto(r.cambio)) return;
    const partes = ["La feria es de ", _monto(r.cambio), "."];
    if (receptora) partes.push(" Tómala de la caja de ", _duena(receptora));
    cont.append(_parrafo("feria", partes));
}

// De la caja de Anais
//   [ Le pones en efectivo $60.00 a Ivan ] [ Le pones en efectivo $10.00 a Yareli ] …
// Una card por dueña, las que sean. Si pagaron con tarjeta (r.del_fondo) se
// pasa igual, del dinero que ya hay en esa caja:
//   De la caja de Anais (aunque pagaron con tarjeta)
// Si no hay que pasarle a nadie:
//   Todo el efectivo va a la caja de Anais
function _pintarCajas(cont, r, receptora) {
    const pasar = _listaPasar(r.pasar);
    if (!pasar.length) {
        if (_hayMonto(r.queda_receptora)) {
            cont.append(_parrafo("leyenda", ["Todo el efectivo va a la caja de ", _duena(receptora)]));
        }
        return;
    }
    cont.append(_parrafo("leyenda", [
        "De la caja de ", _duena(receptora),
        _hayMonto(r.del_fondo) ? " (aunque pagaron con tarjeta)" : "",
    ]));
    const fila = _el("div", "cajas");
    pasar.forEach(item => {
        const card = _card("caja", null, [
            _el("span", "texto", "Le pones"),
            _el("span", "texto", "en efectivo"),
            _el("span", "cifra", _dinero(item.efectivo)),
            _llenar(_el("span", "texto"), ["a ", _duena(_nombre(item.nombre) || SIN_NOMBRE)]),
        ]);
        card.style.setProperty("--pos-franja", _colorDuena(item));
        fila.append(card);
    });
    cont.append(fila);
}

function _pintarSinCajon(cont, r, receptora) {
    if (!_hayMonto(r.sin_cajon)) return;
    cont.append(_parrafo("aviso", [
        "⚠ ", _monto(r.sin_cajon),
        " no tiene dueña asignada (producto sin dueña): déjalo en la caja de ",
        _duena(receptora), " y avísale a la encargada.",
    ]));
}

// Ninguna dueña en la cuenta: solo se avisa, no se dice a qué caja va
function _pintarSinDuena(cont, r) {
    if (_hayMonto(r.neto)) {
        cont.append(_parrafo("aviso", [
            "⚠ Este efectivo (", _monto(r.neto),
            ") no tiene dueña asignada: déjalo en la caja donde cobraste y avísale a la encargada.",
        ]));
    }
    if (_hayMonto(r.tarjeta)) {
        cont.append(_parrafo("aviso", [
            "⚠ Lo de tarjeta (", _monto(r.tarjeta),
            ") no tiene dueña asignada: avísale a la encargada.",
        ]));
    }
}


// ============================================================
// 3. API pública
// ============================================================

function _ocultar(contenedor, motivo, r) {
    if (motivo) console.warn(`[POS:reparto] ${motivo} → oculto`, r);
    if (typeof contenedor.replaceChildren === "function") contenedor.replaceChildren();
    else contenedor.textContent = "";
    contenedor.className = PREFIJO;
    contenedor.hidden = true;
}

// Pinta "¿Cómo acomodo el dinero?" dentro de `contenedor` (#resultado-reparto).
// Si no hay datos, vienen en una versión que no conocemos o les falta algo
// para no inventar a quién va el dinero → se oculta, y el modal queda
// exactamente como antes de que existiera esta función.
// Devuelve true si pintó lo recibido y la feria: ui.js entonces esconde los
// campos sueltos "Monto recibido" / "Cambio" (si no, se quedan como antes).
export function pintarReparto(contenedor, r) {
    if (!contenedor) return false;

    // Limpia lo de la venta anterior SIEMPRE, antes de cualquier validación
    _ocultar(contenedor);

    if (!r || r.version !== VERSION) {
        if (r) console.warn(`[POS:reparto] versión desconocida (${JSON.stringify(r.version)}) → oculto`);
        return false;
    }

    const caso = CASOS.includes(r.caso) ? r.caso : null;
    if (!caso) {
        _ocultar(contenedor, `caso desconocido (${JSON.stringify(r.caso)})`, r);
        return false;
    }

    const receptora = _nombre(r.receptora?.nombre);
    const clip      = (r.clip && typeof r.clip === "object" && _hayMonto(r.clip.monto)) ? r.clip : null;
    const nombreClip = clip ? (_nombre(clip.nombre) || receptora) : "";
    console.log(`[POS:reparto] pintarReparto → caso=${caso} receptora="${receptora}" recibido=${r.recibido} cambio=${r.cambio} neto=${r.neto} tarjeta=${r.tarjeta} clip=${clip ? `${nombreClip}:${clip.monto}` : "-"} del_fondo=${r.del_fondo} sin_cajon=${r.sin_cajon}`);

    contenedor.classList.add(`${PREFIJO}--${caso.replace(/_/g, "-")}`);

    // Ninguna dueña en la cuenta: solo el aviso; "Monto recibido" y "Cambio"
    // se quedan visibles en el modal (por eso devuelve false).
    if (caso === "sin_duena") {
        _pintarSinDuena(contenedor, r);
        if (!contenedor.childNodes.length) _ocultar(contenedor);   // nada que avisar
        else contenedor.hidden = false;
        return false;
    }

    // Sin receptora no se sabe a qué caja / Clip va el dinero: mejor no decir
    // nada que mandarlo al lugar equivocado.
    const conEfectivo = caso === "varias" || caso === "una";
    if ((conEfectivo || _hayMonto(r.sin_cajon) || _hayMonto(r.cambio)) && !receptora) {
        _ocultar(contenedor, "falta la receptora", r);
        return false;
    }
    if (clip && !nombreClip) {
        _ocultar(contenedor, "Clip sin nombre", r);
        return false;
    }

    contenedor.append(_el("p", "titulo", "¿Cómo acomodo el dinero?"));
    _pintarPagos(contenedor, r, clip, nombreClip);
    _pintarFeria(contenedor, r, receptora);
    if (conEfectivo) _pintarCajas(contenedor, r, receptora);
    _pintarSinCajon(contenedor, r, receptora);

    // Venta en $0 (p. ej. solo regalos): solo el título
    if (contenedor.childNodes.length === 1) {
        contenedor.append(_parrafo("principal", ["No hay dinero que repartir."]));
    }

    contenedor.hidden = false;
    return true;
}
