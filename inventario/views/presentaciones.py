"""
Precios por cantidad (Media docena, Decena, Caja): Lista de precios y las
llamadas que usan el alta y el detalle del producto. Solo dueñas.

Vistas delgadas: las reglas están en inventario/services/presentacion_service.py.
"""
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from inventario.models import Producto, ValorAtributo
from inventario.services import presentacion_service
from inventario.templatetags.cloudinary_helpers import foto_mini
from ventas.models import IdempotencyKey

MAX_RESULTADOS = 20


def _empleado_duena(request):
    empleado = getattr(request.user, "empleado", None)
    return empleado if presentacion_service.puede_editar(empleado) else None


def _sin_permiso():
    return JsonResponse(
        {"success": False, "errors": ["Solo las dueñas pueden cambiar estos precios."]}, status=403
    )


def _productos_con_datos():
    return (
        Producto.objects
        .filter(activo=True)
        .prefetch_related(
            "presentaciones",
            Prefetch("valores_atributo", queryset=ValorAtributo.objects.select_related("atributo")),
        )
    )


def _producto_json(producto):
    detalle = " · ".join(
        v.valor for v in producto.valores_atributo.all()
        if v.valor and v.valor.strip().upper() != "N/A"
    )
    return {
        "producto_id": producto.id,
        "nombre": producto.nombre,
        "detalle": detalle,
        "codigo_barras": producto.codigo_barras or "",
        "foto_url": foto_mini(producto.foto_url) or "",
        "precio_menudeo": str(producto.precio_menudeo),
        "precio_mayoreo": str(producto.precio_mayoreo),
        "precio_docena": str(producto.precio_docena) if producto.precio_docena is not None else "",
        "presentaciones": presentacion_service.de_producto(producto),
    }


@login_required
def lista_precios(request):
    """Pantalla de la Lista de precios: escanear, poner precios y guardar todo junto."""
    if _empleado_duena(request) is None:
        messages.error(request, "Solo las dueñas pueden entrar a la Lista de precios.")
        return redirect("tienda_temp:landing")
    return render(request, "inventario/lista_precios.html", {
        "piezas_minimas_caja": presentacion_service.PIEZAS_MINIMAS_CAJA,
    })


@login_required
@require_GET
def buscar_producto(request):
    """
    Productos con sus precios para la Lista, para copiar en el alta y para
    el detalle. `q` es un código escaneado (varias variantes pueden compartir
    código) o parte del nombre.
    """
    if _empleado_duena(request) is None:
        return _sin_permiso()

    q = (request.GET.get("q") or "").strip()
    if not q:
        return JsonResponse({"success": True, "productos": []})

    codigos = [q]
    if q.isdigit():
        if len(q) == 12:
            codigos.append("0" + q)
        elif len(q) == 13 and q.startswith("0"):
            codigos.append(q[1:])

    base = _productos_con_datos()
    productos = list(base.filter(codigo_barras__in=codigos).order_by("nombre", "id")[:MAX_RESULTADOS])
    por_codigo = bool(productos)
    if not productos:
        productos = list(
            base.filter(Q(nombre__icontains=q) | Q(codigo_barras__icontains=q))
            .order_by("nombre", "id")[:MAX_RESULTADOS]
        )
    return JsonResponse({
        "success": True,
        "por_codigo": por_codigo,   # True: escaneó un código exacto (no buscó por nombre)
        "productos": [_producto_json(p) for p in productos],
    })


@login_required
@require_GET
def ultimo_registrado(request):
    """Para "Usar los del último que registraste" en el alta."""
    empleado = _empleado_duena(request)
    if empleado is None:
        return _sin_permiso()
    producto = presentacion_service.ultimo_registrado_por(empleado)
    return JsonResponse({
        "success": True,
        "producto": {
            "producto_id": producto.id,
            "nombre": producto.nombre,
            "presentaciones": presentacion_service.de_producto(producto),
        } if producto else None,
    })


@login_required
@require_POST
def guardar_lista(request):
    """
    Guarda la Lista de precios (o la tarjeta del detalle, que es una lista de
    un producto) todo o nada.
    Body: {renglones: [{producto_id, originales: [...], presentaciones: [...]}], idempotency_key}
    """
    empleado = _empleado_duena(request)
    if empleado is None:
        return _sin_permiso()

    try:
        data = json.loads(request.body)
    except ValueError:
        return JsonResponse({"success": False, "errors": ["La lista llegó mal. Recarga la página."]},
                            status=400)

    idem_obj = None
    idem_key = data.get("idempotency_key")
    if idem_key:
        idem_obj, cached = IdempotencyKey.claim(idem_key, "lista_precios", empleado)
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

    try:
        resumen = presentacion_service.guardar_lista(data.get("renglones"))
    except presentacion_service.ListaConErrores as e:
        return respond({
            "success": False,
            "errors": ["No se guardó nada. Revisa los productos marcados en rojo."],
            "por_producto": {str(k): v for k, v in e.errores.items()},
        }, status=400)
    except ValidationError as e:
        return respond({"success": False, "errors": e.messages}, status=400)

    productos = _productos_con_datos().filter(
        id__in=[r.get("producto_id") for r in data["renglones"] if isinstance(r, dict)]
    )
    return respond({
        "success": True,
        "resumen": resumen,
        "productos": [_producto_json(p) for p in productos],
    })
