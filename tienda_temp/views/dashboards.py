import json

from django.db.models import Sum, F, Value, Q
from django.db.models.functions import TruncMonth, Coalesce
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils.timezone import now
from django.utils.timezone import localtime
from datetime import timedelta
from django.utils.timezone import localtime
from django.contrib.auth.decorators import login_required
from sucursales.models import Sucursal
from ventas.models import Venta, VentaDetalle, piezas_vendidas
from ventas.services.reparto import totales_caja
from inventario.models import Categoria, Inventario, MovimientoInventario, Producto, Ubicacion
from inventario.services.filtros_service import filtrar_productos, nombres_filtros, parse_filtros





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
            .annotate(cantidad=piezas_vendidas())
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
        .annotate(cantidad=piezas_vendidas())
    )

    sin_codigo = (
        VentaDetalle.objects
        .filter(producto__dueño=empleado, **filtro_fecha)
        .filter(Q(producto__codigo_barras__isnull=True) | Q(producto__codigo_barras=""))
        .aggregate(cantidad=piezas_vendidas())["cantidad"] or 0
    )

    servicios = (
        VentaDetalle.objects
        .filter(
            producto__isnull=True,
            atributos_snapshot__tipo="servicio",
            venta__caja__sucursal__dueño_servicios=empleado,
            **filtro_fecha,
        )
        .aggregate(cantidad=piezas_vendidas())["cantidad"] or 0
    )

    resultado = list(productos)
    if sin_codigo:
        resultado.append({"nombre": "Productos sin código", "cantidad": sin_codigo})
    if servicios:
        resultado.append({"nombre": "Servicios", "cantidad": servicios})
    resultado.sort(key=lambda x: -x["cantidad"])
    return resultado[:10]


def _rango_periodo(periodo, hoy):
    """Traduce el periodo del explorador a (desde, hasta), ambas inclusive."""
    if periodo == "hoy":
        return hoy, hoy
    if periodo == "7":
        return hoy - timedelta(days=6), hoy
    if periodo == "mes":
        return hoy.replace(day=1), hoy
    return hoy - timedelta(days=29), hoy   # "30" — default


def _mas_vendidos_filtrado(empleado, desde, hasta, filtros, solo_mios=True, limite=10):
    """
    Top productos vendidos entre `desde` y `hasta` (fechas locales, ambas
    inclusive), acotado por categoría / subcategoría / atributos (ej. marca).

    A diferencia de _mas_vendidos_dueno aquí NO se agrupan "Servicios" ni
    "Productos sin código": filtrar por subcategoría o por marca solo tiene
    sentido sobre renglones con Producto ligado, y un servicio no lo tiene.
    """
    detalles = VentaDetalle.objects.filter(
        producto__isnull=False,
        venta__fecha__date__gte=desde,
        venta__fecha__date__lte=hasta,
    )

    if solo_mios:
        detalles = detalles.filter(producto__dueño=empleado)

    # El filtro por atributos se resuelve sobre Producto y se inyecta como
    # subconsulta: si se filtrara con JOINs sobre el detalle, cada JOIN a
    # valores_atributo duplicaría renglones e inflaría los Sum().
    if filtros["categoria"] or filtros["subcategoria"] or filtros["atributos"]:
        productos = filtrar_productos(
            categoria_id=filtros["categoria"],
            subcategoria_id=filtros["subcategoria"],
            atributos=filtros["atributos"],
        )
        detalles = detalles.filter(producto__in=productos.values("id"))

    filas = (
        detalles
        .values(nombre=F("producto__nombre"))
        .annotate(cantidad=piezas_vendidas(), ingreso=Sum("subtotal"))
        .order_by("-cantidad")[:limite]
    )

    # float() porque Decimal no es serializable a JSON.
    return [
        {
            "nombre": f["nombre"],
            "cantidad": f["cantidad"],
            "ingreso": round(float(f["ingreso"] or 0), 2),
        }
        for f in filas
    ]


@login_required
def api_mas_vendidos_dueno(request):
    """
    Explorador de más vendidos del dashboard dueño. Reusa parse_filtros de
    reportes, así que acepta los MISMOS parámetros (categoria, subcategoria,
    an/av para atributos por subcategoría, gan/gav para el global) más:
      - periodo: hoy | 7 | 30 | mes   (default 30)
      - mostrar: todos | mios         (default todos)
    """
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"error": "Acceso denegado."}, status=403)

    filtros = parse_filtros(request)
    periodo = (request.GET.get("periodo") or "30").strip()
    # Default: todo lo que se vendió en la tienda. "mios" acota a sus productos.
    solo_mios = request.GET.get("mostrar") == "mios"

    hoy = localtime(now()).date()
    desde, hasta = _rango_periodo(periodo, hoy)

    datos = _mas_vendidos_filtrado(empleado, desde, hasta, filtros, solo_mios=solo_mios)

    return JsonResponse({
        "datos": datos,
        "periodo": periodo,
        "solo_mios": solo_mios,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "filtros_legibles": nombres_filtros(filtros),
        "atributos": [{"nombre": n, "valor": v} for n, v in filtros["atributos"]],
        "total_unidades": sum(d["cantidad"] for d in datos),
        "total_ingreso": round(sum(d["ingreso"] for d in datos), 2),
    })


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
    # 2) El mes: efectivo que le tocó en los cortes y lo que entró a su
    #    Clip, día por día (corte_service.resumen_mes_dueno). Es lo que
    #    cada dueña compara contra lo que tiene en la mano y su app de Clip.
    # ============================================================
    from ventas.services.corte_service import resumen_mes_dueno, sumar_resumen_dueno
    mes = resumen_mes_dueno(empleado, hoy)

    # ============================================================
    # 2b) $ vendido AHORITA (hoy) — efectivo/tarjeta, su fila del corte
    #     (con servicios y "Prod. sin registro" si es la responsable).
    #     Se refresca en vivo por polling (dashboard_dueno.js →
    #     /ventas/api/ventas/hoy/), esto solo pinta el valor inicial.
    #     Es el día de hoy del mes (resumen_ventas_dueno_por_caja), ya
    #     calculado arriba.
    # ============================================================
    hoy_en_mes = mes["dias"][0] if mes["dias"] and mes["dias"][0]["fecha"] == hoy else None
    mis_por_caja = hoy_en_mes["cajas"] if hoy_en_mes else []
    ventas_hoy_dueno = sumar_resumen_dueno(mis_por_caja)
    # Lookup por caja_id — se cruza más abajo con TODAS las cajas de la
    # sucursal (aunque este dueño no haya vendido nada ahí hoy, se
    # muestra en $0 para que la lista no "desaparezca" una caja).
    dueno_por_caja_id = {d["caja_id"]: d for d in mis_por_caja}

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
        .annotate(cantidad=piezas_vendidas())
        .order_by("-cantidad")[:10]
    )

    # ============================================================
    # 4) Ventas HOY por sucursal → por caja → efectivo y tarjeta
    #    Recorre todas las sucursales y sus cajas, con las ventas
    #    de hoy — sin importar dueño del producto, porque esto es
    #    para saber cuánto hay físicamente en caja.
    #    totales_caja (reparto.py, el mismo cálculo que el corte):
    #    efectivo NETO = pagado_efectivo - cambio, o sea lo que
    #    físicamente queda en el cajón (sumar solo pagado_efectivo
    #    inflaba el efectivo); total = Σ venta.total, ya con descuento.
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

            t = totales_caja(ventas_caja)
            efectivo, tarjeta, total = t["efectivo"], t["tarjeta"], t["total"]

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
            mis = dueno_por_caja_id.get(caja.id, {"efectivo": 0, "tarjeta": 0, "total": 0, "saldo": 0, "en_caja": 0})
            ventas_hoy_dueno_por_caja.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": mis["efectivo"],
                "tarjeta": mis["tarjeta"],
                "total": mis["total"],
                "saldo": mis["saldo"],   # > 0 le deben, < 0 debe (cobros en el Clip de otra)
                "en_caja": mis["en_caja"],   # efectivo ya sin vales y gastos (caja chica)
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
    # 5) Vales y gastos (caja chica): esta semana y la pasada, para
    #    revisarlos el domingo y corregirlos.
    # ============================================================
    from caja_chica import api as caja_chica
    caja_chica_semanas = caja_chica.semanas_para_dashboard(hoy)

    # ============================================================
    # CONTEXTO FINAL
    # ============================================================
    context = {
        "productos_dueno": productos_dueno,
        "mes": mes,                                        # card del mes: efectivo / Clip / por día
        # Solo a la responsable de servicios se le desglosa productos /
        # servicios / sin registro (hoy) y los vales del mes; a las demás, no.
        "es_responsable_servicios": empleado.sucursales_como_responsable_servicios.exists(),
        "ventas_hoy_dueno": ventas_hoy_dueno,              # card "ahorita" (efectivo/tarjeta)
        "ventas_hoy_dueno_por_caja": ventas_hoy_dueno_por_caja,  # mismo, desglosado por caja
        "mes_actual": mes_actual,
        "mas_vendidos_hoy": list(mas_vendidos_hoy),
        "mas_vendidos_semana": list(mas_vendidos_semana),
        "mas_vendidos_tienda_hoy": list(mas_vendidos_tienda_hoy),
        "ventas_por_sucursal": ventas_por_sucursal,       # cards de cajas
        "ventas_chart_sucursal": ventas_chart_sucursal,   # chart de sucursales
        "caja_chica_semanas": caja_chica_semanas,         # [esta semana, la pasada]
        # Explorador de más vendidos: solo las categorías padre. Las
        # subcategorías y los atributos se piden por AJAX al elegir.
        "categorias_padre": Categoria.objects.filter(padre__isnull=True).order_by("nombre"),
        "ahora": now(),
    }

    return render(request, "tienda/dashboard_dueno.html", context)


@login_required
def base_conocimientos(request):
    # La guía enseña solo lo que el puesto de cada quien le deja hacer. Las
    # banderas copian las reglas de las vistas (pos_view, puede_transferir,
    # desactivar_producto, detalle_producto…): si cambia un permiso allá,
    # hay que cambiarlo aquí también. Superusuario sin perfil = ve todo.
    empleado = getattr(request.user, "empleado", None)
    if empleado:
        rol, rol_nombre = empleado.rol, empleado.get_rol_display()
    elif request.user.is_superuser:
        rol, rol_nombre = "dueño", "Administrador"
    else:
        rol, rol_nombre = None, ""

    return render(request, 'tienda/base_conocimientos.html', {
        "rol":              rol,
        "rol_nombre":       rol_nombre,
        "nombre":           request.user.first_name or request.user.username,
        "es_empleado":      rol is not None,
        "es_dueno":         rol == "dueño",
        "es_ayudante":      rol == "ayudante",
        "puede_caja":       rol in ("cajero", "dueño"),
        "puede_desactivar": rol in ("dueño", "cajero", "almacenista"),
        "puede_editar":     rol in ("dueño", "cajero"),
    })