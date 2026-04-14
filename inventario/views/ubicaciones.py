from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError

from inventario.models import Ubicacion
from inventario.forms import UbicacionForm
from inventario.services.ubicaciones_service import UbicacionService
from sucursales.models import Sucursal


# ============================================================
# LISTA DE UBICACIONES — todos los roles pueden ver
# ============================================================

@login_required
def ubicaciones(request):

    # Almacenes globales (sin sucursal)
    almacenes_globales = (
        Ubicacion.objects
        .filter(sucursal__isnull=True)
        .order_by("nombre")
    )

    # Ubicaciones agrupadas por sucursal
    sucursales = Sucursal.objects.prefetch_related("ubicaciones").order_by("nombre")

    grupos_sucursal = []
    for sucursal in sucursales:
        ubicaciones_sucursal = sucursal.ubicaciones.order_by("tipo", "nombre")
        grupos_sucursal.append({
            "sucursal": sucursal,
            "ubicaciones": ubicaciones_sucursal,
        })

    return render(request, "inventario/ubicaciones.html", {
        "almacenes_globales": almacenes_globales,
        "grupos_sucursal": grupos_sucursal,
        "es_dueno": request.user.empleado.rol == "dueño",
    })


# ============================================================
# NUEVA UBICACIÓN — solo dueño
# ============================================================

@login_required
def ubicacion_nueva(request):
    if request.user.empleado.rol != "dueño":
        return JsonResponse({"success": False, "error": "Sin permiso."}, status=403)

    if request.method == "POST":
        form = UbicacionForm(request.POST)

        if form.is_valid():
            try:
                nueva = UbicacionService.crear(
                    nombre=form.cleaned_data["nombre"],
                    tipo="global",
                    sucursal=None,
                    direccion=form.cleaned_data["direccion"]
                )

                ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
                return JsonResponse({
                    "success": True,
                    "ubicaciones": ubicaciones,
                    "id": nueva.id
                })

            except ValidationError as e:
                form.add_error(None, e.message)

        html = render_to_string("inventario/ubicacion_form.html", {"form": form}, request=request)
        return JsonResponse({"success": False, "html": html})

    form = UbicacionForm()
    html = render_to_string("inventario/ubicacion_form.html", {"form": form}, request=request)
    return JsonResponse({"html": html})


# ============================================================
# EDITAR UBICACIÓN — solo dueño
# ============================================================

@login_required
def editar_ubicacion(request, ubicacion_id):
    if request.user.empleado.rol != "dueño":
        return JsonResponse({"success": False, "error": "Sin permiso."}, status=403)

    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    if request.method == "POST":
        form = UbicacionForm(request.POST, instance=ubicacion)

        if form.is_valid():
            try:
                ubicacion.nombre = form.cleaned_data["nombre"]
                ubicacion.direccion = form.cleaned_data["direccion"]
                ubicacion.tipo = "global"
                ubicacion.sucursal = None
                ubicacion.full_clean()
                ubicacion.save()

                ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
                return JsonResponse({"success": True, "ubicaciones": ubicaciones})

            except ValidationError as e:
                form.add_error(None, e.message)

        html = render_to_string(
            "inventario/ubicacion_form.html",
            {"form": form, "ubicacion": ubicacion},
            request=request
        )
        return JsonResponse({"success": False, "html": html})

    form = UbicacionForm(instance=ubicacion)
    html = render_to_string(
        "inventario/ubicacion_form.html",
        {"form": form, "ubicacion": ubicacion},
        request=request
    )
    return JsonResponse({"html": html})


# ============================================================
# ELIMINAR UBICACIÓN — solo dueño
# ============================================================

@login_required
def eliminar_ubicacion(request, ubicacion_id):
    if request.user.empleado.rol != "dueño":
        return JsonResponse({"success": False, "error": "Sin permiso."}, status=403)

    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
    ubicacion.delete()

    ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
    return JsonResponse({"success": True, "ubicaciones": ubicaciones})