
from django.db import models
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from inventario.models import Producto, Ubicacion
from django.db.models import Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST
from django.core.cache import cache
import json
import logging
from django.core.serializers.json import DjangoJSONEncoder
from ventas.services.pos_service import POSService
from ventas.models import Promocion, Oferta
from sucursales.models import Sucursal
from django.http import JsonResponse

logger = logging.getLogger(__name__)


@login_required
def pos_view(request):

    empleado = request.user.empleado

    # 0) Validar rol
    if empleado.rol not in ["cajero", "dueño"]:
        messages.error(request, "No tienes permiso para usar el POS.")
        return redirect("tienda_temp:dashboard_socio")

    # 1) Validar sucursal activa
    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        messages.error(request, "Debes seleccionar una sucursal.")
        return redirect("sucursales:crear_sucursal")  # ruta segura

    # 2) Validar caja activa
    caja_id = request.session.get("caja_actual")
    if not caja_id:
        messages.error(request, "Debes autenticarte en una caja.")
        return redirect("sucursales:dashboard_sucursal", sucursal_id=sucursal_id)

    # 3) Obtener Piso
    try:
        ubicacion_pos = Ubicacion.objects.get(
            sucursal_id=sucursal_id,
            tipo="piso"
        )
    except Ubicacion.DoesNotExist:
        messages.error(request, "La sucursal no tiene Piso configurado.")
        return redirect("sucursales:dashboard_sucursal", sucursal_id=sucursal_id)

    # 4) Cargar productos
    productos = (
        Producto.objects.annotate(
            stock_piso=Coalesce(
                Sum(
                    Case(
                        When(
                            inventarios__ubicacion__sucursal_id=sucursal_id,
                            inventarios__ubicacion__tipo="piso",
                            then="inventarios__cantidad_actual",
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
            stock_bodega=Coalesce(
                Sum(
                    Case(
                        When(
                            inventarios__ubicacion__sucursal_id=sucursal_id,
                            inventarios__ubicacion__tipo="bodega",
                            then="inventarios__cantidad_actual",
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
        )
        .filter(stock_piso__gt=0)
        .order_by("nombre")
    )
    from sucursales.models import Caja
    caja_nombre = "Caja"
    try:
        caja_nombre = Caja.objects.get(id=caja_id).nombre
    except Caja.DoesNotExist:
        pass

    from datetime import date
    hoy = date.today()

    # Prefetch attribute values for POS offer filtering
    productos_list = list(productos.prefetch_related('valores_atributo__atributo'))
    for p in productos_list:
        p.atributos_json = json.dumps(
            {va.atributo.nombre: va.valor for va in p.valores_atributo.all()},
            cls=DjangoJSONEncoder,
        )

    promociones_data = list(
        Promocion.objects.filter(activo=True).values(
            "id", "nombre", "tipo_condicion", "tipo_resultado",
            "categoria_disparadora_id", "monto_minimo",
            "producto_regalo_id", "categoria_regalo_id",
            "filtros_atributos",
        )
    )

    ofertas_qs = Oferta.objects.filter(activo=True).filter(
        models.Q(fecha_inicio__isnull=True) | models.Q(fecha_inicio__lte=hoy)
    ).filter(
        models.Q(fecha_fin__isnull=True) | models.Q(fecha_fin__gte=hoy)
    )
    ofertas_data = list(ofertas_qs.values(
        "id", "nombre", "tipo", "aplica_a",
        "producto_id", "categoria_id",
        "valor", "cantidad_n",
        "filtros_atributos",
    ))

    return render(
        request,
        "ventas/pos.html",
        {
            "productos":      productos_list,
            "ubicacion_pos":  ubicacion_pos,
            "caja_nombre":    caja_nombre,
            "promociones_json": json.dumps(promociones_data, cls=DjangoJSONEncoder),
            "ofertas_json":     json.dumps(ofertas_data,    cls=DjangoJSONEncoder),
        },
    )


    
@login_required
@require_POST
def procesar_venta(request):

    # 0) Validar rol
    empleado = request.user.empleado

    if empleado.rol not in ["cajero", "dueno", "dueño"]:
        return JsonResponse({"status": "error", "message": "No tienes permiso"}, status=403)

    # Guard contra doble envío: un solo request activo por empleado
    lock_key = f"pos_lock_{empleado.id}"
    if cache.get(lock_key):
        return JsonResponse({"status": "error", "message": "Venta en proceso, espera un momento."}, status=409)
    cache.set(lock_key, True, timeout=15)

    try:
        # 1) Validar caja activa
        sucursal_id = request.session.get("sucursal_actual")
        caja_id = request.session.get("caja_actual")

        if not sucursal_id or not caja_id:
            return JsonResponse({"status": "error", "message": "Debes autenticarte en una caja."}, status=400)

        # 2) Obtener sucursal
        try:
            sucursal = Sucursal.objects.get(id=sucursal_id)
        except Sucursal.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Sucursal inválida."}, status=400)

        # Verificar que la caja pertenece a esta sucursal
        from sucursales.models import Caja
        if not Caja.objects.filter(id=caja_id, sucursal_id=sucursal_id).exists():
            return JsonResponse({"status": "error", "message": "Caja no válida para esta sucursal."}, status=403)

        # 3) Parsear JSON
        try:
            data = json.loads(request.body)
        except Exception:
            return JsonResponse({"status": "error", "message": "JSON inválido."}, status=400)

        carrito = data.get("carrito", [])
        pagado_efectivo = data.get("pagado_efectivo")
        pagado_tarjeta = data.get("pagado_tarjeta")
        descuento_10 = data.get("descuento_10")

        # 4) Validación básica
        if not carrito:
            return JsonResponse({"status": "error", "message": "Carrito vacío."}, status=400)

        # 5) Convertir carrito
        carrito_real = []
        for item in carrito:
            try:
                carrito_real.append({
                    "producto_id":    item.get("producto_id"),
                    "cantidad":       int(item.get("cantidad")),
                    "precio_aplicado": float(item.get("precio_aplicado")),
                    "es_servicio":    item.get("es_servicio", False),
                    "es_regalo":      item.get("es_regalo", False),
                    "nombre_servicio": item.get("nombre_servicio", ""),
                    "promo_id":       item.get("promo_id"),
                    "promo_nombre":   item.get("promo_nombre", ""),
                })
            except Exception:
                return JsonResponse({"status": "error", "message": "Error en item del carrito."}, status=400)

        # 6) Crear venta con POSService
        try:
            resultado = POSService.crear_venta(
                empleado=empleado,
                sucursal=sucursal,
                caja_id=caja_id,
                carrito=carrito_real,
                pagado_efectivo=float(pagado_efectivo),
                pagado_tarjeta=float(pagado_tarjeta),
                descuento_10=bool(descuento_10)
            )

            venta = resultado["venta"]
            ticket_texto = resultado["ticket_texto"]

            return JsonResponse({
                "status": "ok",
                "venta_id": venta.id,
                "total_venta": float(venta.total),
                "pagado_efectivo": float(pagado_efectivo),
                "pagado_tarjeta": float(pagado_tarjeta),
                "cambio": float(venta.cambio),
                "impresion_ok": False,
                "descuento": float(venta.descuento),
                "url_html": reverse("ventas:ticket_venta", args=[venta.id]),
                "url_pdf": reverse("ventas:ticket_venta_pdf", args=[venta.id]),
                "url_termico": reverse("ventas:ticket_venta_termico", args=[venta.id]),
                "ticket_texto": ticket_texto,
            })

        except Exception as e:
            logger.error("Error en POSService.crear_venta: %s", e, exc_info=True)
            return JsonResponse({"status": "error", "message": "Error al procesar la venta."}, status=400)

    finally:
        cache.delete(lock_key)


@login_required
def stock_productos(request):
    """
    Devuelve el stock actualizado de todos los productos en la sucursal activa.
    Usado por el POS para refrescar las tarjetas sin recargar la página.
    """
    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        return JsonResponse({"error": "Sin sucursal"}, status=400)

    productos = Producto.objects.annotate(
        stock_piso=Coalesce(
            Sum(
                Case(
                    When(
                        inventarios__ubicacion__sucursal_id=sucursal_id,
                        inventarios__ubicacion__tipo="piso",
                        then="inventarios__cantidad_actual",
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            0,
        ),
        stock_bodega=Coalesce(
            Sum(
                Case(
                    When(
                        inventarios__ubicacion__sucursal_id=sucursal_id,
                        inventarios__ubicacion__tipo="bodega",
                        then="inventarios__cantidad_actual",
                    ),
                    default=0,
                    output_field=IntegerField(),
                )
            ),
            0,
        ),
    ).values("id", "stock_piso", "stock_bodega")

    data = {p["id"]: {"piso": p["stock_piso"], "bodega": p["stock_bodega"]} for p in productos}
    return JsonResponse(data)
