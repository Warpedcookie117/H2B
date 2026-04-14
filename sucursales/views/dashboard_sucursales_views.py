from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import Http404
from sucursales.models import Sucursal
from ventas.models import CorteCaja, Venta, VentaDetalle
from inventario.models import Inventario
from django.db.models import Sum


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count

from sucursales.models import Sucursal, Caja
from inventario.models import Inventario
from ventas.models import Venta, CorteCaja


@login_required
def dashboard_sucursal(request, sucursal_id):

    empleado = getattr(request.user, "empleado", None)
    if not empleado:
        raise Http404("Acceso denegado")

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    # Cantidad de PRODUCTOS distintos en piso (no piezas)
    productos_piso = (
        Inventario.objects
        .filter(
            ubicacion__sucursal=sucursal,
            ubicacion__tipo="piso",
            cantidad_actual__gt=0
        )
        .values("producto")
        .distinct()
        .count()
    )

    # Cantidad de PRODUCTOS distintos en bodega (no piezas)
    productos_bodega = (
        Inventario.objects
        .filter(
            ubicacion__sucursal=sucursal,
            ubicacion__tipo="bodega",
            cantidad_actual__gt=0
        )
        .values("producto")
        .distinct()
        .count()
    )

    # Cajas
    cajas = sucursal.cajas.all()

    # Últimos 5 tickets de venta
    ultimas_ventas = (
        Venta.objects
        .filter(ubicacion__sucursal=sucursal)
        .order_by("-fecha")[:5]
    )

    # Últimos 5 cortes de caja
    ultimos_cortes = (
        CorteCaja.objects
        .filter(caja__sucursal=sucursal)
        .order_by("-fecha")[:5]
    )

    return render(request, "sucursales/dashboard_sucursal.html", {
        "sucursal": sucursal,
        "productos_piso": productos_piso,
        "productos_bodega": productos_bodega,
        "cajas": cajas,
        "ultimas_ventas": ultimas_ventas,
        "ultimos_cortes": ultimos_cortes,
        "es_dueno": empleado.rol == "dueño",
        "puede_ver_historial": empleado.rol in ["dueño", "cajero"],
    })


@login_required
@require_POST
def eliminar_caja(request, caja_id):

    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"success": False, "error": "Sin permiso."}, status=403)

    caja = get_object_or_404(Caja, id=caja_id)
    sucursal_id = caja.sucursal_id
    caja.delete()

    cajas = list(
        Caja.objects
        .filter(sucursal_id=sucursal_id)
        .values("id", "nombre")
    )

    return JsonResponse({"success": True, "cajas": cajas})