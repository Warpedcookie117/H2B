from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from inventario.forms import UbicacionForm
from inventario.models import Ubicacion
from django.template.loader import render_to_string




@login_required

def ubicaciones(request):
    ubicaciones = Ubicacion.objects.all().order_by("nombre")
    return render(request, "inventario/ubicaciones.html", {"ubicaciones": ubicaciones})

@login_required

def ubicacion_nueva(request):
    if request.method == "POST":
        form = UbicacionForm(request.POST)
        if form.is_valid():
            nueva = form.save()
            ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
            return JsonResponse({
                "success": True,
                "ubicaciones": ubicaciones,
                "id": nueva.id
            })
        else:
            html = render_to_string("inventario/ubicacion_form.html", {"form": form})
            return JsonResponse({"success": False, "html": html})

    form = UbicacionForm()
    html = render_to_string("inventario/ubicacion_form.html", {"form": form})
    return JsonResponse({"html": html})


@login_required
def editar_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    if request.method == "POST":
        form = UbicacionForm(request.POST, instance=ubicacion)
        if form.is_valid():
            form.save()
            ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
            return JsonResponse({"success": True, "ubicaciones": ubicaciones})
        return JsonResponse({"success": False, "html": render_to_string("inventario/ubicacion_form.html", {"form": form, "ubicacion": ubicacion})})

    form = UbicacionForm(instance=ubicacion)
    html = render_to_string("inventario/ubicacion_form.html", {"form": form, "ubicacion": ubicacion})
    return JsonResponse({"html": html})

@login_required
def eliminar_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
    ubicacion.delete()

    ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
    return JsonResponse({"success": True, "ubicaciones": ubicaciones})