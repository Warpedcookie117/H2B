
from django.db import models
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from inventario.models import Producto, Ubicacion
from django.db.models import Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.views.decorators.http import require_POST
import json
from django.core.serializers.json import DjangoJSONEncoder
from ventas.services.pos_service import POSService
from ventas.models import Promocion, Oferta
from sucursales.models import Sucursal
from django.http import JsonResponse


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

    print("\n\n================= DEBUG POS =================")
    print("Método:", request.method)
    print("URL:", request.path)

    # 0) Validar rol
    empleado = request.user.empleado
    print("Empleado:", empleado.id, empleado.rol)

    if empleado.rol not in ["cajero", "dueno", "dueño"]:
        print("ERROR: Rol inválido")
        return JsonResponse({"status": "error", "message": "No tienes permiso"}, status=403)

    # 1) Validar caja activa
    sucursal_id = request.session.get("sucursal_actual")
    caja_id = request.session.get("caja_actual")

    print("Sucursal en sesión:", sucursal_id)
    print("Caja en sesión:", caja_id)

    if not sucursal_id or not caja_id:
        print("ERROR: No hay sucursal o caja en sesión")
        return JsonResponse({"status": "error", "message": "Debes autenticarte en una caja."}, status=400)

    # 2) Obtener sucursal
    try:
        sucursal = Sucursal.objects.get(id=sucursal_id)
        print("Sucursal OK:", sucursal)
    except Sucursal.DoesNotExist:
        print("ERROR: Sucursal inválida")
        return JsonResponse({"status": "error", "message": "Sucursal inválida."}, status=400)

    # 3) Parsear JSON
    print("Raw body:", request.body)

    try:
        data = json.loads(request.body)
        print("JSON recibido:")
        print(json.dumps(data, indent=4))
    except Exception as e:
        print("ERROR PARSEANDO JSON:", str(e))
        return JsonResponse({"status": "error", "message": "JSON inválido."}, status=400)

    carrito = data.get("carrito", [])
    pagado_efectivo = data.get("pagado_efectivo")
    pagado_tarjeta = data.get("pagado_tarjeta")
    descuento_10 = data.get("descuento_10")

    print("\n--- CAMPOS RECIBIDOS ---")
    print("carrito:", carrito)
    print("pagado_efectivo:", pagado_efectivo)
    print("pagado_tarjeta:", pagado_tarjeta)
    print("descuento_10:", descuento_10)

    # 4) Validación básica
    if not carrito:
        print("ERROR: Carrito vacío")
        return JsonResponse({"status": "error", "message": "Carrito vacío."}, status=400)

    # 5) Convertir carrito
    carrito_real = []
    print("\n--- PROCESANDO CARRITO ---")
    for item in carrito:
        print("Item recibido:", item)

        try:
            producto_id = item.get("producto_id")
            cantidad = int(item.get("cantidad"))
            precio_aplicado = float(item.get("precio_aplicado"))

            print("[OK] producto_id:", producto_id,
                  "cantidad:", cantidad,
                  "precio:", precio_aplicado)

            carrito_real.append({
                "producto_id": producto_id,
                "cantidad": cantidad,
                "precio_aplicado": precio_aplicado,
            })

        except Exception as e:
            print("ERROR EN ITEM:", str(e))
            return JsonResponse({
                "status": "error",
                "message": f"Error en item del carrito: {str(e)}"
            }, status=400)

    # 6) Crear venta con POSService
    print("\n--- LLAMANDO POSService.crear_venta ---")
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

        print("VENTA CREADA OK:", venta.id)

        return JsonResponse({
            "status": "ok",
            "venta_id": venta.id,

            # 🔥 Datos que el modal necesita
            "total_venta": float(venta.total),
            "pagado_efectivo": float(pagado_efectivo),
            "pagado_tarjeta": float(pagado_tarjeta),
            "cambio": float(venta.cambio),

            # 🔥 Si tienes impresión automática, cámbialo a True
            "impresion_ok": False,

            # Opcional: si quieres seguir mandando esto
            "descuento": float(venta.descuento),

            # URLs para ver ticket
            "url_html": reverse("ventas:ticket_venta", args=[venta.id]),
            "url_pdf": reverse("ventas:ticket_venta_pdf", args=[venta.id]),
            "url_termico": reverse("ventas:ticket_venta_termico", args=[venta.id]),

            # Ticket ESC/POS para impresión automática
            "ticket_texto": ticket_texto,
        })

    except Exception as e:
        print("ERROR EN POSService:", str(e))
        return JsonResponse({
            "status": "error",
            "message": str(e)
        }, status=400)


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
