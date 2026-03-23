from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError

from inventario.forms import UbicacionForm
from inventario.models import Ubicacion
from inventario.services.ubicaciones_service import UbicacionService


@login_required
def ubicaciones(request):
    ubicaciones = Ubicacion.objects.all().order_by("nombre")
    return render(request, "inventario/ubicaciones.html", {"ubicaciones": ubicaciones})


@login_required
def ubicacion_nueva(request):
    if request.method == "POST":
        form = UbicacionForm(request.POST)

        if form.is_valid():
            try:
                nueva = UbicacionService.crear(
                    nombre=form.cleaned_data["nombre"],
                    tipo="global",          # 🔥 SIEMPRE GLOBAL
                    sucursal=None,          # 🔥 SIN SUCURSAL
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


@login_required
def editar_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    if request.method == "POST":
        form = UbicacionForm(request.POST, instance=ubicacion)

        if form.is_valid():
            try:
                # Aplicamos reglas del dominio
                ubicacion.nombre = form.cleaned_data["nombre"]
                ubicacion.direccion = form.cleaned_data["direccion"]

                # 🔥 Siempre global desde este módulo
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
            request=request  # 🔥 Necesario para CSRF
        )
        return JsonResponse({"success": False, "html": html})

    form = UbicacionForm(instance=ubicacion)
    html = render_to_string(
        "inventario/ubicacion_form.html",
        {"form": form, "ubicacion": ubicacion},
        request=request  # 🔥 Necesario para CSRF
    )
    return JsonResponse({"html": html})

@login_required
def eliminar_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
    ubicacion.delete()

    ubicaciones = list(Ubicacion.objects.values("id", "nombre", "direccion"))
    return JsonResponse({"success": True, "ubicaciones": ubicaciones})