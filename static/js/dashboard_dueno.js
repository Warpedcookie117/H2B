let chartVentasHoy = null;
let chartMasVendidosHoy = null;
let chartMasVendidos = null;
let chartMasVendidosTiendaHoy = null;

document.addEventListener("DOMContentLoaded", () => {
    initChartVentasHoySucursal();
    chartMasVendidosHoy = initChartBarras("chartMasVendidosHoy", window.INIT_MAS_VENDIDOS_HOY, "#06D6A0");
    chartMasVendidos = initChartBarras("chartMasVendidosSemana", window.INIT_MAS_VENDIDOS_SEMANA, "#8338EC");
    chartMasVendidosTiendaHoy = initChartBarras("chartMasVendidosTiendaHoy", window.INIT_MAS_VENDIDOS_TIENDA_HOY, "#FFBE0B");
    setInterval(actualizarVentasHoy, 10000);
});

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

function initChartBarras(canvasId, data, color) {
    data = data || [];
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

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
            animation: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#000", font: { size: 14, weight: "bold" } } },
                y: { ticks: { color: "#000", font: { size: 13 } }, beginAtZero: true }
            }
        }
    });
}