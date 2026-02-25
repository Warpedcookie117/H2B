##Vista que maneja el acceso y registro de categorias de los PRODUCTOS

from django.http import JsonResponse
from django.template.loader import render_to_string
from inventario.forms import AtributoForm, CategoriaPadreForm, SubcategoriaForm
from inventario.models import Atributo, Categoria
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


@login_required
def categoria_view(request):
    user = request.user

    es_empleado = hasattr(user, "empleado")
    es_dueno = user.is_superuser or (es_empleado and user.empleado.rol == "dueño")

    if not (es_dueno or es_empleado):
        raise PermissionDenied("No tienes permiso para ver esta página.")

    # 🔥 Categorías padre
    categorias_padre = Categoria.objects.filter(padre__isnull=True).order_by("nombre")

    # 🔥 Subcategorías (solo para mostrar)
    subcategorias = Categoria.objects.filter(padre__isnull=False).order_by("padre__nombre", "nombre")

    # 🔥 Ya NO procesamos POST aquí
    # Todo el CRUD se hace por AJAX en modales

    return render(request, "inventario/categorias.html", {
        "categorias_padre": categorias_padre,
        "subcategorias": subcategorias,
        "solo_lectura": not es_dueno,
    })
    
@login_required
def modal_categoria_view(request, categoria_id=None):
    categoria = Categoria.objects.filter(id=categoria_id, padre__isnull=True).first()
    form = CategoriaPadreForm(instance=categoria)

    return render(request, "inventario/categoria_form.html", {
        "form": form,
        "categoria": categoria,
    })

@login_required
def guardar_categoria_view(request, categoria_id=None):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})

    categoria = Categoria.objects.filter(id=categoria_id, padre__isnull=True).first()

    form = CategoriaPadreForm(request.POST, instance=categoria)

    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True, "msg": "Categoría guardada correctamente."})

    return JsonResponse({"ok": False, "msg": "Error en el formulario."})


@login_required
def eliminar_categoria_view(request, categoria_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})

    categoria = get_object_or_404(Categoria, id=categoria_id, padre__isnull=True)

    if categoria.subcategorias.exists():
        return JsonResponse({"ok": False, "msg": "No puedes eliminar una categoría con subcategorías."})

    categoria.delete()
    return JsonResponse({"ok": True, "msg": "Categoría eliminada correctamente."})


@login_required
def modal_subcategoria_view(request, padre_id, sub_id=None):
    padre = get_object_or_404(Categoria, id=padre_id, padre__isnull=True)

    subcategoria = Categoria.objects.filter(id=sub_id, padre=padre).first()

    form = SubcategoriaForm(
        instance=subcategoria,
        padre=padre
    )

    return render(request, "inventario/subcategoria_form.html", {
        "form": form,
        "padre": padre,
        "subcategoria": subcategoria,
    })
    
@login_required
def guardar_subcategoria_view(request, padre_id, sub_id=None):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})

    padre = get_object_or_404(Categoria, id=padre_id, padre__isnull=True)

    subcategoria = Categoria.objects.filter(id=sub_id, padre=padre).first()

    form = SubcategoriaForm(
        request.POST,
        instance=subcategoria,
        padre=padre
    )

    if form.is_valid():
        form.save()
        return JsonResponse({"ok": True, "msg": "Subcategoría guardada correctamente."})

    return JsonResponse({"ok": False, "msg": "Error en el formulario."})


@login_required
def eliminar_subcategoria_view(request, sub_id):
    if request.method != "POST":
        return JsonResponse({"ok": False, "msg": "Método no permitido"})

    sub = get_object_or_404(Categoria, id=sub_id, padre__isnull=False)

    sub.delete()
    return JsonResponse({"ok": True, "msg": "Subcategoría eliminada correctamente."})

    
    
    

#Vista que ya no funciona, replicar el funcionamiento de nuevo_producto
@login_required
def api_categorias(request):
    """
    Devuelve:
    - categorias_padre: lista de categorías raíz con sus subcategorías
      [{id, nombre, subcategorias:[{id,nombre}]}]
    """
    # Categorías padre
    padres = Categoria.objects.filter(padre__isnull=True).order_by('nombre')

    # Subcategorías
    subqs = Categoria.objects.filter(padre__isnull=False).order_by('nombre')
    subs_por_padre = {}
    for s in subqs:
        subs_por_padre.setdefault(s.padre_id, []).append({
            'id': s.id,
            'nombre': s.nombre
        })

    categorias_data = []
    for p in padres:
        categorias_data.append({
            'id': p.id,
            'nombre': p.nombre,
            'subcategorias': subs_por_padre.get(p.id, [])
        })

    return JsonResponse({'categorias_padre': categorias_data})

@login_required
def configurar_atributos(request):
    user = request.user

    es_empleado = hasattr(user, "empleado")
    es_dueno = user.is_superuser or (es_empleado and user.empleado.rol == "dueño")

    if not (es_dueno or es_empleado):
        raise PermissionDenied("No tienes permiso para ver esta página.")

    # Todas las categorías padre
    categorias_padre = Categoria.objects.filter(padre__isnull=True).order_by("nombre")

    # Todas las subcategorías con sus atributos
    subcategorias = Categoria.objects.filter(padre__isnull=False).order_by("padre__nombre", "nombre")

    # Si el dueño está editando o creando un atributo
    edit_id = request.GET.get("editar")
    subcat_id = request.GET.get("subcategoria")

    form = None
    subcategoria = None

    if subcat_id:
        subcategoria = get_object_or_404(Categoria, id=subcat_id)

        if edit_id and es_dueno:
            atributo = get_object_or_404(Atributo, id=edit_id, categoria=subcategoria)
            form = AtributoForm(instance=atributo)
        elif es_dueno:
            form = AtributoForm()

    # POST: crear o editar atributo
    if request.method == "POST":
        if not es_dueno:
            raise PermissionDenied("No tienes permiso para modificar atributos.")

        subcat_id = request.POST.get("subcategoria_id")
        subcategoria = get_object_or_404(Categoria, id=subcat_id)

        atributo_id = request.POST.get("atributo_id")

        if atributo_id:
            atributo = get_object_or_404(Atributo, id=atributo_id, categoria=subcategoria)
            form = AtributoForm(request.POST, instance=atributo)
        else:
            form = AtributoForm(request.POST)

        if form.is_valid():
            nuevo = form.save(commit=False)
            nuevo.categoria = subcategoria
            nuevo.save()

            messages.success(request, "Atributo guardado correctamente.")
            return redirect("inventario:configurar_atributos")

    return render(request, "inventario/atributos.html", {
        "categorias_padre": categorias_padre,
        "subcategorias": subcategorias,
        "form": form,
        "subcategoria": subcategoria,
        "solo_lectura": not es_dueno,
        "edit_id": edit_id,
    })
    
    
    
@login_required
def nuevo_atributo(request, subcat_id, atributo_id=None):
    subcategoria = get_object_or_404(Categoria, id=subcat_id)

    es_empleado = hasattr(request.user, "empleado")
    es_dueno = request.user.is_superuser or (es_empleado and request.user.empleado.rol == "dueño")

    if not es_dueno:
        raise PermissionDenied("No tienes permiso para modificar atributos.")

    atributo = None
    if atributo_id:
        atributo = get_object_or_404(Atributo, id=atributo_id, categoria=subcategoria)

    # GET → devolver HTML del formulario
    if request.method == "GET":
        form = AtributoForm(instance=atributo)
        html = render_to_string(
            "inventario/atributo_form.html",
            {
                "form": form,
                "subcategoria": subcategoria,
                "atributo": atributo,
            },
            request=request
        )
        return JsonResponse({"html": html})

    # POST → guardar
    form = AtributoForm(request.POST, instance=atributo)
    if form.is_valid():
        nuevo = form.save(commit=False)
        nuevo.categoria = subcategoria
        nuevo.save()

        # Devolver SOLO los atributos en JSON
        atributos = list(
            subcategoria.atributos.values("id", "nombre", "tipo")
        )

        return JsonResponse({
            "success": True,
            "atributos": atributos
        })

    # Si hay errores → devolver formulario con errores
    html = render_to_string(
        "inventario/atributo_form.html",
        {
            "form": form,
            "subcategoria": subcategoria,
            "atributo": atributo,
        },
        request=request
    )

    return JsonResponse({"success": False, "html": html})

@login_required
def eliminar_atributo(request, subcat_id, atributo_id):
    subcategoria = get_object_or_404(Categoria, id=subcat_id)

    es_empleado = hasattr(request.user, "empleado")
    es_dueno = request.user.is_superuser or (es_empleado and request.user.empleado.rol == "dueño")

    if not es_dueno:
        raise PermissionDenied("No tienes permiso para eliminar atributos.")

    atributo = get_object_or_404(Atributo, id=atributo_id, categoria=subcategoria)
    atributo.delete()

    # Devolver lista actualizada
    atributos = list(subcategoria.atributos.values("id", "nombre", "tipo"))

    return JsonResponse({
        "success": True,
        "atributos": atributos
    })
    
    
