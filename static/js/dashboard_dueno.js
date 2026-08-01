let chartVentasHoy = null;
let chartMasVendidosHoy = null;
let chartMasVendidos = null;
let chartMasVendidosTiendaHoy = null;
let chartExplorador = null;

document.addEventListener("DOMContentLoaded", () => {
    initChartVentasHoySucursal();
    chartMasVendidosHoy = initChartBarras("chartMasVendidosHoy", window.INIT_MAS_VENDIDOS_HOY, "#06D6A0");
    chartMasVendidos = initChartBarras("chartMasVendidosSemana", window.INIT_MAS_VENDIDOS_SEMANA, "#8338EC");
    chartMasVendidosTiendaHoy = initChartBarras("chartMasVendidosTiendaHoy", window.INIT_MAS_VENDIDOS_TIENDA_HOY, "#FFBE0B");
    setInterval(actualizarVentasHoy, 10000);
    initToggleMes();
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
            const { ctx: c, data: d, scales: { x } } = chart;

            chart.getDatasetMeta(0).data.forEach((bar, i) => {
                const value = d.datasets[0].data[i];
                if (!value) return;

                c.save();
                c.font = 'bold 18px sans-serif';
                c.fillStyle = '#FF006E';
                c.textAlign = 'center';
                c.textBaseline = 'top';
                // ⭐ Debajo del label del eje X
                c.fillText(`$${value}`, bar.x, x.bottom + 8);
                c.restore();
            });
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
            padding: { top: 10, bottom: 35 }
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
            }

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

    // Cantidad vendida escrita debajo de cada barra — no basta con el
    // eje Y para leer el número exacto de un vistazo.
    const cantidadLabelsPlugin = {
        id: 'cantidadLabels',
        afterDatasetsDraw(chart) {
            const { ctx: c, data: d, scales: { x } } = chart;
            chart.getDatasetMeta(0).data.forEach((bar, i) => {
                const value = d.datasets[0].data[i];
                if (!value) return;
                c.save();
                c.font = 'bold 14px sans-serif';
                c.fillStyle = '#111';
                c.textAlign = 'center';
                c.textBaseline = 'top';
                c.fillText(value, bar.x, x.bottom + 6);
                c.restore();
            });
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
            layout: { padding: { bottom: 24 } },
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#000", font: { size: 14, weight: "bold" } } },
                y: { ticks: { color: "#000", font: { size: 13 } }, beginAtZero: true }
            }
        },
        plugins: [cantidadLabelsPlugin]
    });
}