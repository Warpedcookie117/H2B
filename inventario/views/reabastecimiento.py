import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from inventario.models import Producto, Ubicacion
from inventario.services.inventario_service import InventarioService
from ventas.models import IdempotencyKey


def _piso_y_bodega_de(sucursal):
    """Resuelve (piso, bodega) de una sucursal, o (None, None) si falta alguna."""
    if sucursal is None:
        return None, None
    piso = Ubicacion.objects.filter(sucursal=sucursal, tipo="piso").first()
    bodega = Ubicacion.objects.filter(sucursal=sucursal, tipo="bodega").first()
    return piso, bodega


@login_required
def orden_reabastecimiento(request, ubicacion_id):
    """
    Pantalla móvil para armar la orden de reabastecimiento:
    escanear en piso → recolectar en bodega → confirmar → transferencia múltiple.
    Solo empleados (cualquier rol). Los clientes no tienen acceso.

    La sucursal se resuelve desde `ubicacion_id` (la card de piso/bodega desde la
    que se dio clic), igual que el resto de vistas de inventario_ubicacion —
    NO depende de session["sucursal_actual"], que solo se llena al entrar a una
    caja del POS y puede estar vacía si se llega por el sidebar.
    """
    empleado = getattr(request.user, "empleado", None)
    if empleado is None:
        messages.error(request, "Solo los empleados pueden usar el reabastecimiento.")
        return redirect("tienda_temp:landing")

    ubicacion_actual = get_object_or_404(Ubicacion, id=ubicacion_id)
    piso, bodega = _piso_y_bodega_de(ubicacion_actual.sucursal)
    if piso is None or bodega is None:
        messages.error(
            request,
            "Esta sucursal necesita Piso y Bodega interna configurados.",
        )
        return redirect("inventario:productos_por_ubicacion", ubicacion_id=ubicacion_id)

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

    Body JSON: {piso_id, bodega_id, renglones: [{producto_id, cantidad, vaciar_bodega}],
                idempotency_key}

    piso_id/bodega_id vienen del contexto que la propia página resolvió al cargar
    (no de session) — aquí solo se re-validan como defensa (mismo tipo, misma
    sucursal), no se re-derivan a ciegas.
    """
    empleado = getattr(request.user, "empleado", None)
    if empleado is None:
        return JsonResponse(
            {"success": False, "errors": ["Solo los empleados pueden reabastecer."]},
            status=403,
        )

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"success": False, "errors": ["JSON inválido."]}, status=400)

    piso = Ubicacion.objects.filter(id=data.get("piso_id"), tipo="piso").first()
    bodega = Ubicacion.objects.filter(id=data.get("bodega_id"), tipo="bodega").first()
    if not piso or not bodega or piso.sucursal_id != bodega.sucursal_id:
        return JsonResponse(
            {"success": False, "errors": ["Piso/Bodega inválidos para esta sucursal."]},
            status=400,
        )

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
