// ============================================================
// BASE DE CONOCIMIENTOS
// ============================================================
// 1. Acordeón de cada tarjeta ("Enséñame").
// 2. Buscador: esconde las tarjetas que no tienen lo que escribiste.
// 3. Demos "en cámara lenta": clonan una escena de _kb_escenas.html y un
//    cursor falso hace cada paso despacio mientras "el sistema" lo narra.
//    Son maquetas: nada de aquí toca datos reales.
//
// Cada paso de DEMOS:
//   dice    → lo que dice el sistema (obligatorio)
//   en      → data-d del elemento al que va el cursor
//   clic    → true = "pica" el elemento
//   escribe → texto que se teclea letra por letra en `en`
//   cambios → [op, data-d, valor] que se aplican al final del paso:
//             ver | quitar | texto | vaciar | clase | sinclase | brilla
//   rol     → "dueño" | "noDueño" | "ayudante": solo sale para ese rol
// `inicio` (en la demo) son cambios que se aplican al montar la escena.
// ============================================================
(function () {
    "use strict";

    const ROL      = JSON.parse(document.getElementById("kb-rol")?.textContent || "null");
    const ES_DUENO = ROL === "dueño";

    // ============================================================
    // 1. ACORDEÓN
    // ============================================================
    document.querySelectorAll(".kb-accordion-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            const abierta = btn.closest(".kb-card").classList.toggle("open");
            btn.setAttribute("aria-expanded", abierta ? "true" : "false");
        });
    });

    // ============================================================
    // 2. CONTADORES Y BUSCADOR
    // ============================================================
    const cards = [...document.querySelectorAll(".kb-card")];
    const demosEnPagina = new Set([...document.querySelectorAll("[data-demo]")].map(b => b.dataset.demo));

    const ponerTexto = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    ponerTexto("kb-cuenta-temas", cards.length);
    ponerTexto("kb-cuenta-demos", demosEnPagina.size);

    const normalizar = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

    // Palabras que no dicen nada de lo que buscas ("¿cómo le hago para cobrar?")
    const RELLENO = new Set(["como", "que", "hago", "hacer", "para", "una", "uno", "los", "las",
        "del", "con", "por", "quiero", "puedo", "donde", "cuando", "esta", "este", "eso", "mas"]);

    // Raíz corta para que "cobro" encuentre "cobrar" y "piezas" encuentre "pieza".
    const raiz = p => p.slice(0, Math.max(4, p.length - 2));

    cards.forEach(c => { c._texto = normalizar((c.dataset.buscar || "") + " " + c.textContent); });

    const buscador      = document.getElementById("kb-buscar");
    const sinResultados = document.getElementById("kb-sin-resultados");

    buscador?.addEventListener("input", () => {
        const palabras = normalizar(buscador.value)
            .split(/[^a-z0-9ñ]+/)
            .filter(p => p.length >= 3 && !RELLENO.has(p))
            .map(raiz);

        let visibles = 0;
        cards.forEach(c => {
            const ok = palabras.every(p => c._texto.includes(p));
            c.hidden = !ok;
            if (ok) visibles++;
        });
        document.querySelectorAll("[data-seccion]").forEach(s => {
            s.hidden = !s.querySelector(".kb-card:not([hidden])");
        });
        if (sinResultados) sinResultados.hidden = visibles > 0;
    });

    // ============================================================
    // 3. DEMOS EN CÁMARA LENTA
    // ============================================================
    const DEMOS = {
        "entrar-caja": {
            titulo: "Entrar a la caja",
            escena: "caja",
            pasos: [
                { dice: "Abre el menú y pícale a Sucursales.", en: "sucursales", clic: true, cambios: [["ver", "sub"]] },
                { dice: "Escoge tu sucursal. Aquí es Centro.", en: "centro", clic: true, cambios: [["ver", "sub2"]] },
                { dice: "Abajo, en Cajas, pícale a la caja donde vas a cobrar.", en: "caja1", clic: true, cambios: [["ver", "pass"]] },
                { dice: "Escribe tu contraseña. Es la misma con la que entras al sistema.", en: "password", escribe: "••••••••" },
                { dice: "Pícale a Entrar.", en: "entrar", clic: true, cambios: [["quitar", "pass"], ["ver", "dentro"]] },
                { dice: "Listo, ya estás en la caja. Si ayer se quedó sin corte, yo lo hago al entrar y te enseño el ticket." },
            ],
        },

        "vender": {
            titulo: "Meter productos al carrito",
            escena: "pos",
            pasos: [
                { dice: "Esta es la barra para escanear. Siempre está lista para el siguiente código.", en: "scan" },
                { dice: "Escanea el producto con la pistola. Si no tiene código, escribe el nombre.", en: "scan", escribe: "7501234500017",
                  cambios: [["vaciar", "scan"], ["quitar", "vacio"], ["ver", "item1"], ["brilla", "item1"], ["texto", "total", "$45.00"]] },
                { dice: "Ya lo puse en el carrito. Abajo te voy diciendo el total.", en: "total" },
                { dice: "Escanea el que sigue.", en: "scan", escribe: "7501234500024",
                  cambios: [["vaciar", "scan"], ["ver", "item2"], ["brilla", "item2"], ["texto", "total", "$95.00"]] },
                { dice: "¿Lleva otro labial igual? Pícale al +.", en: "mas1", clic: true,
                  cambios: [["texto", "cant1", "2"], ["texto", "precio1", "$90.00"], ["texto", "total", "$140.00"], ["brilla", "item1"]] },
                { dice: "¿Ya no quiere el rímel? La ✕ lo quita.", en: "x2", clic: true,
                  cambios: [["quitar", "item2"], ["texto", "total", "$90.00"]] },
                { dice: "Cuando ya está todo, se cobra con este botón. Eso te lo enseño en «Cobrar y acomodar el dinero».", en: "cobrar" },
            ],
        },

        "cantidad": {
            titulo: "Muchas piezas de lo mismo",
            escena: "pos",
            pasos: [
                { dice: "En la barra teclea asterisco y cuántas piezas. Aquí, *12.", en: "scan", escribe: "*12" },
                { dice: "Aprieta Enter.", en: "scan", cambios: [["vaciar", "scan"], ["ver", "badge"]] },
                { dice: "Arriba te sale ×12. Ya estoy esperando el producto.", en: "badge" },
                { dice: "Escanea una sola vez.", en: "scan", escribe: "7501234500017",
                  cambios: [["vaciar", "scan"], ["quitar", "badge"], ["quitar", "vacio"], ["ver", "item1"], ["brilla", "item1"],
                            ["texto", "cant1", "12"], ["texto", "precio1", "$420.00"], ["clase", "doc1", "kbd-modo-on"],
                            ["texto", "total", "$420.00"]] },
                { dice: "Como son 12 iguales y tiene precio de docena, le puse DOC solito.", en: "doc1" },
                { dice: "Si te equivocas antes de escanear, aprieta Esc y lo cancelo." },
            ],
        },

        "cobrar": {
            titulo: "Cobrar y acomodar el dinero",
            escena: "pos",
            inicio: [["quitar", "vacio"], ["ver", "item1"], ["ver", "item2"], ["texto", "total", "$95.00"]],
            pasos: [
                { dice: "Ya está todo en el carrito. Pícale a Cobrar.", en: "cobrar", clic: true, cambios: [["ver", "pago"]] },
                { dice: "Escribe cuánto te dio. Aquí pagó con $200 en efectivo.", en: "efectivo", escribe: "200",
                  cambios: [["ver", "pago-info"]] },
                { dice: "Yo te digo el cambio. Si te dio de menos, te digo cuánto falta.", en: "pago-info" },
                { dice: "Si paga con tarjeta, escríbelo aquí y te digo en qué Clip cobrarla.", en: "tarjeta" },
                { dice: "¿No quiere ticket? Quítale esta palomita. Aquí sí quiere.", en: "check" },
                { dice: "Pícale a Confirmar.", en: "confirmar", clic: true, cambios: [["quitar", "pago"], ["ver", "hecho"]] },
                { dice: "Lee esto con calma: cuánto es la feria, de qué caja la sacas y en qué caja va el efectivo.", en: "reparto" },
                { dice: "Pícale a Aceptar y atiende al siguiente.", en: "aceptar", clic: true,
                  cambios: [["quitar", "hecho"], ["quitar", "item1"], ["quitar", "item2"], ["ver", "vacio"], ["texto", "total", "$0.00"]] },
            ],
        },

        "pendiente": {
            titulo: "Cuenta pendiente",
            escena: "pos",
            inicio: [["quitar", "vacio"], ["ver", "item1"], ["ver", "item2"], ["texto", "total", "$95.00"]],
            pasos: [
                { dice: "Este cliente ya trae su cuenta, pero se fue por otra cosa y hay fila.", en: "carrito" },
                { dice: "Pícale a Pendiente.", en: "pendiente", clic: true,
                  cambios: [["quitar", "item1"], ["quitar", "item2"], ["ver", "vacio"], ["texto", "total", "$0.00"], ["ver", "tabs"]] },
                { dice: "Te guardé su cuenta en esta pestaña y te dejé el carrito vacío. Atiende al siguiente.", en: "tab1" },
                { dice: "Cuando regrese, pícale a su pestaña.", en: "tab1", clic: true,
                  cambios: [["quitar", "tabs"], ["quitar", "vacio"], ["ver", "item1"], ["ver", "item2"], ["texto", "total", "$95.00"]] },
                { dice: "Te la regreso tal cual. Ya la puedes cobrar.", en: "carrito" },
                { dice: "Ojo: la cuenta pendiente se queda en esta compu. En otra compu no la vas a ver." },
            ],
        },

        "corte": {
            titulo: "Corte de caja",
            escena: "pos",
            pasos: [
                { dice: "Al final del turno, pícale a ¿Estresao?.", en: "estresao", clic: true, cambios: [["ver", "menu"]] },
                { dice: "Si nada más vas a salir un rato, es Salir de caja. Ese no hace corte.", en: "salir" },
                { dice: "Para cerrar tu turno, pícale a Corte de caja.", en: "corte", clic: true,
                  cambios: [["quitar", "menu"], ["ver", "ticket"]] },
                { dice: "Junté todas las ventas desde el último corte de esta caja. Te imprimo este ticket con el total y lo de cada dueña.", en: "ticket-papel" },
                { dice: "Y te saco de la caja. Para volver a vender, entra otra vez." },
            ],
        },

        "agregar": {
            titulo: "Agregar piezas que llegaron",
            escena: "almacen",
            pasos: [
                { dice: "Busca el producto en el lugar donde lo vas a guardar.", en: "buscar", escribe: "labial rojo" },
                { dice: "Pícale a + Agregar.", en: "agregar", clic: true, cambios: [["ver", "m-agregar"]] },
                { dice: "Escribe cuántas piezas llegaron. Solo las nuevas, no el total.", en: "agregar-cant", escribe: "24" },
                { dice: "Guarda.", en: "agregar-ok", clic: true,
                  cambios: [["quitar", "m-agregar"], ["texto", "cant", "34"], ["brilla", "card"]] },
                { dice: "Ya las sumé: había 10, llegaron 24, ahora hay 34.", en: "cant" },
            ],
        },

        "ajustar": {
            titulo: "Corregir piezas",
            escena: "almacen",
            pasos: [
                { dice: "Yo digo que hay 10, pero contaste 8 en el anaquel.", en: "card" },
                { dice: "Pícale a Ajustar.", en: "ajustar", clic: true, cambios: [["ver", "m-ajustar"]] },
                { dice: "Escribe cuántas hay de verdad. El total, no la diferencia.", en: "ajustar-cant", escribe: "8" },
                { dice: "Escribe por qué.", en: "ajustar-motivo", escribe: "Conteo físico" },
                { rol: "dueño", dice: "Guarda. Como eres dueño, pasa directo.", en: "ajustar-ok", clic: true,
                  cambios: [["quitar", "m-ajustar"], ["texto", "cant", "8"], ["brilla", "card"]] },
                { rol: "dueño", dice: "Listo, ya dice 8.", en: "cant" },
                { rol: "noDueño", dice: "Guarda.", en: "ajustar-ok", clic: true,
                  cambios: [["quitar", "m-ajustar"], ["ver", "toast"], ["texto", "toast", "Le mandé tu solicitud al dueño del producto."]] },
                { rol: "noDueño", dice: "Como bajaste piezas, le pregunto al dueño. Mientras no diga que sí, se queda en 10.", en: "cant" },
                { rol: "noDueño", dice: "Lo que te conteste lo ves arriba, en Mis Solicitudes. Si hubieras subido piezas, pasaba directo." },
            ],
        },

        "transferir": {
            titulo: "Pasar mercancía a otro lugar",
            escena: "almacen",
            inicio: [["texto", "head", "Bodega interna · Centro"]],
            pasos: [
                { dice: "Estás en la bodega. En el producto, pícale a Transferir.", en: "transferir", clic: true, cambios: [["ver", "m-transferir"]] },
                { dice: "Escoge a dónde va. Aquí, al piso de venta.", en: "destino", clic: true, cambios: [["texto", "destino", "Piso de venta · Centro"]] },
                { dice: "Escribe cuántas piezas pasas.", en: "trans-cant", escribe: "6" },
                { dice: "Pícale a Transferir.", en: "trans-ok", clic: true,
                  cambios: [["quitar", "m-transferir"], ["texto", "cant", "4"], ["brilla", "card"],
                            ["ver", "toast"], ["texto", "toast", "Transferidos 6 de Labial mate rojo hacia Piso de venta."]] },
                { dice: "Aquí quedan 4 y en el piso hay 6 más.", en: "cant" },
                { rol: "ayudante", dice: "Con tu puesto solo puedes pasar mercancía dentro de tu misma sucursal." },
            ],
        },

        "reabastecer": {
            titulo: "Surtir el piso",
            escena: "reab",
            pasos: [
                { dice: "Camina el piso. Lo que veas que falta, escanéalo.", en: "camara" },
                { dice: "Bip. Lo anoto.", en: "codigo", escribe: "7501234500017",
                  cambios: [["vaciar", "codigo"], ["quitar", "vacio"], ["ver", "r1"], ["brilla", "r1"]] },
                { dice: "¿Falta otra del mismo? Escanéalo otra vez y le sumo 1.", en: "codigo", escribe: "7501234500017",
                  cambios: [["vaciar", "codigo"], ["texto", "n1", "2"], ["brilla", "r1"]] },
                { dice: "Sigue con lo demás.", en: "codigo", escribe: "7501234500024",
                  cambios: [["vaciar", "codigo"], ["ver", "r2"], ["brilla", "r2"]] },
                { dice: "Ya en la bodega, junta cada cosa y palomea.", en: "c1", clic: true, cambios: [["clase", "c1", "kbd-caja--on"]] },
                { dice: "Palomea todo lo que ya traes.", en: "c2", clic: true,
                  cambios: [["clase", "c2", "kbd-caja--on"], ["sinclase", "confirmar", "kbd-apagado"]] },
                { dice: "Pícale a Confirmar orden.", en: "confirmar", clic: true,
                  cambios: [["ver", "toast"], ["texto", "toast", "Listo. Pasé todo de bodega a piso."]] },
                { dice: "Las piezas ya están en el piso. Si lo va a juntar otra persona, mándale la lista en PDF." },
            ],
        },
    };

    const dialog = document.getElementById("kb-demo");
    if (!dialog) return;

    const $ = nombre => dialog.querySelector(`[data-kbd="${nombre}"]`);
    const pantalla = $("pantalla");
    const voz      = $("voz");
    const pasoTxt  = $("paso");
    const barra    = $("barra");
    const titulo   = $("titulo");
    const btnAtras = $("atras");
    const btnPlay  = $("play");
    const btnSig   = $("sig");
    const btnVel   = $("vel");

    const REDUCIDO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const CURSOR_SVG =
        '<svg viewBox="0 0 24 24" width="26" height="26" aria-hidden="true">' +
        '<path d="M3 2 L3 20 L8 15 L11.5 22 L14.5 20.6 L11 13.8 L18 13.8 Z" fill="#fff" stroke="#000" stroke-width="1.8" stroke-linejoin="round"/>' +
        '</svg>';

    const estado = {
        demo: null,
        pasos: [],
        i: 0,
        jugando: false,
        lenta: true,
        listo: false,     // el paso actual ya terminó su animación
        token: 0,         // cambia al navegar: cancela la animación anterior
    };
    let cursor = null;

    const esperar = ms => new Promise(r => setTimeout(r, ms));
    const factor  = () => (estado.lenta ? 2 : 1);
    const el      = nombre => pantalla.querySelector(`[data-d="${nombre}"]`);

    function pasosParaMiRol(demo) {
        return demo.pasos.filter(p =>
            !p.rol ||
            (p.rol === "dueño"   && ES_DUENO) ||
            (p.rol === "noDueño" && !ES_DUENO) ||
            p.rol === ROL
        );
    }

    function aplicar(cambios) {
        (cambios || []).forEach(([op, nombre, valor]) => {
            const e = el(nombre);
            if (!e) return;
            if (op === "ver")           e.hidden = false;
            else if (op === "quitar")   e.hidden = true;
            else if (op === "texto")    e.textContent = valor;
            else if (op === "vaciar")   e.textContent = "";
            else if (op === "clase")    e.classList.add(valor);
            else if (op === "sinclase") e.classList.remove(valor);
            else if (op === "brilla") {
                e.classList.remove("kbd-brilla");
                void e.offsetWidth;              // reinicia la animación
                e.classList.add("kbd-brilla");
            }
        });
    }

    function montarEscena() {
        const tpl = document.getElementById("kbd-escena-" + estado.demo.escena);
        pantalla.innerHTML = "";
        if (tpl) pantalla.append(tpl.content.cloneNode(true));
        cursor = document.createElement("div");
        cursor.className = "kbd-cursor";
        cursor.innerHTML = CURSOR_SVG;
        pantalla.append(cursor);
        aplicar(estado.demo.inicio);
    }

    function moverCursor(objetivo, ms) {
        if (!objetivo || !cursor) return;
        const r = objetivo.getBoundingClientRect();
        const p = pantalla.getBoundingClientRect();
        const x = r.left - p.left + r.width / 2;
        const y = r.top - p.top + r.height / 2;
        cursor.style.transitionDuration = ms + "ms";
        cursor.style.transform = `translate(${x}px, ${y}px)`;
        cursor.classList.add("kbd-cursor--visible");
    }

    // Deja la escena como quedaría al terminar el paso, sin animar.
    function aplicarDeGolpe(p) {
        if (p.escribe && p.en) {
            const o = el(p.en);
            if (o) o.textContent = p.escribe;
        }
        aplicar(p.cambios);
    }

    async function animarPaso(p, token) {
        const vivo = () => token === estado.token;
        const f = factor();
        const objetivo = p.en ? el(p.en) : null;

        if (objetivo) {
            moverCursor(objetivo, REDUCIDO ? 0 : 800 * f);
            await esperar(REDUCIDO ? 30 : 850 * f);
            if (!vivo()) return;
        }

        if (p.clic && objetivo) {
            cursor.classList.add("kbd-cursor--clic");
            objetivo.classList.add("kbd-presionado");
            await esperar(300 * f);
            if (!vivo()) return;
            cursor.classList.remove("kbd-cursor--clic");
            objetivo.classList.remove("kbd-presionado");
        }

        if (p.escribe && objetivo) {
            objetivo.textContent = "";
            objetivo.classList.add("kbd-escribiendo");
            for (const letra of p.escribe) {
                objetivo.textContent += letra;
                if (!REDUCIDO) await esperar(85 * f);
                if (!vivo()) return;
            }
            objetivo.classList.remove("kbd-escribiendo");
            await esperar(250 * f);
            if (!vivo()) return;
        }

        aplicar(p.cambios);
    }

    function pintarControles() {
        const ultimo = estado.i === estado.pasos.length - 1;
        btnAtras.disabled = estado.i === 0;
        btnSig.disabled   = ultimo;
        if (ultimo && estado.listo && !estado.jugando) btnPlay.textContent = "Ver otra vez";
        else btnPlay.textContent = estado.jugando ? "Pausa" : "Seguir";
        btnVel.textContent = "Cámara lenta: " + (estado.lenta ? "Sí" : "No");
        btnVel.setAttribute("aria-pressed", estado.lenta ? "true" : "false");
    }

    async function irA(i) {
        const token = ++estado.token;
        estado.i = i;
        estado.listo = false;

        montarEscena();
        for (let k = 0; k < i; k++) aplicarDeGolpe(estado.pasos[k]);

        // El cursor arranca donde lo dejó el paso anterior.
        const anterior = estado.pasos.slice(0, i).reverse().find(p => p.en);
        if (anterior) moverCursor(el(anterior.en), 0);

        const p = estado.pasos[i];
        voz.textContent     = p.dice;
        pasoTxt.textContent = `Paso ${i + 1} de ${estado.pasos.length}`;
        barra.style.width   = ((i + 1) / estado.pasos.length * 100) + "%";
        pintarControles();

        await animarPaso(p, token);
        if (token !== estado.token) return;
        estado.listo = true;

        const ultimo = i === estado.pasos.length - 1;
        if (ultimo) estado.jugando = false;
        pintarControles();
        if (!estado.jugando) return;

        // Tiempo para leer lo que dijo el sistema antes de pasar al siguiente.
        const leer = Math.max(2200, p.dice.length * 55) * (estado.lenta ? 1.5 : 1);
        await esperar(leer);
        if (token !== estado.token || !estado.jugando) return;
        irA(i + 1);
    }

    function abrir(id) {
        const demo = DEMOS[id];
        if (!demo) return;
        estado.demo    = demo;
        estado.pasos   = pasosParaMiRol(demo);
        estado.jugando = true;
        titulo.textContent = demo.titulo;
        if (!dialog.open) dialog.showModal();
        irA(0);
    }

    document.querySelectorAll("[data-demo]").forEach(btn => {
        btn.addEventListener("click", () => abrir(btn.dataset.demo));
    });

    btnPlay.addEventListener("click", () => {
        const ultimo = estado.i === estado.pasos.length - 1;
        if (estado.jugando) {
            estado.jugando = false;
            pintarControles();
        } else if (ultimo && estado.listo) {
            estado.jugando = true;
            irA(0);
        } else {
            estado.jugando = true;
            pintarControles();
            if (estado.listo) irA(estado.i + 1);   // si no, el paso en curso sigue solo
        }
    });

    // Moverse a mano pausa la reproducción: así cada quien va a su ritmo.
    btnSig.addEventListener("click", () => {
        if (estado.i >= estado.pasos.length - 1) return;
        estado.jugando = false;
        irA(estado.i + 1);
    });
    btnAtras.addEventListener("click", () => {
        if (estado.i === 0) return;
        estado.jugando = false;
        irA(estado.i - 1);
    });

    btnVel.addEventListener("click", () => {
        estado.lenta = !estado.lenta;
        pintarControles();
    });

    $("cerrar").addEventListener("click", () => dialog.close());
    dialog.addEventListener("close", () => {
        estado.token++;
        estado.jugando = false;
        pantalla.innerHTML = "";
    });

    // Si cambia el tamaño de la ventana, el cursor se reacomoda sobre lo que señala.
    window.addEventListener("resize", () => {
        if (!dialog.open || !estado.pasos.length) return;
        const actual = estado.pasos.slice(0, estado.i + 1).reverse().find(p => p.en);
        if (actual) moverCursor(el(actual.en), 0);
    });
})();
