import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from inventario.models import Producto, Ubicacion
from inventario.services.inventario_service import InventarioService
from ventas.models import IdempotencyKey


def _ubicaciones_de_sesion(request):
    """Resuelve (piso, bodega) de la sucursal activa en sesión, o (None, None)."""
    sucursal_id = request.session.get("sucursal_actual")
    if not sucursal_id:
        return None, None
    piso = Ubicacion.objects.filter(sucursal_id=sucursal_id, tipo="piso").first()
    bodega = Ubicacion.objects.filter(sucursal_id=sucursal_id, tipo="bodega").first()
    return piso, bodega


@login_required
def orden_reabastecimiento(request):
    """
    Pantalla móvil para armar la orden de reabastecimiento:
    escanear en piso → recolectar en bodega → confirmar → transferencia múltiple.
    Solo empleados (cualquier rol). Los clientes no tienen acceso.
    """
    empleado = getattr(request.user, "empleado", None)
    if empleado is None:
        messages.error(request, "Solo los empleados pueden usar el reabastecimiento.")
        return redirect("tienda_temp:landing")

    piso, bodega = _ubicaciones_de_sesion(request)
    if piso is None or bodega is None:
        messages.error(
            request,
            "Necesitas una sucursal activa con Piso y Bodega interna configurados.",
        )
        return redirect("inventario:dashboard_inventario")

    return render(request, "inventario/orden_reabastecimiento.html", {
        "piso":     piso,
        "bodega":   bodega,
        "sucursal": piso.sucursal,
    })


@login_required
@require_POST
def confirmar_orden_reabastecimiento(request):
    """
    Ejecuta la orden completa: por renglón hace el ajuste positivo automático
    si trae más de lo registrado, la transferencia bodega→piso, y el ajuste a 0
    si el empleado marcó "ya no quedó nada". Responde resultado POR RENGLÓN.

    Body JSON: {renglones: [{producto_id, cantidad, vaciar_bodega}], idempotency_key}
    """
    empleado = getattr(request.user, "empleado", None)
    if empleado is None:
        return JsonResponse(
            {"success": False, "errors": ["Solo los empleados pueden reabastecer."]},
            status=403,
        )

    piso, bodega = _ubicaciones_de_sesion(request)
    if piso is None or bodega is None:
        return JsonResponse(
            {"success": False, "errors": ["Sin sucursal activa con Piso y Bodega interna."]},
            status=400,
        )

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"success": False, "errors": ["JSON inválido."]}, status=400)

    renglones_raw = data.get("renglones") or []
    if not renglones_raw:
        return JsonResponse({"success": False, "errors": ["La orden está vacía."]}, status=400)

    # Idempotencia: reintentos (doble tap, red móvil inestable) no duplican la orden.
    idem_obj = None
    idem_key = data.get("idempotency_key")
    if idem_key:
        idem_obj, cached = IdempotencyKey.claim(idem_key, "orden_reabastecimiento", empleado)
        if cached is not None:
            status = cached.pop("__status", 200)
            return JsonResponse(cached, status=status)

    def respond(payload, status=200):
        if idem_obj:
            if payload.get("success"):
                idem_obj.commit(payload, status_code=status)
            else:
                idem_obj.release()
        return JsonResponse(payload, status=status)

    # Armar renglones válidos; los inválidos se reportan como fallidos, no abortan.
    renglones = []
    fallidos = []
    for item in renglones_raw:
        try:
            producto_id = int(item.get("producto_id"))
            cantidad = int(item.get("cantidad"))
            vaciar = bool(item.get("vaciar_bodega", False))
            producto = Producto.objects.get(id=producto_id, activo=True)
            renglones.append({
                "producto": producto,
                "cantidad": cantidad,
                "vaciar_origen": vaciar,
            })
        except Producto.DoesNotExist:
            fallidos.append({
                "producto_id": item.get("producto_id"),
                "nombre": "",
                "ok": False,
                "error": "Producto no encontrado o inactivo.",
            })
        except Exception:
            fallidos.append({
                "producto_id": item.get("producto_id"),
                "nombre": "",
                "ok": False,
                "error": "Renglón inválido.",
            })

    resultados = InventarioService.orden_reabastecimiento(
        origen=bodega,
        destino=piso,
        renglones=renglones,
        empleado=empleado,
    ) + fallidos

    exitosos = sum(1 for r in resultados if r.get("ok"))

    return respond({
        "success": True,
        "total": len(resultados),
        "exitosos": exitosos,
        "resultados": resultados,
    })
