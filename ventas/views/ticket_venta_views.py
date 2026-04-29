from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from ventas.models import Venta
from django.http import HttpResponse, JsonResponse
from ventas.services.ticket_service import generar_texto_ticket, imprimir_silencioso
from reportlab.pdfgen import canvas
from sucursales.models import Sucursal
from django.db.models import Sum, F

@login_required
def ticket_venta(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)

    # 🔥 Generar el ticket térmico EXACTO
    ticket_texto = generar_texto_ticket(venta)

    contexto = {
        "venta": venta,
        "detalles": venta.detalles.all(),
        "empleado": venta.empleado,
        "fecha": venta.fecha,
        "total": venta.total,
        "subtotal": venta.subtotal,
        "descuento": venta.descuento,
        "metodo_pago": venta.metodo_pago,
        "pagado_efectivo": venta.pagado_efectivo,
        "pagado_tarjeta": venta.pagado_tarjeta,
        "cambio": venta.cambio,
        "ticket_texto": ticket_texto,
    }

    return render(request, "ventas/ticket_venta.html", contexto)


@login_required
def tickets_ventas(request, sucursal_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    ventas = Venta.objects.filter(
        caja__sucursal=sucursal
    ).order_by("-fecha")

    # Filtros
    ticket_id = request.GET.get("ticket_id")
    fecha = request.GET.get("fecha")
    caja_id = request.GET.get("caja")

    if ticket_id:
        ventas = ventas.filter(id=ticket_id)

    if fecha:
        ventas = ventas.filter(fecha__date=fecha)

    if caja_id:
        ventas = ventas.filter(caja_id=caja_id)

    return render(request, "ventas/tickets_ventas.html", {
        "sucursal": sucursal,
        "ventas": ventas,
    })




@login_required
def ticket_venta_pdf(request, venta_id):
    venta = get_object_or_404(Venta, id=venta_id)
    texto = generar_texto_ticket(venta)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="venta_{venta_id}.pdf"'

    p = canvas.Canvas(response)
    y = 800

    for linea in texto.split("\n"):
        p.drawString(40, y, linea)
        y -= 18

    p.showPage()
    p.save()

    return response


@login_required
def ticket_venta_termico(request, venta_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Sin permiso.")
    venta = get_object_or_404(Venta, id=venta_id)
    imprimir_silencioso(generar_texto_ticket(venta))
    return redirect("ventas:ticket_venta", venta_id)
