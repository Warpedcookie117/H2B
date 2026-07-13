let chartVentasHoy = null;
let chartMasVendidos = null;

document.addEventListener("DOMContentLoaded", () => {
    initChartVentasHoySucursal();
    initChartMasVendidosSemana();
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

function initChartMasVendidosSemana() {
    const data = window.INIT_MAS_VENDIDOS_SEMANA || [];
    const ctx = document.getElementById("chartMasVendidosSemana");
    if (!ctx) return;

    chartMasVendidos = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.map(x => x.nombre),
            datasets: [{
                label: 'Cantidad vendida',
                data: data.map(x => x.cantidad),
                backgroundColor: "#8338EC",
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