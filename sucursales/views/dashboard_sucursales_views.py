from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from sucursales.models import Sucursal
from ventas.models import Venta, VentaDetalle
from inventario.models import Inventario
from django.db.models import Sum


# ---------------------------------------------------------
# DASHBOARD POR SUCURSAL (accesible para todos los roles)
# ---------------------------------------------------------
@login_required
def dashboard_sucursal(request, sucursal_id):

    empleado = getattr(request.user, "empleado", None)

    # Si el usuario no tiene empleado asociado, no debería entrar
    if not empleado:
        raise Http404("Acceso denegado")

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    # Ubicaciones internas
    ubicaciones = sucursal.ubicaciones.all()

    # Stock total
    stock_total = (
        Inventario.objects.filter(
            ubicacion__sucursal=sucursal
        ).aggregate(total=Sum("cantidad_actual"))["total"] or 0
    )

    # Productos bajos
    productos_bajos = (
        Inventario.objects.filter(
            ubicacion__sucursal=sucursal,
            cantidad_actual__lte=5
        )
        .select_related("producto", "ubicacion")
        .order_by("cantidad_actual")[:10]
    )

    # Productos más vendidos
    productos_mas_vendidos = (
        VentaDetalle.objects.filter(
            venta__ubicacion__sucursal=sucursal
        )
        .values("producto__nombre")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")[:10]
    )

    # Ventas recientes
    ventas = Venta.objects.filter(
        ubicacion__sucursal=sucursal
    ).order_by("-fecha")[:20]

    # Total vendido
    total_vendido = Venta.objects.filter(
        ubicacion__sucursal=sucursal
    ).aggregate(total=Sum("total"))["total"] or 0

    return render(request, "sucursales/dashboard_sucursal.html", {
        "sucursal": sucursal,
        "ubicaciones": ubicaciones,
        "stock_total": stock_total,
        "productos_bajos": productos_bajos,
        "productos_mas_vendidos": productos_mas_vendidos,
        "ventas": ventas,
        "total_vendido": total_vendido,
        "cajas": sucursal.cajas.all(),
    })