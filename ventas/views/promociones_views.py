from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum, Case, When, IntegerField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string

from inventario.models import Atributo, Categoria, Producto, ValorAtributo
from ventas.models import Oferta, Promocion


def _es_dueno(user):
    es_empleado = hasattr(user, "empleado")
    return user.is_superuser or (es_empleado and user.empleado.rol == "dueño")


def _categorias_agrupadas():
    padres = Categoria.objects.filter(padre__isnull=True).order_by("nombre")
    subs   = Categoria.objects.filter(padre__isnull=False).order_by("padre__nombre", "nombre")
    return padres, subs


@login_required
def promociones_view(request):
    user = request.user
    if not (user.is_superuser or hasattr(user, "empleado")):
        raise PermissionDenied

    promociones  = Promocion.objects.select_related(
        "categoria_disparadora", "producto_regalo", "categoria_regalo"
    ).all()
    ofertas      = Oferta.objects.select_related("producto", "categoria").all()
    padres, subs = _categorias_agrupadas()
    productos    = Producto.objects.filter(activo=True).order_by("nombre")

    return render(request, "ventas/promociones.html", {
        "promociones":    promociones,
        "ofertas":        ofertas,
        "padres":         padres,
        "subcategorias":  subs,
        "productos":      productos,
        "solo_lectura":   not _es_dueno(user),
    })


@login_required
def modal_promocion_view(request, promocion_id=None):
    if not _es_dueno(request.user):
        raise PermissionDenied

    promocion    = Promocion.objects.filter(id=promocion_id).first() if promocion_id else None
    padres, subs = _categorias_agrupadas()
    productos    = Producto.objects.filter(activo=True).order_by("nombre")

    html = render_to_string("ventas/promocion_form.html", {
        "promocion":     promocion,
        "padres":        padres,
        "subcategorias": subs,
        "productos":     productos,
    }, request=request)

    return JsonResponse({"html": html})


@login_required
def guardar_promocion_view(request, promocion_id=None):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    promocion = Promocion.objects.filter(id=promocion_id).first() if promocion_id else None

    nombre           = request.POST.get("nombre", "").strip()
    descripcion      = request.POST.get("descripcion", "").strip()
    tipo_condicion   = request.POST.get("tipo_condicion", "")
    tipo_resultado   = request.POST.get("tipo_resultado", "")
    cat_disp_id      = request.POST.get("categoria_disparadora") or None
    monto_minimo     = request.POST.get("monto_minimo") or None
    prod_regalo_id   = request.POST.get("producto_regalo") or None
    cat_regalo_id    = request.POST.get("categoria_regalo") or None

    if not nombre:
        return JsonResponse({"ok": False, "msg": "El nombre es obligatorio."})
    if tipo_condicion not in ("categoria", "monto", "monto_categoria"):
        return JsonResponse({"ok": False, "msg": "Elige qué dispara la promoción."})
    if tipo_resultado not in ("regalo_fijo", "regalo_variante"):
        return JsonResponse({"ok": False, "msg": "Elige qué regala la promoción."})

    if tipo_condicion == "categoria" and not cat_disp_id:
        return JsonResponse({"ok": False, "msg": "Selecciona la categoría que dispara la promoción."})
    if tipo_condicion == "monto" and not monto_minimo:
        return JsonResponse({"ok": False, "msg": "Escribe el monto mínimo."})
    if tipo_condicion == "monto_categoria":
        if not cat_disp_id:
            return JsonResponse({"ok": False, "msg": "Selecciona la categoría."})
        if not monto_minimo:
            return JsonResponse({"ok": False, "msg": "Escribe el monto mínimo."})

    if tipo_resultado == "regalo_fijo" and not prod_regalo_id:
        return JsonResponse({"ok": False, "msg": "Selecciona el producto de regalo."})
    if tipo_resultado == "regalo_variante" and not cat_regalo_id:
        return JsonResponse({"ok": False, "msg": "Selecciona la categoría del regalo."})

    if not promocion:
        promocion = Promocion()

    promocion.nombre              = nombre
    promocion.descripcion         = descripcion
    promocion.tipo_condicion      = tipo_condicion
    promocion.tipo_resultado      = tipo_resultado
    promocion.categoria_disparadora = Categoria.objects.filter(id=cat_disp_id).first()
    promocion.monto_minimo        = monto_minimo
    promocion.producto_regalo     = Producto.objects.filter(id=prod_regalo_id).first()
    promocion.categoria_regalo    = Categoria.objects.filter(id=cat_regalo_id).first()

    # Limpiar campos que no aplican
    if tipo_condicion == "categoria":
        promocion.monto_minimo = None
    elif tipo_condicion == "monto":
        promocion.categoria_disparadora = None
    # monto_categoria conserva ambos campos

    filtros_nombres = request.POST.getlist("filtro_nombre[]")
    filtros_valores = request.POST.getlist("filtro_valor[]")
    filtros_atributos = [
        {"nombre": n, "valor": v}
        for n, v in zip(filtros_nombres, filtros_valores)
        if n and v
    ]

    if tipo_resultado == "regalo_fijo":
        promocion.categoria_regalo  = None
        promocion.filtros_atributos = []
    else:
        promocion.producto_regalo = None
        if tipo_condicion == "monto_categoria":
            promocion.categoria_regalo  = promocion.categoria_disparadora
            promocion.filtros_atributos = []
        else:
            promocion.filtros_atributos = filtros_atributos

    promocion.save()
    return JsonResponse({"ok": True, "msg": "Promoción guardada."})


@login_required
def toggle_promocion_view(request, promocion_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    promocion        = get_object_or_404(Promocion, id=promocion_id)
    promocion.activo = not promocion.activo
    promocion.save()
    return JsonResponse({"ok": True, "activo": promocion.activo})


@login_required
def eliminar_promocion_view(request, promocion_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})
    if not _es_dueno(request.user):
        raise PermissionDenied

    promocion = get_object_or_404(Promocion, id=promocion_id)
    promocion.delete()
    return JsonResponse({"ok": True, "msg": "Promoción eliminada."})


@login_required
def atributos_categoria_view(request, categoria_id):
    atributos = Atributo.objects.filter(categoria_id=categoria_id).order_by("nombre")
    result = []
    for atr in atributos:
        valores = list(
            ValorAtributo.objects.filter(atributo=atr)
            .values_list("valor", flat=True)
            .distinct()
            .order_by("valor")
        )
        result.append({"nombre": atr.nombre, "valores": valores})
    return JsonResponse({"atributos": result})


@login_required
def productos_regalo_view(request, promo_id):
    promo = get_object_or_404(Promocion, id=promo_id, activo=True)
    sucursal_id = request.session.get("sucursal_actual")
    cat = promo.categoria_regalo

    # Incluye productos de la categoría directa y de sus subcategorías
    productos_qs = Producto.objects.filter(
        Q(categoria=cat) | Q(categoria__padre=cat),
        activo=True,
    )

    for f in (promo.filtros_atributos or []):
        nombre_f = f.get("nombre", "")
        valor_f  = f.get("valor", "")
        if not nombre_f or not valor_f:
            continue
        ids = ValorAtributo.objects.filter(
            atributo__nombre__iexact=nombre_f,
            valor__iexact=valor_f,
        ).filter(
            Q(atributo__categoria=cat) | Q(atributo__categoria__padre=cat)
        ).values_list("producto_id", flat=True)
        productos_qs = productos_qs.filter(id__in=ids)

    if sucursal_id:
        productos_qs = productos_qs.annotate(
            stock_piso=Coalesce(
                Sum(
                    Case(
                        When(
                            inventarios__ubicacion__tipo="piso",
                            inventarios__ubicacion__sucursal_id=sucursal_id,
                            then="inventarios__cantidad_actual",
                        ),
                        output_field=IntegerField(),
                    )
                ),
                0,
            )
        )

    result = []
    for p in productos_qs.order_by("nombre"):
        valores = ValorAtributo.objects.filter(
            producto=p,
            atributo__categoria=promo.categoria_regalo,
        ).select_related("atributo").order_by("atributo__nombre")
        atributos = {va.atributo.nombre: va.valor for va in valores}
        result.append({
            "id":        p.id,
            "nombre":    p.nombre,
            "stock":     getattr(p, "stock_piso", None),
            "atributos": atributos,
        })

    return JsonResponse({
        "promo_nombre": promo.nombre,
        "tipo_resultado": promo.tipo_resultado,
        "productos": result,
    })
