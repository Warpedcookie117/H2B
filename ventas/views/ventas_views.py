from django.utils import timezone
from ventas.models import CorteCaja, Venta
from django.shortcuts import redirect, render




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
