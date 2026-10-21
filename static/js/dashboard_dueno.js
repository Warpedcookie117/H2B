let chartVentasHoy = null;
let chartMasVendidosHoy = null;
let chartMasVendidos = null;
let chartMasVendidosTiendaHoy = null;
let chartExplorador = null;

// Dibuja el valor de cada barra ARRIBA de la barra (no debajo, donde compite
// por espacio con el nombre del producto ya rotado). En móvil, con muchas
// barras angostas juntas, un tamaño de letra fijo hace que los números se
// encimen y se vean como un solo churro ilegible — aquí la letra se encoge
// según qué tan pegadas están las barras, y si de plano no cabe, mejor no
// se dibuja ese label a que se vea encimado con el de al lado.
function dibujarValoresBarras(chart, { color = '#111', prefijo = '', sufijo = '' } = {}) {
    const { ctx: c, data: d } = chart;
    const meta = chart.getDatasetMeta(0);
    if (!meta.data.length) return;

    const separaciones = meta.data
        .map((bar, i) => meta.data[i + 1] ? Math.abs(meta.data[i + 1].x - bar.x) : Infinity)
        .filter(sep => sep !== Infinity);
    const anchoDisponible = separaciones.length ? Math.min(...separaciones) : chart.width;
    const fontSize = Math.max(9, Math.min(14, Math.floor(anchoDisponible / 3)));

    c.save();
    c.font = `bold ${fontSize}px sans-serif`;
    c.fillStyle = color;
    c.textAlign = 'center';
    c.textBaseline = 'bottom';

    meta.data.forEach((bar, i) => {
        const value = d.datasets[0].data[i];
        if (!value) return;
        const texto = `${prefijo}${value}${sufijo}`;
        if (c.measureText(texto).width > anchoDisponible - 2) return;
        c.fillText(texto, bar.x, bar.y - 4);
    });

    c.restore();
}

document.addEventListener("DOMContentLoaded", () => {
    initChartVentasHoySucursal();
    chartMasVendidosHoy = initChartBarras("chartMasVendidosHoy", window.INIT_MAS_VENDIDOS_HOY, "#06D6A0");
    chartMasVendidos = initChartBarras("chartMasVendidosSemana", window.INIT_MAS_VENDIDOS_SEMANA, "#8338EC");
    chartMasVendidosTiendaHoy = initChartBarras("chartMasVendidosTiendaHoy", window.INIT_MAS_VENDIDOS_TIENDA_HOY, "#FFBE0B");
    setInterval(actualizarVentasHoy, 10000);
    initToggleMes();
    initCuentasDuenas();
    initExplorador();
});

// ============================================================
// EXPLORADOR DE MÁS VENDIDOS
// Categoría → subcategoría → atributos de esa subcategoría (marca, etc).
// Los catálogos se piden a las mismas APIs que usa la página de reportes,
// y el resultado a /tienda/api/dashboard/mas-vendidos/.
// ============================================================
function initExplorador() {
    const panel = document.getElementById("explorador-vendidos");
    if (!panel) return;

    const urlVendidos   = panel.dataset.apiVendidos;
    const urlCategorias = panel.dataset.apiCategorias;
    const urlAtributos  = panel.dataset.apiAtributos;   // .../subcategoria/0/atributos-valores/

    const selCategoria = document.getElementById("exp-categoria");
    const selSubcat    = document.getElementById("exp-subcategoria");
    const selPeriodo   = document.getElementById("exp-periodo");
    const selMostrar   = document.getElementById("exp-mostrar");
    const panelAttrs   = document.getElementById("exp-panel-atributos");
    const rowsAttrs    = document.getElementById("exp-atributos-rows");
    const elUnidades   = document.getElementById("exp-total-unidades");
    const elIngreso    = document.getElementById("exp-total-ingreso");
    const elRango      = document.getElementById("exp-rango");
    const elVacio      = document.getElementById("exp-vacio");
    const canvas       = document.getElementById("chartExplorador");

    let categoriasCache = null;
    let fetchActivo     = null;

    async function cargarSubcategorias(categoriaId) {
        selSubcat.innerHTML = '<option value="">Todas</option>';
        limpiarAtributos();
        if (!categoriaId) return;

        selSubcat.innerHTML = '<option value="">Cargando...</option>';
        try {
            if (!categoriasCache) {
                const resp = await fetch(urlCategorias, { headers: { "X-Requested-With": "XMLHttpRequest" } });
                if (!resp.ok) throw new Error("HTTP " + resp.status);
                categoriasCache = await resp.json();
            }
            const cat = (categoriasCache.categorias_padre || [])
                .find(c => String(c.id) === String(categoriaId));

            let html = '<option value="">Todas</option>';
            (cat?.subcategorias || []).forEach(s => {
                html += `<option value="${s.id}">${s.nombre}</option>`;
            });
            selSubcat.innerHTML = html;
        } catch (e) {
            console.error("Error subcategorías:", e);
            selSubcat.innerHTML = '<option value="">Error al cargar</option>';
        }
    }

    function limpiarAtributos() {
        rowsAttrs.innerHTML = "";
        panelAttrs.classList.add("hidden");
    }

    async function cargarAtributos(subcatId) {
        limpiarAtributos();
        if (!subcatId) return;

        let atributos = [];
        try {
            const resp = await fetch(urlAtributos.replace("/0/", "/" + subcatId + "/"),
                                     { headers: { "X-Requested-With": "XMLHttpRequest" } });
            const data = await resp.json();
            atributos = data.atributos || [];
        } catch (e) {
            console.error("Error atributos:", e);
            return;
        }

        if (!atributos.length) return;
        panelAttrs.classList.remove("hidden");

        atributos.forEach(a => {
            const wrap = document.createElement("div");

            const label = document.createElement("label");
            label.className = "block font-black text-black text-xs uppercase tracking-widest mb-1.5";
            label.textContent = a.nombre;

            const sel = document.createElement("select");
            sel.dataset.attr = a.nombre;
            sel.className = "w-full border-4 border-black bg-white px-3 py-2 font-bold text-black";

            const opt0 = document.createElement("option");
            opt0.value = "";
            opt0.textContent = "Cualquiera";
            sel.appendChild(opt0);

            (a.valores || []).forEach(v => {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = v;
                sel.appendChild(opt);
            });

            sel.addEventListener("change", cargarDatos);

            wrap.appendChild(label);
            wrap.appendChild(sel);
            rowsAttrs.appendChild(wrap);
        });
    }

    // Mismos nombres de parámetro que reportes (an/av) — el backend reusa
    // parse_filtros, así que no hay dos formatos que mantener.
    function construirUrl() {
        const params = new URLSearchParams();
        if (selCategoria.value) params.set("categoria", selCategoria.value);
        if (selSubcat.value)    params.set("subcategoria", selSubcat.value);
        params.set("periodo", selPeriodo.value);
        params.set("mostrar", selMostrar.value);

        rowsAttrs.querySelectorAll("select[data-attr]").forEach(sel => {
            if (sel.value) {
                params.append("an", sel.dataset.attr);
                params.append("av", sel.value);
            }
        });

        return urlVendidos + "?" + params.toString();
    }

    async function cargarDatos() {
        if (fetchActivo) fetchActivo.abort();
        fetchActivo = new AbortController();

        let data;
        try {
            const resp = await fetch(construirUrl(), {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                signal: fetchActivo.signal,
            });
            if (!resp.ok) throw new Error("HTTP " + resp.status);
            data = await resp.json();
        } catch (e) {
            if (e.name !== "AbortError") console.error("Error explorador:", e);
            return;
        }

        const datos = data.datos || [];

        elUnidades.textContent = data.total_unidades || 0;
        elIngreso.textContent  = "$" + (data.total_ingreso || 0);
        elRango.textContent    = `Del ${data.desde} al ${data.hasta}`;

        elVacio.classList.toggle("hidden", datos.length > 0);
        canvas.parentElement.classList.toggle("hidden", datos.length === 0);

        pintarChart(datos);
    }

    function pintarChart(datos) {
        // Sin datos el contenedor está oculto: crear el chart ahí lo dejaría
        // con tamaño 0. Se crea hasta que haya algo que dibujar.
        if (!chartExplorador && !datos.length) return;

        if (chartExplorador) {
            chartExplorador.data.labels = datos.map(d => d.nombre);
            chartExplorador.data.datasets[0].data = datos.map(d => d.cantidad);
            chartExplorador.$ingresos = datos.map(d => d.ingreso);
            chartExplorador.update();
            return;
        }

        chartExplorador = initChartBarras("chartExplorador", datos, "#3A86FF", true);
        if (!chartExplorador) return;

        chartExplorador.$ingresos = datos.map(d => d.ingreso);
        // El eje mide unidades; el dinero de cada producto va en el tooltip.
        chartExplorador.options.plugins.tooltip = {
            callbacks: {
                afterLabel: (ctx) => {
                    const ingreso = chartExplorador.$ingresos?.[ctx.dataIndex];
                    return ingreso != null ? `Vendido: $${ingreso}` : "";
                },
            },
        };
        chartExplorador.update();
    }

    selCategoria.addEventListener("change", async () => {
        await cargarSubcategorias(selCategoria.value);
        cargarDatos();
    });
    selSubcat.addEventListener("change", async () => {
        await cargarAtributos(selSubcat.value);
        cargarDatos();
    });
    selPeriodo.addEventListener("change", cargarDatos);
    selMostrar.addEventListener("change", cargarDatos);

    cargarDatos();
}

// Card "vendido este mes" — oculta al entrar y se revela al tocar, para no
// mostrar el monto de un vistazo a quien esté cerca.
function initToggleMes() {
    const btn     = document.getElementById("btn-toggle-mes");
    const wrap    = document.getElementById("monto-mes-wrap");
    const chevron = document.getElementById("chevron-mes");
    const hint    = document.getElementById("monto-mes-hint");
    if (!btn || !wrap) return;

    let abierto = false;
    btn.addEventListener("click", () => {
        abierto = !abierto;
        if (abierto) {
            wrap.style.maxHeight = wrap.scrollHeight + "px";
            wrap.style.opacity   = "1";
            if (chevron) chevron.style.transform = "rotate(180deg)";
            if (hint) hint.style.display = "none";
            btn.setAttribute("aria-expanded", "true");
        } else {
            wrap.style.maxHeight = "0";
            wrap.style.opacity   = "0";
            if (chevron) chevron.style.transform = "";
            if (hint) hint.style.display = "";
            btn.setAttribute("aria-expanded", "false");
        }
    });
}

function initChartVentasHoySucursal() {
    const data = window.INIT_VENTAS_HOY_SUCURSAL || [];
    const ctx = document.getElementById("chartVentasHoySucursal");
    if (!ctx) return;

    // ⭐ Plugin inline — no necesita CDN
    const totalLabelsPlugin = {
        id: 'totalLabels',
        afterDatasetsDraw(chart) {
            dibujarValoresBarras(chart, { color: '#FF006E', prefijo: '$' });
        }
    };

    chartVentasHoy = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(x => x.nombre),
            datasets: [{
                label: 'Total vendido hoy',
                data: data.map(x => x.total),
                backgroundColor: "#FF006E",
                borderRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            layout: {
                padding: { top: 24 }
            },
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#000", font: { size: 14, weight: "bold" } } },
                y: { ticks: { color: "#000", font: { size: 13 } }, beginAtZero: true }
            }
        },
        plugins: [totalLabelsPlugin]  // ⭐ plugin local
    });
}

// ============================================================
// CUENTAS CON OTRAS DUEÑAS (card acordeón)
// Lo que una dueña cobró en su Clip y es de otra. Es sensible: ya no sale en
// el corte, solo aquí. Datos: contexto `mis_deudas` (json_script) al cargar y
// `data.mis_deudas` en cada polling de /ventas/api/ventas/hoy/.
// Todo se arma con createElement/textContent: los nombres vienen de la BD.
// El <details> nunca se reemplaza, así que abierto/cerrado se conserva.
// ============================================================
let misDeudas = null;
const deudasEnviando = new Set();   // ids con POST en curso
let avisoDeudasTimer = null;

// |monto| → "$50.00" (redondeado a centavos: floats de la API).
function dineroDeuda(monto) {
    const centavos = Math.abs(Math.round((Number(monto) || 0) * 100));
    return `$${(centavos / 100).toFixed(2)}`;
}

function centavosDe(monto) {
    return Math.round((Number(monto) || 0) * 100);
}

function nodoDeuda(tag, className, texto) {
    const nodo = document.createElement(tag);
    if (className) nodo.className = className;
    if (texto != null) nodo.textContent = texto;
    return nodo;
}

function initCuentasDuenas() {
    const card = document.getElementById("card-cuentas-duenas");
    if (!card) return;
    let inicial = null;
    try {
        const script = document.getElementById("init-mis-deudas");
        inicial = script ? JSON.parse(script.textContent) : null;
    } catch (e) {
        console.error("mis_deudas inicial ilegible:", e);
    }
    pintarCuentasDuenas(inicial);
}

function pintarCuentasDuenas(md, forzar = false) {
    const card = document.getElementById("card-cuentas-duenas");
    if (!card) return;

    // Si nada cambió no se toca el DOM (no se pierde el foco del teclado
    // en los botones cada 10 s).
    const firma = JSON.stringify(md ?? null) + "|" + [...deudasEnviando].sort().join(",");
    if (!forzar && card.dataset.firma === firma) return;
    card.dataset.firma = firma;

    misDeudas = (md && typeof md === "object") ? md : null;
    card.hidden = !misDeudas;
    if (!misDeudas) return;

    const hoy = misDeudas.hoy || {};
    const historial = Array.isArray(misDeudas.historial) ? misDeudas.historial : [];

    // --- Encabezado (cerrado): hoy, neteado por persona ---
    const elResumen = document.getElementById("cuentas-resumen");
    if (elResumen) {
        const lineas = (hoy.resumen || [])
            .filter(r => centavosDe(r.monto) !== 0)
            .map(r => nodoDeuda("span", "block", centavosDe(r.monto) < 0
                ? `Le debes ${dineroDeuda(r.monto)} a ${r.con_nombre}`
                : `${r.con_nombre} te debe ${dineroDeuda(r.monto)}`));
        if (!lineas.length) lineas.push(nodoDeuda("span", "block", "Hoy nadie te debe ni le debes"));
        elResumen.replaceChildren(...lineas);
    }

    const elTotales = document.getElementById("cuentas-totales");
    if (elTotales) {
        const partes = [];
        if (centavosDe(hoy.total_debes)) partes.push(`Debes ${dineroDeuda(hoy.total_debes)}`);
        if (centavosDe(hoy.total_te_deben)) partes.push(`Te deben ${dineroDeuda(hoy.total_te_deben)}`);
        elTotales.textContent = partes.join(" · ");
        elTotales.hidden = !partes.length;
    }

    // Pagos en corto de hoy (todavía sin corte): se pintan como historial.
    const pagadasHoy = Array.isArray(hoy.pagadas) ? hoy.pagadas : [];

    // Aviso discreto en el encabezado si quedan deudas viejas sin pagar.
    const elPrevias = document.getElementById("cuentas-previas");
    if (elPrevias) {
        const pendientes = historial.filter(d => !d.pagada).length;
        const avisos = [...historial, ...pagadasHoy].filter(d => d.aviso).length;
        const partes = [];
        if (pendientes) partes.push(`📌 ${pendientes} pendiente${pendientes === 1 ? "" : "s"} de cortes anteriores`);
        if (avisos) partes.push(`⚠ ${avisos} aviso${avisos === 1 ? "" : "s"}`);
        elPrevias.textContent = partes.join(" · ");
        elPrevias.hidden = !partes.length;
    }

    // --- Abierta (a): hoy, por caja — pendientes con "Ya se pagó" y lo ya pagado en corto ---
    const elHoy = document.getElementById("cuentas-hoy");
    if (elHoy) {
        const items = (hoy.items || []).filter(it => centavosDe(it.monto) !== 0);
        if (!items.length && !pagadasHoy.length) {
            elHoy.replaceChildren(nodoDeuda("p", "text-sm font-bold text-black/60", "Hoy nadie te debe ni le debes"));
        } else {
            elHoy.replaceChildren(...items.map(filaDeudaHoy), ...pagadasHoy.map(filaHistorialDeuda));
        }
    }

    // --- Abierta (b): cortes anteriores, con "Ya se pagó" ---
    const elHist = document.getElementById("cuentas-historial");
    if (elHist) {
        if (!historial.length) {
            elHist.replaceChildren(nodoDeuda("p", "text-sm font-bold text-black/60", "No hay deudas de cortes anteriores"));
        } else {
            elHist.replaceChildren(...historial.map(filaHistorialDeuda));
        }
    }
}

const CLASES_BOTON_DEUDA =
    `flex-shrink-0 border-4 border-black shadow-[4px_4px_0_0_black] px-3 py-2 text-xs font-black uppercase tracking-widest
     transition-all duration-150 hover:-translate-x-0.5 hover:-translate-y-0.5 disabled:opacity-50 disabled:cursor-wait`;

// Deuda de hoy (sin corte todavía): "Caja Anais: Anais te debe $10.00 · desde las 4:12 pm" + [Ya se pagó]
function filaDeudaHoy(it) {
    const clave = `hoy-${it.caja_id}-${it.con_id}`;
    const fila = nodoDeuda("div",
        "bg-white border-2 border-black px-3 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2");
    fila.appendChild(nodoDeuda("p", "min-w-0 text-sm font-bold text-black break-words",
        (it.yo_debo
            ? `${it.caja}: le debes ${dineroDeuda(it.monto)} a ${it.con_nombre}`
            : `${it.caja}: ${it.con_nombre} te debe ${dineroDeuda(it.monto)}`)
            + (it.desde_txt ? ` · ${it.desde_txt}` : "")));

    const enviando = deudasEnviando.has(clave);
    const btn = nodoDeuda("button", `${CLASES_BOTON_DEUDA} bg-black text-white`,
        enviando ? "Guardando…" : "Ya se pagó");
    btn.type = "button";
    btn.disabled = enviando || it.caja_id == null;   // respuesta vieja sin caja_id
    btn.addEventListener("click", () => marcarDeudaHoyPagada(it));
    fila.appendChild(btn);
    return fila;
}

function filaHistorialDeuda(d) {
    const pagada = !!d.pagada;
    const fila = nodoDeuda("div",
        `border-2 border-black px-3 py-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 ${pagada ? "bg-gray-100" : "bg-white"}`);
    fila.dataset.deudaId = d.id;

    const info = nodoDeuda("div", "min-w-0 space-y-1");
    const cuanto = d.yo_debo
        ? `Le debes ${dineroDeuda(d.monto)} a ${d.con_nombre}`
        : `${d.con_nombre} te debe ${dineroDeuda(d.monto)}`;
    info.appendChild(nodoDeuda("p",
        `text-sm font-bold text-black break-words ${pagada ? "line-through decoration-2 text-black/50" : ""}`,
        [d.fecha_txt, d.caja, cuanto].filter(Boolean).join(" · ")));

    info.appendChild(nodoDeuda("span",
        `inline-block border-2 border-black px-2 py-0.5 text-[11px] font-black uppercase tracking-widest ${
            pagada ? "bg-[#06D6A0] text-black" : "bg-[#FF006E] text-white"}`,
        pagada ? "Pagada ✓" : "Pendiente"));

    if (d.aviso) {
        info.appendChild(nodoDeuda("p",
            "bg-[#FFBE0B] border-2 border-black px-2 py-1 text-xs font-black text-black",
            `⚠ ${d.aviso}`));
    }
    fila.appendChild(info);

    const enviando = deudasEnviando.has(d.id);
    const btn = nodoDeuda("button",
        `${CLASES_BOTON_DEUDA} ${pagada ? "bg-white text-black" : "bg-black text-white"}`,
        enviando ? "Guardando…" : (pagada ? "Marcar como no pagada" : "Ya se pagó"));
    btn.type = "button";
    btn.disabled = enviando;
    btn.addEventListener("click", () => marcarDeudaPagada(d.id, !pagada));
    fila.appendChild(btn);

    return fila;
}

function csrfTokenDeudas() {
    const input = document.querySelector('#card-cuentas-duenas input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    const m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
}

function avisoCuentasDuenas(texto) {
    const aviso = document.getElementById("cuentas-aviso");
    if (!aviso) return;
    aviso.textContent = texto;
    aviso.hidden = false;
    clearTimeout(avisoDeudasTimer);
    avisoDeudasTimer = setTimeout(() => { aviso.hidden = true; }, 5000);
}

async function marcarDeudaPagada(id, pagada) {
    if (deudasEnviando.has(id)) return;
    deudasEnviando.add(id);
    pintarCuentasDuenas(misDeudas, true);   // botón deshabilitado

    try {
        const resp = await fetch(`/ventas/api/deudas/${encodeURIComponent(id)}/pagada/`, {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfTokenDeudas() },
            body: JSON.stringify({ pagada }),
        });
        let data = null;
        try { data = await resp.json(); } catch { /* respuesta sin JSON */ }

        if (!resp.ok || !data || data.status !== "ok") {
            avisoCuentasDuenas(resp.status === 404
                ? "Esa cuenta ya no está disponible."
                : "No se pudo guardar. Intenta de nuevo.");
            return;
        }
        // deuda null: era un pago en corto de hoy y se desmarcó; el polling
        // de abajo la regresa como pendiente.
        if (data.deuda && misDeudas && Array.isArray(misDeudas.historial)) {
            misDeudas = {
                ...misDeudas,
                historial: misDeudas.historial.map(d => (d.id === id ? data.deuda : d)),
            };
        }
    } catch (e) {
        console.error("Error marcando deuda:", e);
        avisoCuentasDuenas("Sin conexión. No se guardó; intenta de nuevo.");
    } finally {
        deudasEnviando.delete(id);
        pintarCuentasDuenas(misDeudas, true);
        actualizarVentasHoy();   // trae todo ya actualizado sin esperar 10 s
    }
}

// "Ya se pagó" en una deuda de hoy (sin corte todavía): pago en corto.
async function marcarDeudaHoyPagada(it) {
    const clave = `hoy-${it.caja_id}-${it.con_id}`;
    if (deudasEnviando.has(clave)) return;
    deudasEnviando.add(clave);
    pintarCuentasDuenas(misDeudas, true);   // botón deshabilitado

    try {
        const resp = await fetch("/ventas/api/deudas/hoy/pagada/", {
            method: "POST",
            headers: { "Content-Type": "application/json", "X-CSRFToken": csrfTokenDeudas() },
            body: JSON.stringify({ caja_id: it.caja_id, con_id: it.con_id, monto: it.monto }),
        });
        let data = null;
        try { data = await resp.json(); } catch { /* respuesta sin JSON */ }

        if (!resp.ok || !data || data.status !== "ok") {
            avisoCuentasDuenas(
                resp.status === 409 ? "La cuenta cambió (entró otra venta o ya la marcaron). Revísala y vuelve a picarle."
                : resp.status === 404 ? "Esa cuenta ya no está disponible."
                : "No se pudo guardar. Intenta de nuevo.");
        }
    } catch (e) {
        console.error("Error marcando deuda de hoy:", e);
        avisoCuentasDuenas("Sin conexión. No se guardó; intenta de nuevo.");
    } finally {
        deudasEnviando.delete(clave);
        pintarCuentasDuenas(misDeudas, true);
        actualizarVentasHoy();   // trae la cuenta ya con el pago
    }
}

function actualizarVentasHoy() {
    fetch("/ventas/api/ventas/hoy/")
        .then(r => r.json())
        .then(data => {
            if (chartVentasHoy) {
                chartVentasHoy.data.labels = data.chart.map(x => x.nombre);
                chartVentasHoy.data.datasets[0].data = data.chart.map(x => x.total);
                chartVentasHoy.update();
            }

            // Tarjeta "mis productos — vendido ahorita" (efectivo/tarjeta/total)
            if (data.mis_ventas) {
                const elEf = document.getElementById("dueno-ahorita-efectivo");
                const elTa = document.getElementById("dueno-ahorita-tarjeta");
                const elTo = document.getElementById("dueno-ahorita-total");
                if (elEf) elEf.textContent = `$${data.mis_ventas.efectivo}`;
                if (elTa) elTa.textContent = `$${data.mis_ventas.tarjeta}`;
                if (elTo) elTo.textContent = `$${data.mis_ventas.total}`;
                // `saldo` (si la API lo sigue mandando) se ignora aquí: las
                // deudas entre dueñas van en la card "Cuentas con otras dueñas".
            }

            // Card "Cuentas con otras dueñas": misma respuesta, sin otro fetch.
            // Respuesta sin la llave (API vieja) → se deja como está.
            if ("mis_deudas" in data) pintarCuentasDuenas(data.mis_deudas);

            // Desglose por caja de "mis productos" dentro de esa misma tarjeta
            (data.mis_cajas || []).forEach(caja => {
                const key = `${caja.sucursal}__${caja.caja}`;
                const card = document.querySelector(`[data-dueno-caja-key="${key}"]`);
                if (!card) return;

                const elEfectivo = card.querySelector(".dueno-caja-efectivo");
                const elTarjeta = card.querySelector(".dueno-caja-tarjeta");
                const elTotal = card.querySelector(".dueno-caja-total");

                if (elEfectivo) elEfectivo.textContent = `$${caja.efectivo}`;
                if (elTarjeta) elTarjeta.textContent = `$${caja.tarjeta}`;
                if (elTotal) elTotal.textContent = caja.total;
            });

            data.cajas.forEach(caja => {
                const key = `${caja.sucursal}__${caja.caja}`;
                const card = document.querySelector(`[data-caja-key="${key}"]`);
                if (!card) return;

                const elEfectivo = card.querySelector(".caja-efectivo");
                const elTarjeta = card.querySelector(".caja-tarjeta");
                const elTotal = card.querySelector(".caja-total");
                const elHora = card.querySelector(".caja-hora");

                if (elEfectivo) elEfectivo.textContent = `$${caja.efectivo}`;
                if (elTarjeta) elTarjeta.textContent = `$${caja.tarjeta}`;
                if (elTotal) elTotal.textContent = `$${caja.total}`;
                if (elHora) elHora.textContent = caja.ultima_hora
                    ? `Última venta: ${caja.ultima_hora} hrs`
                    : "Sin ventas hoy";
            });
        })
        .catch(err => console.error("Error actualizando ventas:", err));
}

// `animar` viene apagado por default: las gráficas de arriba se repintan
// solas cada 10s por polling y animarlas las deja parpadeando. El explorador
// sí lo enciende — ahí solo se repinta cuando el dueño mueve un filtro.
function initChartBarras(canvasId, data, color, animar = false) {
    data = data || [];
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    // Cantidad vendida escrita arriba de cada barra — no basta con el
    // eje Y para leer el número exacto de un vistazo.
    const cantidadLabelsPlugin = {
        id: 'cantidadLabels',
        afterDatasetsDraw(chart) {
            dibujarValoresBarras(chart, { color: '#111' });
        }
    };

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(x => x.nombre),
            datasets: [{
                label: 'Cantidad vendida',
                data: data.map(x => x.cantidad),
                backgroundColor: color,
                borderRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: animar
                ? { duration: 700, easing: 'easeOutQuart' }
                : false,
            layout: { padding: { top: 24 } },
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#000", font: { size: 14, weight: "bold" } } },
                y: { ticks: { color: "#000", font: { size: 13 } }, beginAtZero: true }
            }
        },
        plugins: [cantidadLabelsPlugin]
    });
}