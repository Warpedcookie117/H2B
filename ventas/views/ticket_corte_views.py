from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from reportlab.pdfgen import canvas
from ventas.services.ticket_service import generar_texto_ticket, imprimir_silencioso
from ventas.services.reparto import (
    desglose_como_dict,
    desglose_por_dueno,
    totales_caja,
    ventas_para_desglose,
)
from caja_chica import api as caja_chica
from ventas.services.corte_service import efectivo_del_corte, ventas_pendientes_de_corte
from django.utils import timezone
from django.contrib import messages
from ventas.models import CorteCaja, Venta
from sucursales.models import Sucursal, Caja



@login_required
def ticket_corte(request, corte_id):
    corte = get_object_or_404(CorteCaja.objects.select_related("caja__sucursal"), id=corte_id)

    # Todo sale de reparto.py: Σ filas == totales de la caja, al centavo.
    tot = totales_caja(corte.ventas.all())
    filas = desglose_por_dueno(ventas_para_desglose(corte.ventas.all()))

    return render(request, "ventas/ticket_corte.html", {
        "corte": corte,
        "caja": corte.caja,
        "empleado": corte.empleado,
        "fecha": corte.fecha,
        "total_general": corte.total_general,
        "resumen_duenos": desglose_como_dict(filas),
        "filas_duenos": filas,
        # Lo que entró al Clip de cada dueña; Σ == total_tarjeta.
        "clips": [f for f in filas if f["tarjeta"] != 0],
        "total_efectivo": tot["efectivo"],
        "total_tarjeta": tot["tarjeta"],
        # Debe haber por cajón, ya sin los vales y gastos de la caja chica.
        "efectivo": efectivo_del_corte(corte, filas),
    })

@login_required
def tickets_cortes_caja(request, sucursal_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
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


@login_required
def ticket_corte_pdf(request, corte_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    corte = get_object_or_404(CorteCaja, id=corte_id)
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


@login_required
def ticket_corte_termico(request, corte_id):
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    corte = get_object_or_404(CorteCaja, id=corte_id)
    imprimir_silencioso(generar_texto_ticket(corte))
    return redirect("ventas:ticket_corte", corte_id)


@login_required
def ticket_corte_texto_json(request, corte_id):
    """Devuelve el texto del ticket de corte como JSON para que el agente POS lo imprima."""
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    corte = get_object_or_404(CorteCaja, id=corte_id)
    return JsonResponse({"ticket_texto": generar_texto_ticket(corte)})



@login_required
def corte_del_dia(request):
    empleado_rol = getattr(getattr(request.user, "empleado", None), "rol", None)
    if empleado_rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

    # 1. Verificar caja activa
    caja_id = request.session.get("caja_actual")
    if not caja_id:
        messages.error(request, "No estás dentro de ninguna caja.")
        return redirect("tienda_temp:dashboard_socio")

    caja = Caja.objects.get(id=caja_id)

    # 2. Instante del corte (t0): todo lo que se cobró hasta aquí entra en
    # este corte y nada de lo posterior.
    t0 = timezone.now()

    # 3-4. Ventas a incluir: (último corte de esta caja, t0]; si la caja
    # nunca ha tenido corte, las de hoy (hora local).
    ventas = ventas_pendientes_de_corte(caja, t0)

    # Se fija el conjunto UNA vez: el total, el desglose y el M2M salen
    # exactamente de las mismas ventas aunque entre otra mientras tanto.
    ids = list(ventas.values_list("id", flat=True))
    ventas = Venta.objects.filter(id__in=ids)

    # 5. Total general y 6. total por dueño (reparto.py: ya con descuento,
    # servicios dentro de la fila de la responsable de servicios).
    total_general = totales_caja(ventas)["total"]
    totales_dueno = {
        f["nombre"]: float(f["total"])
        for f in desglose_por_dueno(ventas_para_desglose(ventas))
    }

    with transaction.atomic():
        # 7. Crear el corte
        corte = CorteCaja.objects.create(
            caja=caja,
            caja_nombre=caja.nombre,
            empleado=request.user.empleado,
            total_general=total_general,
            total_por_dueno=totales_dueno
        )

        # fecha es auto_now_add (el momento del INSERT, un poco después de t0).
        # El siguiente corte toma ventas con fecha > corte.fecha, así que una
        # venta cobrada entre t0 y el INSERT no entraría en ninguno de los dos.
        # Con fecha = t0 esa venta cae en el siguiente corte y no queda huérfana.
        CorteCaja.objects.filter(pk=corte.pk).update(fecha=t0)
        corte.fecha = t0

        # ⭐ Guardar ventas del corte
        corte.ventas.set(ventas)
        # Vales y gastos de esta caja hasta t0 que no tenían corte.
        caja_chica.al_cerrar_corte(corte, hasta=t0)

    # 8. Imprimir ticket térmico automáticamente
    imprimir_silencioso(generar_texto_ticket(corte))

    # 9. Limpiar sesión
    request.session.pop("sucursal_actual", None)
    request.session.pop("caja_actual", None)

    messages.success(request, "Corte del día realizado correctamente.")

    # 9. Redirigir al ticket
    return redirect("ventas:ticket_corte", corte.id)