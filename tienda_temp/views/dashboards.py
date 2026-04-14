import json

from django.db.models import Sum, F
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils.timezone import now
from django.utils.timezone import localtime
from datetime import timedelta
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from sucursales.models import Sucursal
from ventas.models import Venta, VentaDetalle
from inventario.models import Categoria, Inventario, MovimientoInventario, Producto, Ubicacion





@login_required
def dashboard_socio(request):
 
    hoy = now().date()
    hace_7_dias = now() - timedelta(days=7)
 
    # ============================================================
    # 1) Total de productos registrados en toda la DB (activos)
    # ============================================================
    total_productos = Producto.objects.filter(activo=True).count()
 
    # ============================================================
    # 2) Productos disponibles en piso (con stock > 0)
    # ============================================================
    productos_en_piso = (
        Inventario.objects
        .filter(cantidad_actual__gt=0, ubicacion__tipo="piso")
        .values("producto")
        .distinct()
        .count()
    )
 
    # ============================================================
    # 3) Familias de productos (subcategorías — padre no nulo)
    # ============================================================
    total_familias = Categoria.objects.filter(padre__isnull=False).count()
 
    # ============================================================
    # 4) Stock bajo (menos de 5 en piso) — para la lista
    # ============================================================
    stock_bajo = (
        Inventario.objects
        .filter(cantidad_actual__lt=5, cantidad_actual__gt=0, ubicacion__tipo="piso")
        .select_related("producto", "ubicacion")
        .order_by("cantidad_actual")[:8]
    )
 
    # ============================================================
    # 5) Más vendidos y menos vendidos por sucursal (última semana)
    # ============================================================
    sucursales = Sucursal.objects.all().order_by("nombre")
    graficas_sucursal = []
 
    for sucursal in sucursales:
        ventas_qs = (
            VentaDetalle.objects
            .filter(
                venta__fecha__gte=hace_7_dias,
                venta__ubicacion__sucursal=sucursal
            )
            .values(nombre=F("producto__nombre"))
            .annotate(cantidad=Sum("cantidad"))
            .order_by("-cantidad")
        )
 
        if not ventas_qs:
            graficas_sucursal.append({
                "sucursal": sucursal.nombre,
                "mas_labels": [],
                "mas_data": [],
                "menos_labels": [],
                "menos_data": [],
            })
            continue
 
        ventas_list = list(ventas_qs)
        mas = ventas_list[:5]
        menos = sorted(ventas_list[-5:], key=lambda x: x["cantidad"])
 
        graficas_sucursal.append({
            "sucursal": sucursal.nombre,
            "mas_labels": [v["nombre"] for v in mas],
            "mas_data": [v["cantidad"] for v in mas],
            "menos_labels": [v["nombre"] for v in menos],
            "menos_data": [v["cantidad"] for v in menos],
        })
 
    context = {
        "total_productos": total_productos,
        "productos_en_piso": productos_en_piso,
        "total_familias": total_familias,
        "stock_bajo": stock_bajo,
        "graficas_sucursal": graficas_sucursal,
        "graficas_sucursal_json": json.dumps(graficas_sucursal),
        "ahora": now(),
    }
 
    return render(request, "tienda/dashboard_socio.html", context)



def dashboard_dueno(request):

    empleado = request.user.empleado
    hoy = now().date()
    mes_actual = now().strftime("%B").capitalize()

    # ============================================================
    # 1) Productos activos a mi nombre
    # ============================================================
    productos_dueno = Producto.objects.filter(dueño=empleado, activo=True).count()

    # ============================================================
    # 2) Ventas del mes SOLO de mis productos
    #    Suma los subtotales de VentaDetalle donde el producto
    #    es mío, en el mes actual. Usa subtotal del detalle
    #    para no contar el total de la venta completa.
    # ============================================================
    ventas_mes_dueno = (
        VentaDetalle.objects
        .filter(
            producto__dueño=empleado,
            venta__fecha__month=now().month,
            venta__fecha__year=now().year
        )
        .aggregate(total=Sum("subtotal"))
        .get("total") or 0
    )

    # ============================================================
    # 3) Mis productos más vendidos en la última semana
    #    Agrupa por nombre del producto y suma cantidades.
    # ============================================================
    hace_7_dias = localtime(now()) - timedelta(days=7)

    mas_vendidos_semana = (
        VentaDetalle.objects
        .filter(
            producto__dueño=empleado,
            venta__fecha__gte=hace_7_dias
        )
        .values(nombre=F("producto__nombre"))
        .annotate(cantidad=Sum("cantidad"))
        .order_by("-cantidad")[:10]
    )

    # ============================================================
    # 4) Ventas HOY por sucursal → por caja → efectivo y tarjeta
    #    Recorre todas las sucursales y sus cajas.
    #    Por cada caja suma pagado_efectivo y pagado_tarjeta
    #    de las ventas de hoy — sin importar dueño del producto,
    #    porque esto es para saber cuánto hay físicamente en caja.
    # ============================================================
    from sucursales.models import Sucursal, Caja

    sucursales = Sucursal.objects.prefetch_related("cajas").all().order_by("nombre")

    ventas_por_sucursal = []
    ventas_chart_sucursal = []

    for sucursal in sucursales:
        cajas_data = []
        total_sucursal = 0
        efectivo_sucursal = 0
        tarjeta_sucursal = 0

        for caja in sucursal.cajas.all().order_by("nombre"):
            ventas_caja = Venta.objects.filter(caja=caja, fecha__date=hoy)

            efectivo = ventas_caja.aggregate(
                total=Sum("pagado_efectivo")
            ).get("total") or 0

            tarjeta = ventas_caja.aggregate(
                total=Sum("pagado_tarjeta")
            ).get("total") or 0

            total = efectivo + tarjeta

            ultima_venta = ventas_caja.order_by("-fecha").first()
            ultima_actualizacion = ultima_venta.fecha if ultima_venta else None

            cajas_data.append({
                "nombre": caja.nombre,
                "efectivo": efectivo,
                "tarjeta": tarjeta,
                "total": total,
                "ultima_actualizacion": ultima_actualizacion,
            })

            # Acumular para el chart de sucursal
            efectivo_sucursal += float(efectivo)
            tarjeta_sucursal += float(tarjeta)
            total_sucursal += float(total)

        ventas_por_sucursal.append({
            "sucursal": sucursal.nombre,
            "cajas": cajas_data,
        })

        # ⭐ Totales por sucursal para el chart
        ventas_chart_sucursal.append({
            "nombre": sucursal.nombre,
            "efectivo": round(efectivo_sucursal, 2),
            "tarjeta": round(tarjeta_sucursal, 2),
            "total": round(total_sucursal, 2),
        })

    # ============================================================
    # CONTEXTO FINAL
    # ============================================================
    context = {
        "productos_dueno": productos_dueno,
        "ventas_mes_dueno": ventas_mes_dueno,
        "mes_actual": mes_actual,
        "mas_vendidos_semana": list(mas_vendidos_semana),
        "ventas_por_sucursal": ventas_por_sucursal,       # cards de cajas
        "ventas_chart_sucursal": ventas_chart_sucursal,   # chart de sucursales
        "ahora": now(),
    }

    return render(request, "tienda/dashboard_dueno.html", context)


def base_conocimientos(request):
    return render(request, 'tienda/base_conocimientos.html')