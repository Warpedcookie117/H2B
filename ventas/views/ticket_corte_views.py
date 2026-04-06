from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from ventas.models import CorteCaja
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from ventas.services.ticket_service import generar_texto_ticket
from sucursales.models import Sucursal
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum
from ventas.models import Venta
from sucursales.models import Sucursal, Caja




@login_required
def ticket_corte(request, corte_id):
    corte = get_object_or_404(CorteCaja, id=corte_id)

    contexto = {
        "corte": corte,
        "caja": corte.caja,
        "empleado": corte.empleado,
        "fecha": corte.fecha,
        "total_general": corte.total_general,
        "totales_dueno": corte.total_por_dueno,
    }

    return render(request, "ventas/ticket_corte.html", contexto)

@login_required
def tickets_cortes_caja(request, sucursal_id):
    sucursal = get_object_or_404(Sucursal, id=sucursal_id)

    cortes = CorteCaja.objects.filter(
        caja__sucursal=sucursal
    ).order_by("-fecha")

    # Filtros
    fecha = request.GET.get("fecha")
    caja_id = request.GET.get("caja")

    if fecha:
        cortes = cortes.filter(fecha__date=fecha)

    if caja_id:
        cortes = cortes.filter(caja_id=caja_id)

    return render(request, "ventas/tickets_cortes_caja.html", {
        "sucursal": sucursal,
        "cortes": cortes,
    })


def ticket_corte_pdf(request, corte_id):
    corte = CorteCaja.objects.get(id=corte_id)
    texto = generar_texto_ticket(corte)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="corte_{corte_id}.pdf"'

    p = canvas.Canvas(response)
    y = 800

    for linea in texto.split("\n"):
        p.drawString(40, y, linea)
        y -= 18

    p.showPage()
    p.save()

    return response


def ticket_corte_termico(request, corte_id):
    corte = CorteCaja.objects.get(id=corte_id)
    texto = generar_texto_ticket(corte)

    response = HttpResponse(texto, content_type="text/plain; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="corte_{corte_id}.txt"'

    return response



@login_required
def corte_del_dia(request):
    # 1. Verificar caja activa
    caja_id = request.session.get("caja_actual")
    if not caja_id:
        messages.error(request, "No estás dentro de ninguna caja.")
        return redirect("dashboard_socio")

    caja = Caja.objects.get(id=caja_id)

    # 2. Fecha actual
    hoy = timezone.now().date()

    # 3. Buscar el último corte de esta caja
    ultimo_corte = CorteCaja.objects.filter(caja=caja).order_by("-fecha").first()

    # 4. Ventas a incluir en este corte
    if ultimo_corte:
        # 🔥 Solo ventas DESPUÉS del último corte
        ventas = Venta.objects.filter(
            caja=caja,
            fecha__gt=ultimo_corte.fecha
        )
    else:
        # 🔥 Primer corte → ventas del día
        ventas = Venta.objects.filter(
            caja=caja,
            fecha__date=hoy
        )

    # 5. Total general
    total_general = ventas.aggregate(total=Sum("total"))["total"] or 0

    # 6. Totales por dueño
    totales_dueno = {}

    for venta in ventas:
        for item in venta.detalles.all():
            empleado_dueno = item.producto.dueño

            nombre_dueno = (
                empleado_dueno.user.get_full_name()
                or empleado_dueno.user.username
            )

            totales_dueno.setdefault(nombre_dueno, 0)
            totales_dueno[nombre_dueno] += float(item.subtotal)

    # 7. Crear el corte
    corte = CorteCaja.objects.create(
        caja=caja,
        empleado=request.user.empleado,
        total_general=total_general,
        total_por_dueno=totales_dueno
    )

    # 8. Limpiar sesión de caja
    request.session.pop("sucursal_actual", None)
    request.session.pop("caja_actual", None)

    messages.success(request, "Corte del día realizado correctamente.")

    # 9. Redirigir al ticket del corte
    return redirect("ventas:ticket_corte", corte.id)

