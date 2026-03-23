from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from inventario.models import Producto, Ubicacion
from django.db.models import Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json
from sucursales.models import Sucursal
from ventas.models import CorteCaja, Venta
from .services.pos_service import POSService
from django.contrib import messages
from django.shortcuts import redirect, render


@login_required
def pos_view(request):

    empleado = request.user.empleado

    # 0) Validar rol
    if empleado.rol not in ["cajero", "dueño"]:
        messages.error(request, "No tienes permiso para usar el POS.")
        return redirect("sucursales:crear_sucursal")  # ruta segura

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
                            inventarios__ubicacion__tipo="bodega_interna",
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

    return render(
        request,
        "ventas/pos.html",
        {
            "productos": productos,
            "ubicacion_pos": ubicacion_pos,
        },
    )


    
    
@login_required
@require_POST
def procesar_venta(request):

    # 0) Validar rol
    empleado = request.user.empleado
    if empleado.rol not in ["cajero", "dueno"]:
        return JsonResponse({
            "status": "error",
            "message": "No tienes permiso para procesar ventas."
        }, status=403)

    # 1) Validar caja activa
    sucursal_id = request.session.get("sucursal_actual")
    caja_id = request.session.get("caja_actual")

    if not sucursal_id or not caja_id:
        return JsonResponse({
            "status": "error",
            "message": "Debes autenticarte en una caja."
        }, status=400)

    # 🔥 1.5) Obtener objeto sucursal (ESTO FALTABA)
    sucursal = Sucursal.objects.get(id=sucursal_id)

    # 2) Parsear JSON
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "JSON inválido"}, status=400)

    carrito = data.get("carrito", [])
    pagado_efectivo = float(data.get("pagado_efectivo", 0))
    pagado_tarjeta = float(data.get("pagado_tarjeta", 0))
    descuento_10 = bool(data.get("descuento_10", False))

    # 3) Validación básica
    if not carrito:
        return JsonResponse({"status": "error", "message": "Carrito vacío"}, status=400)

    # 4) Convertir carrito
    carrito_real = []
    for item in carrito:
        producto_id = item.get("producto_id")
        cantidad = int(item.get("cantidad", 0))
        precio_aplicado = float(item.get("precio_aplicado", 0))

        carrito_real.append({
            "producto_id": producto_id,
            "cantidad": cantidad,
            "precio_aplicado": precio_aplicado
        })

    # 5) Crear venta
    try:
        resultado = POSService.crear_venta(
            empleado=empleado,
            sucursal=sucursal,      # ✔ ahora sí existe
            caja_id=caja_id,        # ✔ clave
            carrito=carrito_real,
            pagado_efectivo=pagado_efectivo,
            pagado_tarjeta=pagado_tarjeta,
            descuento_10=descuento_10
        )

        venta = resultado["venta"]

        return JsonResponse({
            "status": "ok",
            "venta_id": venta.id,
            "total": float(venta.total),
            "cambio": float(venta.cambio),
            "descuento": float(venta.descuento),
        })

    except Exception as e:
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)
        
        
        
@login_required
def ticket_corte(request, corte_id):
    corte = get_object_or_404(CorteCaja, id=corte_id)

    contexto = {
        "corte": corte,
        "caja": corte.caja,
        "empleado": corte.empleado,
        "fecha": corte.fecha,
        "total_general": corte.total_general,
        "totales_dueno": corte.total_por_dueno,
    }

    return render(request, "ventas/ticket_corte.html", contexto)



@login_required
def ticket_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)

    detalles = venta.detalles.all()  # 🔥 VentaDetalle

    contexto = {
        "venta": venta,
        "detalles": detalles,
        "empleado": venta.empleado,
        "fecha": venta.fecha,
        "total": venta.total,
        "subtotal": venta.subtotal,
        "descuento": venta.descuento,
        "metodo_pago": venta.metodo_pago,
        "pagado_efectivo": venta.pagado_efectivo,
        "pagado_tarjeta": venta.pagado_tarjeta,
        "cambio": venta.cambio,
    }

    return render(request, "ventas/ticket_venta.html", contexto)

