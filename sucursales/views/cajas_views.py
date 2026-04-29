from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from sucursales.forms import CajaForm
from  sucursales.models import Caja
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
from django.contrib.auth import authenticate
from django.contrib import messages
from sucursales.models import Sucursal, Caja
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from ventas.models import Venta, CorteCaja
from django.db.models import Sum
from django.utils import timezone
from ventas.services.corte_service import generar_corte_para_fecha




@login_required
@require_POST
def crear_caja_ajax(request, sucursal_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"error": "Sin permiso."}, status=403)

    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    form = CajaForm(request.POST)

    if not form.is_valid():
        # Regresamos el primer error del form
        error = list(form.errors.values())[0][0]
        return JsonResponse({"error": error}, status=400)

    caja = form.save(commit=False)
    caja.sucursal = sucursal
    caja.save()

    return JsonResponse({
        "ok": True,
        "id": caja.id,
        "nombre": caja.nombre
    })


@login_required
def modal_crear_caja(request, sucursal_id):
    form = CajaForm()
    return JsonResponse({
        "html": render_to_string("sucursales/modal_crear_caja.html", {
            "form": form,
            "sucursal_id": sucursal_id
        }, request=request)
    })



@login_required
@require_POST
def entrar_caja_ajax(request):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        return JsonResponse({"error": "Sin permiso."}, status=403)

    caja_id = request.POST.get("caja_id")
    password = request.POST.get("password")

    user = authenticate(username=request.user.username, password=password)
    if not user:
        return JsonResponse({"error": "Contraseña incorrecta."}, status=400)

    caja = get_object_or_404(Caja, id=caja_id)

    hoy = timezone.now().date()
    ayer = hoy - timezone.timedelta(days=1)

    ultimo_corte = CorteCaja.objects.filter(caja=caja).order_by("-fecha").first()

    if not ultimo_corte or ultimo_corte.fecha.date() < hoy:
        # ⭐ Solo genera corte de ayer si hubo ventas
        from ventas.models import Venta
        hubo_ventas_ayer = Venta.objects.filter(caja=caja, fecha__date=ayer).exists()

        if hubo_ventas_ayer:
            corte_auto = generar_corte_para_fecha(caja, ayer)

            request.session["caja_actual"] = caja.id
            request.session["sucursal_actual"] = caja.sucursal_id

            return JsonResponse({
                "redirect": f"/ventas/ticket-corte/{corte_auto.id}/"
            })

    request.session["caja_actual"] = caja.id
    request.session["sucursal_actual"] = caja.sucursal_id

    return JsonResponse({"ok": True})




    
@login_required
def modal_entrar_caja(request):
    caja_id = request.GET.get("caja_id")
    nombre = request.GET.get("nombre")

    html = render_to_string(
        "sucursales/modal_entrar_caja.html",
        {"nombre": nombre, "caja_id": caja_id},
        request=request
    )

    return JsonResponse({"html": html})


@login_required
def salir_caja(request):

    # Limpiar sesión
    request.session.pop("sucursal_actual", None)
    request.session.pop("caja_actual", None)

    empleado = request.user.empleado
    rol = empleado.rol

    messages.info(request, "Has salido de la caja.")

    # Redirección según rol
    if rol == "dueño":
        return redirect("tienda_temp:dashboard_dueno")
    else:
        return redirect("tienda_temp:dashboard_socio")
    
    

# ============================================================
# ELIMINAR CAJA — solo dueño, sin reload
# ============================================================
 
@login_required
@require_POST
def eliminar_caja(request, caja_id):
 
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"success": False, "error": "Sin permiso."}, status=403)
 
    caja = get_object_or_404(Caja, id=caja_id)
    sucursal_id = caja.sucursal_id
    caja.delete()
 
    # Devolver cajas actualizadas
    cajas = list(
        Caja.objects
        .filter(sucursal_id=sucursal_id)
        .values("id", "nombre")
    )
 
    return JsonResponse({"success": True, "cajas": cajas})