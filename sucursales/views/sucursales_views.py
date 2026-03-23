from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from sucursales.forms import SucursalForm
from sucursales.services.sucursales_service import SucursalService


# ---------------------------------------------------------
# CREAR SUCURSAL (solo dueño)
# ---------------------------------------------------------
@login_required
def crear_sucursal(request):

    empleado = getattr(request.user, "empleado", None)

    # Validación de rol
    if not empleado or empleado.rol != "dueño":
        messages.error(request, "Acceso denegado. Solo el dueño puede crear sucursales.")
        return redirect("tienda_temp:dashboard_dueno")

    if request.method == "POST":
        form = SucursalForm(request.POST)

        if form.is_valid():
            try:
                sucursal = SucursalService.crear(
                    nombre=form.cleaned_data["nombre"],
                    direccion=form.cleaned_data["direccion"]
                )

                messages.success(request, "Sucursal creada correctamente.")
                return redirect("sucursales:dashboard_sucursal", sucursal_id=sucursal.id)

            except Exception as e:
                form.add_error(None, str(e))

    else:
        form = SucursalForm()

    return render(request, "sucursales/crear_sucursales.html", {"form": form})