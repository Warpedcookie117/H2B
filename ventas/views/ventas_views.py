from django.http import JsonResponse
from django.utils import timezone
from ventas.models import CorteCaja, Venta
from django.shortcuts import redirect, render
from django.db.models import Sum, F
from django.utils.timezone import now



def ventas_por_cajero(request):
    hoy = timezone.now().date()

    ventas = Venta.objects.filter(fecha__date=hoy)

    resumen = {}

    for venta in ventas:
        cajero = venta.empleado.nombre
        resumen.setdefault(cajero, {
            "total": 0,
            "tickets": 0,
            "productos": 0,
        })

        resumen[cajero]["total"] += float(venta.total)
        resumen[cajero]["tickets"] += 1
        resumen[cajero]["productos"] += sum(d.cantidad for d in venta.detalles.all())

    return render(request, "reportes/ventas_por_cajero.html", {"resumen": resumen})


def api_ventas_hoy(request):
    from sucursales.models import Sucursal
    hoy = now().date()

    sucursales = Sucursal.objects.prefetch_related("cajas").all().order_by("nombre")

    resultado_chart = []
    resultado_cajas = []

    for sucursal in sucursales:
        efectivo_sucursal = 0
        tarjeta_sucursal = 0

        for caja in sucursal.cajas.all().order_by("nombre"):
            ventas_caja = Venta.objects.filter(caja=caja, fecha__date=hoy)

            efectivo = float(ventas_caja.aggregate(total=Sum("pagado_efectivo")).get("total") or 0)
            tarjeta = float(ventas_caja.aggregate(total=Sum("pagado_tarjeta")).get("total") or 0)
            total = efectivo + tarjeta

            ultima_venta = ventas_caja.order_by("-fecha").first()
            ultima_hora = ultima_venta.fecha.strftime("%H:%M") if ultima_venta else None

            efectivo_sucursal += efectivo
            tarjeta_sucursal += tarjeta

            resultado_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": efectivo,
                "tarjeta": tarjeta,
                "total": total,
                "ultima_hora": ultima_hora,
            })

        resultado_chart.append({
            "nombre": sucursal.nombre,
            "efectivo": round(efectivo_sucursal, 2),
            "tarjeta": round(tarjeta_sucursal, 2),
            "total": round(efectivo_sucursal + tarjeta_sucursal, 2),
        })

    return JsonResponse({
        "chart": resultado_chart,
        "cajas": resultado_cajas,
    }, safe=False)