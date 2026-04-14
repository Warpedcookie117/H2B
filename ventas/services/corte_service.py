from ventas.models import Venta, CorteCaja
from django.db.models import Sum


def generar_corte_para_fecha(caja, fecha):
    ventas = Venta.objects.filter(caja=caja, fecha__date=fecha)

    total_general = ventas.aggregate(total=Sum("total"))["total"] or 0

    totales_dueno = {}
    for venta in ventas:
        for item in venta.detalles.all():
            # ⭐ Fix — usar snapshot si producto fue eliminado
            if item.producto:
                empleado_dueno = item.producto.dueño
                nombre = (
                    empleado_dueno.user.get_full_name()
                    or empleado_dueno.user.username
                ) if empleado_dueno else "Sin dueño"
            else:
                nombre = item.nombre_snapshot or "PRODUCTO ELIMINADO"

            totales_dueno.setdefault(nombre, 0)
            totales_dueno[nombre] += float(item.subtotal)

    corte = CorteCaja.objects.create(
        caja=caja,
        empleado=None,
        caja_nombre=caja.nombre,
        total_general=total_general,
        total_por_dueno=totales_dueno
    )

    # ⭐ Fix — ManyToMany en CorteCaja, no FK en Venta
    corte.ventas.set(ventas)

    return corte