from ventas.models import Venta, CorteCaja
from django.db.models import Sum


def generar_corte_para_fecha(caja, fecha):
    ventas = Venta.objects.filter(caja=caja, fecha__date=fecha)

    total_general = ventas.aggregate(total=Sum("total"))["total"] or 0

    totales_dueno = {}
    for venta in ventas:
        for item in venta.detalles.all():
            dueno = item.producto.dueño.user.username
            totales_dueno.setdefault(dueno, 0)
            totales_dueno[dueno] += float(item.subtotal)

    corte = CorteCaja.objects.create(
        caja=caja,
        empleado=None,  # corte automático
        total_general=total_general,
        total_por_dueno=totales_dueno
    )

    return corte
