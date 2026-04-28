from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from inventario.models import Categoria, Producto
from ventas.models import Oferta


def _es_dueno(user):
    es_empleado = hasattr(user, "empleado")
    return user.is_superuser or (es_empleado and user.empleado.rol == "dueño")


def _categorias_agrupadas():
    padres = Categoria.objects.filter(padre__isnull=True).order_by("nombre")
    subs   = Categoria.objects.filter(padre__isnull=False).order_by("padre__nombre", "nombre")
    return padres, subs


@login_required
def modal_oferta_view(request, oferta_id=None):
    if not _es_dueno(request.user):
        raise PermissionDenied

    oferta       = Oferta.objects.filter(id=oferta_id).select_related("producto").first() if oferta_id else None
    padres, subs = _categorias_agrupadas()

    html = render_to_string("ventas/oferta_form.html", {
        "oferta":        oferta,
        "padres":        padres,
        "subcategorias": subs,
    }, request=request)

    return JsonResponse({"html": html})


@login_required
def buscar_producto_view(request):
    q = request.GET.get("q", "").strip()
    if len(q) < 2:
        return JsonResponse([], safe=False)
    productos = Producto.objects.filter(activo=True, nombre__icontains=q).order_by("nombre")[:15]
    return JsonResponse([{"id": p.id, "nombre": p.nombre} for p in productos], safe=False)


@login_required
def guardar_oferta_view(request, oferta_id=None):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    oferta = Oferta.objects.filter(id=oferta_id).first() if oferta_id else None

    nombre     = request.POST.get("nombre", "").strip()
    aplica_a   = request.POST.get("aplica_a", "")
    tipo       = request.POST.get("tipo", "")
    valor      = request.POST.get("valor") or None
    cantidad_n = request.POST.get("cantidad_n") or None
    prod_id    = request.POST.get("producto") or None
    cat_id     = request.POST.get("categoria") or None
    fecha_ini  = request.POST.get("fecha_inicio") or None
    fecha_fin  = request.POST.get("fecha_fin") or None
    descripcion = request.POST.get("descripcion", "").strip()

    if not nombre:
        return JsonResponse({"ok": False, "msg": "El nombre es obligatorio."})
    if aplica_a not in ("producto", "categoria"):
        return JsonResponse({"ok": False, "msg": "Elige a qué aplica la oferta."})
    if tipo not in ("porcentaje", "fijo", "2x1", "nxprecio"):
        return JsonResponse({"ok": False, "msg": "Elige el tipo de descuento."})
    if aplica_a == "producto" and not prod_id:
        return JsonResponse({"ok": False, "msg": "Selecciona el producto."})
    if aplica_a == "categoria" and not cat_id:
        return JsonResponse({"ok": False, "msg": "Selecciona la categoría."})
    if tipo in ("porcentaje", "fijo", "nxprecio") and not valor:
        return JsonResponse({"ok": False, "msg": "Escribe el valor del descuento."})
    if tipo == "nxprecio" and not cantidad_n:
        return JsonResponse({"ok": False, "msg": "Escribe cuántas piezas entran en el precio especial."})

    filtros_nombres = request.POST.getlist("filtro_nombre[]")
    filtros_valores = request.POST.getlist("filtro_valor[]")
    filtros_atributos = [
        {"nombre": n, "valor": v}
        for n, v in zip(filtros_nombres, filtros_valores)
        if n and v
    ]

    if not oferta:
        oferta = Oferta()

    oferta.nombre      = nombre
    oferta.descripcion = descripcion
    oferta.aplica_a    = aplica_a
    oferta.tipo        = tipo
    oferta.valor       = valor
    oferta.cantidad_n  = cantidad_n if tipo == "nxprecio" else None
    oferta.producto    = Producto.objects.filter(id=prod_id).first()
    oferta.categoria   = Categoria.objects.filter(id=cat_id).first()
    oferta.filtros_atributos = filtros_atributos if aplica_a == "categoria" else []
    oferta.fecha_inicio = fecha_ini or None
    oferta.fecha_fin    = fecha_fin or None

    if aplica_a == "producto":
        oferta.categoria = None
    else:
        oferta.producto = None

    if tipo == "2x1":
        oferta.valor = None

    oferta.save()
    return JsonResponse({"ok": True, "msg": "Oferta guardada."})


@login_required
def toggle_oferta_view(request, oferta_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    oferta        = get_object_or_404(Oferta, id=oferta_id)
    oferta.activo = not oferta.activo
    oferta.save()
    return JsonResponse({"ok": True, "activo": oferta.activo})


@login_required
def eliminar_oferta_view(request, oferta_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    oferta = get_object_or_404(Oferta, id=oferta_id)
    oferta.delete()
    return JsonResponse({"ok": True, "msg": "Oferta eliminada."})
