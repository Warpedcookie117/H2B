import json

from django.db.models import Sum, F, Value, Q
from django.db.models.functions import TruncMonth, Coalesce
from django.shortcuts import render, redirect
from django.contrib import messages
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


def _mas_vendidos_dueno(empleado, filtro_fecha):
    """
    Top productos vendidos de `empleado` bajo el filtro de fecha dado
    (ej. {"venta__fecha__date": hoy} o {"venta__fecha__gte": hace_7_dias}).

    Servicios y productos sin código de barras no tienen caso desglosarlos
    uno por uno en un top — se agrupan en una sola barra cada uno:
    "Servicios" (atribuidos vía Sucursal.dueño_servicios, ya que un
    renglón de servicio no tiene Producto ligado) y "Productos sin código".
    """
    productos = (
        VentaDetalle.objects
        .filter(producto__dueño=empleado, **filtro_fecha)
        .exclude(producto__codigo_barras__isnull=True)
        .exclude(producto__codigo_barras="")
        .values(nombre=F("producto__nombre"))
        .annotate(cantidad=Sum("cantidad"))
    )

    sin_codigo = (
        VentaDetalle.objects
        .filter(producto__dueño=empleado, **filtro_fecha)
        .filter(Q(producto__codigo_barras__isnull=True) | Q(producto__codigo_barras=""))
        .aggregate(cantidad=Sum("cantidad"))["cantidad"] or 0
    )

    servicios = (
        VentaDetalle.objects
        .filter(
            producto__isnull=True,
            atributos_snapshot__tipo="servicio",
            venta__caja__sucursal__dueño_servicios=empleado,
            **filtro_fecha,
        )
        .aggregate(cantidad=Sum("cantidad"))["cantidad"] or 0
    )

    resultado = list(productos)
    if sin_codigo:
        resultado.append({"nombre": "Productos sin código", "cantidad": sin_codigo})
    if servicios:
        resultado.append({"nombre": "Servicios", "cantidad": servicios})
    resultado.sort(key=lambda x: -x["cantidad"])
    return resultado[:10]


@login_required
def dashboard_dueno(request):

    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        messages.error(request, "Acceso denegado.")
        return redirect("tienda_temp:dashboard_socio")

    # now() regresa UTC — pasadas las 6pm hora de Monterrey (UTC-6) ya cae
    # en el dia siguiente en UTC. Todo lo que se compara contra un
    # calendario (dia/mes) debe pasar por localtime() primero.
    ahora_local = localtime(now())
    hoy = ahora_local.date()
    mes_actual = ahora_local.strftime("%B").capitalize()

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
            venta__fecha__month=ahora_local.month,
            venta__fecha__year=ahora_local.year
        )
        .aggregate(total=Sum("subtotal"))
        .get("total") or 0
    )

    # ============================================================
    # 2b) $ vendido de mis productos AHORITA (hoy) — efectivo/tarjeta.
    #     Se refresca en vivo por polling (dashboard_dueno.js →
    #     /ventas/api/ventas/hoy/), esto solo pinta el valor inicial.
    # ============================================================
    from ventas.services.corte_service import resumen_ventas_dueno_por_fecha, resumen_ventas_dueno_por_caja
    ventas_hoy_dueno = resumen_ventas_dueno_por_fecha(empleado, hoy)
    # Lookup por caja_id — se cruza más abajo con TODAS las cajas de la
    # sucursal (aunque este dueño no haya vendido nada ahí hoy, se
    # muestra en $0 para que la lista no "desaparezca" una caja).
    dueno_por_caja_id = {d["caja_id"]: d for d in resumen_ventas_dueno_por_caja(empleado, hoy)}

    # ============================================================
    # 3) Mis productos más vendidos — hoy y última semana.
    #    Incluye "Servicios" y "Productos sin código" como barras
    #    aparte (ver _mas_vendidos_dueno).
    # ============================================================
    hace_7_dias = ahora_local - timedelta(days=7)

    mas_vendidos_hoy = _mas_vendidos_dueno(empleado, {"venta__fecha__date": hoy})
    mas_vendidos_semana = _mas_vendidos_dueno(empleado, {"venta__fecha__gte": hace_7_dias})

    # ============================================================
    # 3b) Más vendidos en TODA la tienda hoy — sin filtrar por dueño.
    #     nombre_snapshot cubre servicios y productos sin código (no
    #     tienen FK a Producto) y productos ya eliminados — sin esto,
    #     producto__nombre sale None y Python "None" rompe el <script>
    #     del dashboard completo en el navegador (no es JS válido).
    # ============================================================
    mas_vendidos_tienda_hoy = (
        VentaDetalle.objects
        .filter(venta__fecha__date=hoy)
        .values(nombre=Coalesce("nombre_snapshot", "producto__nombre", Value("Producto eliminado")))
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
    ventas_hoy_dueno_por_caja = []   # desglose "mis productos" — misma lista, todas las cajas

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

            # Desglose de SOLO mis productos en esta caja — en $0 si hoy
            # no vendí nada ahí, para que la caja no "desaparezca" de la lista.
            mis = dueno_por_caja_id.get(caja.id, {"efectivo": 0, "tarjeta": 0, "total": 0})
            ventas_hoy_dueno_por_caja.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": mis["efectivo"],
                "tarjeta": mis["tarjeta"],
                "total": mis["total"],
            })

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
        "ventas_hoy_dueno": ventas_hoy_dueno,              # card "ahorita" (efectivo/tarjeta)
        "ventas_hoy_dueno_por_caja": ventas_hoy_dueno_por_caja,  # mismo, desglosado por caja
        "mes_actual": mes_actual,
        "mas_vendidos_hoy": list(mas_vendidos_hoy),
        "mas_vendidos_semana": list(mas_vendidos_semana),
        "mas_vendidos_tienda_hoy": list(mas_vendidos_tienda_hoy),
        "ventas_por_sucursal": ventas_por_sucursal,       # cards de cajas
        "ventas_chart_sucursal": ventas_chart_sucursal,   # chart de sucursales
        "ahora": now(),
    }

    return render(request, "tienda/dashboard_dueno.html", context)


def base_conocimientos(request):
    return render(request, 'tienda/base_conocimientos.html')