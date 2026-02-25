from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from inventario.models import Producto
import json
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .services.pos_service import POSService
from inventario.models import Producto, Ubicacion
from django.db.models import Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce




@login_required
def pos_view(request):

    # Ubicación del POS
    ubicacion_pos = Ubicacion.objects.get(nombre="Piso")

    # Productos con stock anotado correctamente
    productos = (
        Producto.objects.annotate(
            stock_piso=Coalesce(
                Sum(
                    Case(
                        When(
                            inventarios__ubicacion__nombre="Piso",
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
                            inventarios__ubicacion__nombre="Bodega Interna",
                            then="inventarios__cantidad_actual",
                        ),
                        default=0,
                        output_field=IntegerField(),
                    )
                ),
                0,
            ),
        )
        # 🔥 Solo mostrar productos con stock en piso
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



    
# API para procesar la venta en vivo desde el frontend
@login_required
@require_POST
def procesar_venta(request):

    # 1) Parsear JSON
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "JSON inválido"}, status=400)

    carrito = data.get("carrito", [])

    pagado_efectivo = float(data.get("pagado_efectivo", 0))
    pagado_tarjeta = float(data.get("pagado_tarjeta", 0))
    ubicacion_id = data.get("ubicacion_id")
    descuento_10 = bool(data.get("descuento_10", False))

    # 2) Validación básica
    if not carrito:
        return JsonResponse({"status": "error", "message": "Carrito vacío"}, status=400)

    # 3) Validar ubicación
    try:
        ubicacion = Ubicacion.objects.get(id=ubicacion_id)
    except Ubicacion.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Ubicación inválida"}, status=400)

    empleado = request.user.empleado

    # 4) Convertir carrito a estructura que POSService espera
    carrito_real = []
    for item in carrito:

        try:
            producto_id = item["producto_id"]
        except Exception:
            return JsonResponse({"status": "error", "message": "'producto_id' faltante"}, status=400)

        try:
            producto = Producto.objects.get(id=producto_id)
        except Producto.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Producto inválido"}, status=400)

        cantidad = int(item.get("cantidad", 0))
        precio_aplicado = float(item.get("precio_aplicado", 0))

        carrito_real.append({
            "producto_id": producto.id,
            "cantidad": cantidad,
            "precio_aplicado": precio_aplicado
        })

    # 5) Crear venta
    try:
        resultado = POSService.crear_venta(
            empleado=empleado,
            ubicacion=ubicacion,
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