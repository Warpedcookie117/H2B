
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from inventario.models import Inventario, Producto, Ubicacion
from sucursales.models import Sucursal
from tienda_temp.models import Empleado
from ventas.models import IdempotencyKey, Oferta, Promocion
from ventas.services.pos_service import POSService

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

    from sucursales.models import Caja
    caja_nombre = "Caja"
    try:
        caja_nombre = Caja.objects.get(id=caja_id).nombre
    except Caja.DoesNotExist:
        pass

    from datetime import date
    hoy = date.today()

    # 4) Cargar productos — lookup directo por ubicacion_id (evita GROUP BY + HAVING)
    # Sin caché: siempre datos reales de la BD; el WS mantiene el stock en vivo tras la carga.
    piso_map = {
        inv["producto_id"]: inv["cantidad_actual"]
        for inv in Inventario.objects.filter(
            ubicacion=ubicacion_pos, cantidad_actual__gt=0
        ).values("producto_id", "cantidad_actual")
    }

    bodega_map = {}
    ubicacion_bodega = Ubicacion.objects.filter(
        sucursal_id=sucursal_id, tipo="bodega"
    ).first()
    if ubicacion_bodega and piso_map:
        bodega_map = {
            inv["producto_id"]: inv["cantidad_actual"]
            for inv in Inventario.objects.filter(
                ubicacion=ubicacion_bodega,
                producto_id__in=piso_map.keys(),
            ).values("producto_id", "cantidad_actual")
        }

    productos_qs = (
        Producto.objects
        .filter(id__in=piso_map.keys())
        .only(
            "id", "nombre", "precio_menudeo", "precio_mayoreo", "precio_docena",
            "foto_url", "codigo_barras", "categoria_id", "categoria_padre_id",
        )
        .prefetch_related("valores_atributo__atributo")
        .order_by("nombre")
    )

    productos_list = []
    for p in productos_qs:
        p.stock_piso   = piso_map.get(p.id, 0)
        p.stock_bodega = bodega_map.get(p.id, 0)
        p.atributos_json = json.dumps(
            {va.atributo.nombre: va.valor for va in p.valores_atributo.all()},
            cls=DjangoJSONEncoder,
        )
        productos_list.append(p)

    promociones_data = list(
        Promocion.objects.filter(activo=True).values(
            "id", "nombre", "tipo_condicion", "tipo_resultado",
            "categoria_disparadora_id", "monto_minimo",
            "producto_regalo_id", "categoria_regalo_id",
            "filtros_atributos", "filtros_disparador", "atributos_enlazados",
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

    es_dueno = empleado.rol == "dueño"

    sucursal_obj = Sucursal.objects.select_related("dueño_servicios__user").get(id=sucursal_id)
    dueno_servicios_id = sucursal_obj.dueño_servicios_id or ""

    duenos_json = "[]"
    if es_dueno:
        duenos = list(
            Empleado.objects.filter(rol="dueño")
            .select_related("user")
            .values("id", "user__first_name", "user__last_name", "user__username")
        )
        for d in duenos:
            nombre = f"{d['user__first_name']} {d['user__last_name']}".strip()
            d["nombre"] = nombre or d["user__username"]
        duenos_json = json.dumps(duenos, cls=DjangoJSONEncoder)

    return render(
        request,
        "ventas/pos.html",
        {
            "productos":          productos_list,
            "ubicacion_pos":      ubicacion_pos,
            "caja_nombre":        caja_nombre,
            "promociones_json":   json.dumps(promociones_data, cls=DjangoJSONEncoder),
            "ofertas_json":       json.dumps(ofertas_data,    cls=DjangoJSONEncoder),
            "es_dueno":           es_dueno,
            "duenos_json":        duenos_json,
            "dueno_servicios_id": dueno_servicios_id,
        },
    )


    
@login_required
@require_POST
def procesar_venta(request):

    # 0) Validar rol
    empleado = request.user.empleado

    if empleado.rol not in ["cajero", "dueno", "dueño"]:
        return JsonResponse({"status": "error", "message": "No tienes permiso"}, status=403)

    # Parsear JSON una sola vez al inicio — necesitamos idempotency_key antes
    # de cualquier otra cosa para reclamar la llave atómicamente.
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "JSON inválido."}, status=400)

    # ============================
    # IDEMPOTENCY: claim del token antes de tocar nada
    # ============================
    idem_key = data.get("idempotency_key")
    idem_obj = None
    if idem_key:
        idem_obj, cached = IdempotencyKey.claim(idem_key, "venta", empleado)
        if cached is not None:
            status = cached.pop("__status", 200)
            return JsonResponse(cached, status=status)

    def respond(payload, status=200):
        """Devuelve JSON, commitea/libera la llave idempotente según éxito."""
        if idem_obj:
            if payload.get("status") == "ok":
                idem_obj.commit(payload, status_code=status)
            else:
                idem_obj.release()
        return JsonResponse(payload, status=status)

    # Guard contra doble envío concurrente (defensa adicional al idempotency)
    lock_key = f"pos_lock_{empleado.id}"
    if cache.get(lock_key):
        return respond({"status": "error", "message": "Venta en proceso, espera un momento."}, status=409)
    cache.set(lock_key, True, timeout=15)

    try:
        # 1) Validar caja activa
        sucursal_id = request.session.get("sucursal_actual")
        caja_id = request.session.get("caja_actual")

        if not sucursal_id or not caja_id:
            return respond({"status": "error", "message": "Debes autenticarte en una caja."}, status=400)

        # 2) Obtener sucursal
        try:
            sucursal = Sucursal.objects.get(id=sucursal_id)
        except Sucursal.DoesNotExist:
            return respond({"status": "error", "message": "Sucursal inválida."}, status=400)

        # Verificar que la caja pertenece a esta sucursal
        from sucursales.models import Caja
        if not Caja.objects.filter(id=caja_id, sucursal_id=sucursal_id).exists():
            return respond({"status": "error", "message": "Caja no válida para esta sucursal."}, status=403)

        carrito = data.get("carrito", [])
        pagado_efectivo = data.get("pagado_efectivo")
        pagado_tarjeta = data.get("pagado_tarjeta")
        descuento_10 = data.get("descuento_10")

        # 4) Validación básica
        if not carrito:
            return respond({"status": "error", "message": "Carrito vacío."}, status=400)

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
                return respond({"status": "error", "message": "Error en item del carrito."}, status=400)

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

            return respond({
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
            return respond({"status": "error", "message": "Error al procesar la venta."}, status=400)

    finally:
        cache.delete(lock_key)


@login_required
@require_POST
def set_dueno_servicios(request):
    empleado = request.user.empleado
    if empleado.rol != "dueño":
        return JsonResponse({"status": "error", "message": "Solo los dueños pueden cambiar esto."}, status=403)

    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        return JsonResponse({"status": "error", "message": "Sin sucursal activa."}, status=400)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"status": "error", "message": "JSON inválido."}, status=400)

    dueno_id = data.get("dueno_id") or None

    try:
        sucursal = Sucursal.objects.get(id=sucursal_id)
    except Sucursal.DoesNotExist:
        return JsonResponse({"status": "error", "message": "Sucursal no encontrada."}, status=404)

    if dueno_id:
        try:
            nuevo_dueno = Empleado.objects.get(id=dueno_id, rol="dueño")
            sucursal.dueño_servicios = nuevo_dueno
        except Empleado.DoesNotExist:
            return JsonResponse({"status": "error", "message": "Dueño inválido."}, status=400)
    else:
        sucursal.dueño_servicios = None

    sucursal.save(update_fields=["dueño_servicios"])
    return JsonResponse({"status": "ok"})


@login_required
def stock_productos(request):
    """
    Devuelve el stock actualizado de todos los productos en la sucursal activa.
    Usado por el POS para refrescar las tarjetas sin recargar la página.
    """
    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        return JsonResponse({"error": "Sin sucursal"}, status=400)

    ubs = {
        ub["tipo"]: ub["id"]
        for ub in Ubicacion.objects.filter(
            sucursal_id=sucursal_id, tipo__in=["piso", "bodega"]
        ).values("id", "tipo")
    }
    piso_id   = ubs.get("piso")
    bodega_id = ubs.get("bodega")

    if not piso_id:
        return JsonResponse({})

    ub_ids = [x for x in [piso_id, bodega_id] if x]
    data = {}
    for inv in Inventario.objects.filter(ubicacion_id__in=ub_ids).values(
        "producto_id", "ubicacion_id", "cantidad_actual"
    ):
        pid = inv["producto_id"]
        if pid not in data:
            data[pid] = {"piso": 0, "bodega": 0}
        if inv["ubicacion_id"] == piso_id:
            data[pid]["piso"] = inv["cantidad_actual"]
        elif inv["ubicacion_id"] == bodega_id:
            data[pid]["bodega"] = inv["cantidad_actual"]

    return JsonResponse(data)


@login_required
def producto_card(request, producto_id):
    """
    Renderiza UNA card de producto para el Piso de la sucursal activa.
    El POS lo usa para insertar en vivo un producto que apareció en piso
    (nuevo, trasladado desde bodega, o restock de algo que se había agotado)
    sin recargar la página.

    Devuelve 204 si el producto no debe mostrarse (sin stock en piso o inactivo),
    lo que mantiene la misma regla que la carga inicial del POS.
    """
    # Mismo candado que pos_view: solo cajero/dueño operan el POS.
    empleado = getattr(request.user, "empleado", None)
    if empleado is None or empleado.rol not in ["cajero", "dueño"]:
        return HttpResponse(status=204)

    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        return HttpResponse(status=204)

    try:
        piso = Ubicacion.objects.get(sucursal_id=sucursal_id, tipo="piso")
    except Ubicacion.DoesNotExist:
        return HttpResponse(status=204)

    stock_piso = (
        Inventario.objects
        .filter(ubicacion=piso, producto_id=producto_id)
        .values_list("cantidad_actual", flat=True)
        .first()
    ) or 0

    # Misma regla que pos_view: solo se muestran productos con existencia en piso.
    if stock_piso <= 0:
        return HttpResponse(status=204)

    try:
        p = (
            Producto.objects
            .prefetch_related("valores_atributo__atributo")
            .get(id=producto_id, activo=True)
        )
    except Producto.DoesNotExist:
        return HttpResponse(status=204)

    ubicacion_bodega = Ubicacion.objects.filter(
        sucursal_id=sucursal_id, tipo="bodega"
    ).first()
    stock_bodega = 0
    if ubicacion_bodega:
        stock_bodega = (
            Inventario.objects
            .filter(ubicacion=ubicacion_bodega, producto_id=producto_id)
            .values_list("cantidad_actual", flat=True)
            .first()
        ) or 0

    p.stock_piso = stock_piso
    p.stock_bodega = stock_bodega
    p.atributos_json = json.dumps(
        {va.atributo.nombre: va.valor for va in p.valores_atributo.all()},
        cls=DjangoJSONEncoder,
    )

    return render(request, "ventas/_producto_card.html", {"p": p})
