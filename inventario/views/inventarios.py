from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.forms import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from inventario.forms import AgregarInventarioForm, AjusteInventarioForm, TransferenciaInventarioForm
from inventario.services.inventario_service import InventarioService
from inventario.models import MovimientoInventario, Producto, Inventario, SolicitudAjuste, TransferenciaInventario, Ubicacion
from django.http import JsonResponse
from django.db.models import Sum 
from django.utils.timezone import now
import json
from inventario.services.correo import enviar_correo
from django.urls import reverse
from main import settings






def dashboard_inventario(request):

    # KPIs principales
    productos_total = Producto.objects.count()

    stock_total = (
        Inventario.objects.aggregate(total=Sum("cantidad_actual"))["total"] or 0
    )

    ubicaciones = Ubicacion.objects.all()

    # Productos críticos (<= 5)
    bajos = (
        Inventario.objects
        .select_related("producto", "ubicacion")
        .filter(cantidad_actual__lte=5)
    )

    # Productos más vendidos (aunque sean 0)
    mas_vendidos = (
        MovimientoInventario.objects
        .filter(tipo="salida", motivo="venta")
        .values("producto__nombre")
        .annotate(total=Sum("cantidad"))
        .order_by("-total")[:10]
    )

    context = {
        "productos_total": productos_total,
        "stock_total": stock_total,
        "ubicaciones": ubicaciones,
        "bajos": bajos,
        "mas_vendidos": mas_vendidos,
        "ahora": now(),
    }

    return render(request, "inventario/dashboard_inventario.html", context)



#-----VISTAS PARA MANEJAR EL INVENTARIO--------#

@login_required
def agregar_inventario(request, producto_id, ubicacion_id):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "errors": ["Método no permitido"]},
            status=405
        )

    producto = get_object_or_404(Producto, id=producto_id)
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    inventario, _ = Inventario.objects.get_or_create(
        producto=producto,
        ubicacion=ubicacion,
        defaults={"cantidad_actual": 0}
    )

    # VALIDAR FORM
    form = AgregarInventarioForm(request.POST)

    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "errors": sum(form.errors.values(), [])
        })

    cantidad = form.cleaned_data["cantidad"]
    empleado = getattr(request.user, "empleado", None)

    try:
        inv = InventarioService.entrada(
            producto=producto,
            cantidad=cantidad,
            destino=ubicacion,
            empleado=empleado,
            motivo="reabastecimiento"
        )

        return JsonResponse({
            "success": True,
            "mensaje": f"{cantidad} piezas agregadas a {producto.nombre} en {ubicacion.nombre}.",
            "producto_id": producto.id,
            "ubicacion_id": ubicacion.id,
            "cantidad_actual": inv.cantidad_actual
        })

    except ValidationError as e:
        return JsonResponse({
            "success": False,
            "errors": e.messages
        })




@login_required
def transferir_inventario(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "errors": ["Método no permitido"]}, status=405)

    producto_id = request.POST.get("producto_id")
    origen_id = request.POST.get("origen_id")
    destino_id = request.POST.get("destino")   # ⭐ CORREGIDO
    cantidad = request.POST.get("cantidad")

    if not all([producto_id, origen_id, destino_id, cantidad]):
        return JsonResponse({"success": False, "errors": ["Datos incompletos"]})

    producto = get_object_or_404(Producto, id=producto_id)
    origen = get_object_or_404(Ubicacion, id=origen_id)
    destino = get_object_or_404(Ubicacion, id=destino_id)

    form = TransferenciaInventarioForm(
        request.POST,
        producto=producto,
        origen=origen
    )

    # ⭐ NECESARIO PARA QUE EL MODELO NO TRUENE
    form.instance.producto = producto
    form.instance.origen = origen
    form.instance.destino = destino

    if not form.is_valid():
        return JsonResponse({"success": False, "errors": sum(form.errors.values(), [])})

    cantidad = form.cleaned_data["cantidad"]
    empleado = getattr(request.user, "empleado", None)

    try:
        resultado = InventarioService.transferencia(
            producto=producto,
            cantidad=cantidad,
            origen=origen,
            destino=destino,
            empleado=empleado
        )
    except ValidationError as e:
        return JsonResponse({"success": False, "errors": e.messages})

    return JsonResponse({
        "success": True,
        "mensaje": f"Transferidos {cantidad} de {producto.nombre} hacia {destino.nombre}.",
        **resultado
    })








@login_required
def ajustar_inventario(request, producto_id, ubicacion_id):
    if request.method != "POST":
        return JsonResponse(
            {"success": False, "errors": ["Método no permitido"]},
            status=405
        )

    producto = get_object_or_404(Producto, id=producto_id)
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    inventario = get_object_or_404(
        Inventario,
        producto=producto,
        ubicacion=ubicacion
    )

    form = AjusteInventarioForm(request.POST)
    if not form.is_valid():
        return JsonResponse({
            "success": False,
            "errors": sum(form.errors.values(), [])
        })

    cantidad = form.cleaned_data["cantidad"]
    motivo = form.cleaned_data["motivo"]
    empleado = getattr(request.user, "empleado", None)

    cantidad_actual = inventario.cantidad_actual

    # ⭐ Si es dueño → ajuste directo SIEMPRE
    if empleado and empleado.rol == "dueño":
        inv = InventarioService.ajuste(
            producto=producto,
            nueva_cantidad=cantidad,
            ubicacion=ubicacion,
            empleado=empleado,
            motivo=motivo
        )

        return JsonResponse({
            "success": True,
            "producto_id": producto.id,
            "ubicacion_id": ubicacion.id,
            "cantidad_actual": inv.cantidad_actual,
            "ajuste_directo": True
        })

    # ⭐ Si NO es dueño:
    # Si la cantidad nueva es MAYOR → ajuste directo (no molestar al dueño)
    if cantidad > cantidad_actual:
        inv = InventarioService.ajuste(
            producto=producto,
            nueva_cantidad=cantidad,
            ubicacion=ubicacion,
            empleado=empleado,
            motivo=motivo
        )

        return JsonResponse({
            "success": True,
            "producto_id": producto.id,
            "ubicacion_id": ubicacion.id,
            "cantidad_actual": inv.cantidad_actual,
            "ajuste_directo": True
        })

    # ⭐ Si la cantidad nueva es MENOR → solicitud al dueño
    dueno = producto.dueño
    email_dueno = getattr(getattr(dueno, "user", None), "email", None)

    if not email_dueno:
        return JsonResponse({
            "success": False,
            "errors": ["El dueño del producto no tiene correo registrado."]
        })

    solicitud = SolicitudAjuste.objects.create(
        producto=producto,
        ubicacion=ubicacion,
        usuario=empleado.user,
        cantidad=cantidad,
        motivo=motivo,
    )

    url_aprobar = request.build_absolute_uri(
        reverse("inventario:aprobar_solicitud", args=[solicitud.id])
    )

    url_rechazar = request.build_absolute_uri(
        reverse("inventario:rechazar_solicitud", args=[solicitud.id])
    )

    mensaje = (
        f"El empleado {empleado.user.username} solicita ajustar el inventario.\n\n"
        f"Producto: {producto.nombre}\n"
        f"Ubicación: {ubicacion.nombre}\n"
        f"Nueva cantidad solicitada: {cantidad}\n"
        f"Motivo: {motivo}\n\n"
        f"Aprobar solicitud:\n{url_aprobar}\n\n"
        f"Rechazar solicitud:\n{url_rechazar}\n"
    )

    enviar_correo("Solicitud de ajuste de inventario", mensaje, email_dueno)

    return JsonResponse({
        "success": True,
        "solicitud": True,
        "mensaje": f"Solicitud enviada al dueño ({email_dueno})."
    })
    
    
    


#vista que aprueba la solicitudAjuste desde el link del correo.
@login_required
def aprobar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudAjuste, id=solicitud_id)

    if request.user != solicitud.producto.dueño:
        return render(request, "inventario/solicitudajuste/error_permiso.html")

    if solicitud.estado != "pendiente":
        return render(request, "inventario/solicitudajuste/error_procesada.html")

    InventarioService.aplicar_ajuste(solicitud, request.user.empleado)

    solicitud.estado = "aprobado"
    solicitud.fecha_respuesta = timezone.now()
    solicitud.save()

    return render(request, "inventario/solicitudajuste/solicitud_aprobada.html")
    
    
    
#vista que rechaza la solicitudAjuste desde el link del correo.
@login_required
def rechazar_solicitud(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudAjuste, id=solicitud_id)

    if request.user != solicitud.producto.dueño:
        return render(request, "inventario/solicitudajuste/error_permiso.html", {
            "mensaje": "No tienes permiso para rechazar esta solicitud."
        })

    if solicitud.estado != "pendiente":
        return render(request, "inventario/solicitudajuste/error_procesada.html", {
            "mensaje": "Esta solicitud ya fue procesada anteriormente."
        })

    solicitud.estado = "rechazado"
    solicitud.fecha_respuesta = timezone.now()
    solicitud.save()

    return render(request, "inventario/solicitudajuste/solicitud_rechazada.html", {
        "solicitud": solicitud
    })
    
@login_required

def aprobar_solicitud_panel(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudAjuste, id=solicitud_id)

    if solicitud.estado != "pendiente":
        messages.error(request, "Esta solicitud ya fue procesada.")
        return redirect("inventario:solicitudes_pendientes")

    # Aplicar ajuste con el dueño como responsable
    InventarioService.aplicar_ajuste(solicitud, request.user.empleado)

    solicitud.estado = "aprobado"
    solicitud.fecha_respuesta = timezone.now()
    solicitud.aprobado_por = request.user.empleado
    solicitud.save()

    messages.success(request, "Solicitud aprobada y ajuste aplicado correctamente.")
    return redirect("inventario:solicitudes_pendientes")

@login_required

def rechazar_solicitud_panel(request, solicitud_id):
    solicitud = get_object_or_404(SolicitudAjuste, id=solicitud_id)

    if solicitud.estado != "pendiente":
        messages.error(request, "Esta solicitud ya fue procesada.")
        return redirect("inventario:solicitudes_pendientes")

    solicitud.estado = "rechazado"
    solicitud.fecha_respuesta = timezone.now()
    solicitud.aprobado_por = request.user.empleado
    solicitud.save()

    messages.success(request, "Solicitud rechazada correctamente.")
    return redirect("inventario:solicitudes_pendientes")


#opcion en el navbar para ver las solicitudes pendientes de empleados 
@login_required
def mis_solicitudes(request):
    solicitudes = SolicitudAjuste.objects.filter(usuario=request.user).order_by("-fecha_solicitud")

    return render(request, "inventario/mis_solicitudes.html", {
        "solicitudes": solicitudes
    })
    
#solicitudes pendientes para el dueño, donde podra aceptar o rechazar la solicitud.
@login_required
def solicitudes_pendientes(request):
    empleado = getattr(request.user, "empleado", None)

    # Solo dueños pueden ver solicitudes pendientes
    if not empleado or empleado.rol != "dueño":
        return render(request, "inventario/solicitudajuste/error_permiso.html")

    solicitudes = SolicitudAjuste.objects.filter(
        producto__dueño=request.user.empleado,
        estado="pendiente"
    ).order_by("-fecha_solicitud")

    # Preparamos datos completos para el template
    solicitudes_data = []

    for s in solicitudes:
        inventario = Inventario.objects.get(
            producto=s.producto,
            ubicacion=s.ubicacion
        )

        solicitudes_data.append({
            "solicitud": s,
            "cantidad_actual": inventario.cantidad_actual,
        })

    return render(request, "inventario/solicitudes_pendientes.html", {
        "solicitudes": solicitudes_data
    })

#vistas para la transferencia multiple de inventario

@login_required
def buscar_producto_en_ubicacion(request):
    q = request.GET.get("q", "").strip()
    ubicacion_id = request.GET.get("ubicacion")

    if not q or not ubicacion_id:
        return JsonResponse({"resultados": []})

    inventarios = (
        Inventario.objects
        .filter(
            ubicacion_id=ubicacion_id,
            producto__nombre__icontains=q
        )
        .select_related("producto")
        .order_by("producto__nombre")
    )

    resultados = [
        {
            "id": inv.producto.id,
            "nombre": inv.producto.nombre,
            "cantidad_actual": inv.cantidad_actual,
        }
        for inv in inventarios
    ]

    return JsonResponse({"resultados": resultados})


@login_required
def transferencia_multiple(request, ubicacion_origen_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "errors": ["Método no permitido."]}, status=405)

    origen = get_object_or_404(Ubicacion, id=ubicacion_origen_id)
    empleado = getattr(request.user, "empleado", None)

    try:
        data = json.loads(request.body)
    except:
        return JsonResponse({"success": False, "errors": ["Formato JSON inválido."]})

    destino_id = data.get("destino_id")
    if not destino_id:
        return JsonResponse({"success": False, "errors": ["Debes seleccionar una ubicación destino."]})

    destino = get_object_or_404(Ubicacion, id=destino_id)

    productos_raw = data.get("productos", [])
    if not productos_raw:
        return JsonResponse({"success": False, "errors": ["No se enviaron productos para transferir."]})

    # Convertir a objetos reales
    productos = []
    for item in productos_raw:
        producto = get_object_or_404(Producto, id=item["id"])
        cantidad = int(item["cantidad"])
        productos.append({"producto": producto, "cantidad": cantidad})

    try:
        resultados = InventarioService.transferencia_multiple(
            origen=origen,
            destino=destino,
            productos=productos,
            empleado=empleado
        )
    except ValidationError as e:
        return JsonResponse({"success": False, "errors": e.messages})

    return JsonResponse({
        "success": True,
        "mensaje": "Redistribución completada correctamente.",
        "resultados": resultados
    })
        
    
#Ajax para el formulario de nevo producto.    
#Existe este producto en la base de datos?, existe inventario de este producto en esta ubicacion?
@login_required
def verificar_estado_producto(request):
    producto_id = request.GET.get('producto')
    ubicacion_id = request.GET.get('ubicacion')

    producto_existe = Producto.objects.filter(id=producto_id).exists()

    inventario_existe = False
    if producto_existe and ubicacion_id:
        inventario_existe = Inventario.objects.filter(
            producto_id=producto_id,
            ubicacion_id=ubicacion_id
        ).exists()

    return JsonResponse({
        'producto_existe': producto_existe,
        'inventario_existe': inventario_existe
    })
    
@login_required
def eliminar_inventario_ubicacion(request, producto_id, ubicacion_id):
    if request.method != "DELETE":
        return JsonResponse(
            {"success": False, "errors": ["Método no permitido"]},
            status=405
        )

    inventario = Inventario.objects.filter(
        producto_id=producto_id,
        ubicacion_id=ubicacion_id
    ).first()

    if not inventario:
        return JsonResponse({
            "success": False,
            "errors": ["No existe inventario en esta ubicación."]
        })

    inventario.delete()

    return JsonResponse({"success": True})

#sirve para decir cuantas ubicaciones tienen inventario, cuales, cuanto hay para saber que modal abrir
@login_required
def ubicaciones_del_producto(request, producto_id):
    inventarios = (
        Inventario.objects
        .filter(producto_id=producto_id, cantidad_actual__gt=0)
        .select_related("ubicacion")
    )

    ubicaciones = [
        {
            "id": inv.ubicacion.id,
            "nombre": inv.ubicacion.nombre,
            "cantidad": inv.cantidad_actual,
        }
        for inv in inventarios
    ]

    return JsonResponse({
        "total": len(ubicaciones),
        "ubicaciones": ubicaciones
    })