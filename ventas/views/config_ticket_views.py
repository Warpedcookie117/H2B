from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from ventas.models import ConfigTicket


@login_required
def config_ticket_view(request):
    if request.user.empleado.rol != "dueño":
        messages.error(request, "Solo el dueño puede cambiar la configuración del ticket.")
        return redirect("ventas:pos")

    cfg = ConfigTicket.get()

    if request.method == "POST":
        cfg.nombre_empresa          = request.POST.get("nombre_empresa", "").strip()[:30]
        cfg.telefono                = request.POST.get("telefono", "").strip()[:30]
        cfg.direccion               = request.POST.get("direccion", "").strip()[:30]
        cfg.mostrar_id_producto     = "mostrar_id_producto" in request.POST
        cfg.mostrar_tipo_precio     = "mostrar_tipo_precio" in request.POST
        cfg.texto_mayoreo           = request.POST.get("texto_mayoreo", "").strip()[:30]
        cfg.texto_menudeo           = request.POST.get("texto_menudeo", "").strip()[:30]
        cfg.mensaje_pie             = request.POST.get("mensaje_pie", "").strip()[:30]
        cfg.mensaje_agradecimiento  = request.POST.get("mensaje_agradecimiento", "").strip()[:30]
        cfg.save()
        messages.success(request, "Formato del ticket guardado.")
        return redirect("ventas:config_ticket")

    return render(request, "ventas/config_ticket.html", {"cfg": cfg})
