from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from ventas.models import CorteCaja
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from ventas.services.ticket_service import generar_texto_ticket, imprimir_silencioso
from sucursales.models import Sucursal
from django.utils import timezone
from django.contrib import messages
from django.db.models import Sum
from ventas.models import Venta
from sucursales.models import Sucursal, Caja




@login_required
def ticket_corte(request, corte_id):
    corte = get_object_or_404(CorteCaja, id=corte_id)

    resumen_duenos = {}

    for venta in corte.ventas.all():
        for item in venta.detalles.all():
            if item.producto:
                empleado_dueno = item.producto.dueño
                if empleado_dueno:
                    nombre_dueno = empleado_dueno.user.first_name or empleado_dueno.user.username
                else:
                    nombre_dueno = "Sin dueño"
            else:
                nombre_dueno = item.nombre_snapshot or "PRODUCTO ELIMINADO"

            subtotal = float(item.subtotal)

            if nombre_dueno not in resumen_duenos:
                resumen_duenos[nombre_dueno] = {"total": 0.0, "efectivo": 0.0, "tarjeta": 0.0}

            resumen_duenos[nombre_dueno]["total"] += subtotal

            if venta.metodo_pago == "efectivo":
                resumen_duenos[nombre_dueno]["efectivo"] += subtotal
            elif venta.metodo_pago == "tarjeta":
                resumen_duenos[nombre_dueno]["tarjeta"] += subtotal
            elif venta.metodo_pago == "mixto":
                total_venta = float(venta.total)
                if total_venta > 0:
                    proporcion = subtotal / total_venta
                    efectivo_neto = float(venta.pagado_efectivo) - float(venta.cambio)
                    resumen_duenos[nombre_dueno]["efectivo"] += proporcion * efectivo_neto
                    resumen_duenos[nombre_dueno]["tarjeta"]  += proporcion * float(venta.pagado_tarjeta)

    for d in resumen_duenos.values():
        d["total"]    = round(d["total"],    2)
        d["efectivo"] = round(d["efectivo"], 2)
        d["tarjeta"]  = round(d["tarjeta"],  2)

    total_efectivo = round(sum(float(v.pagado_efectivo) - float(v.cambio) for v in corte.ventas.all()), 2)
    total_tarjeta  = round(sum(float(v.pagado_tarjeta) for v in corte.ventas.all()), 2)

    return render(request, "ventas/ticket_corte.html", {
        "corte": corte,
        "caja": corte.caja,
        "empleado": corte.empleado,
        "fecha": corte.fecha,
        "total_general": corte.total_general,
        "resumen_duenos": resumen_duenos,
        "total_efectivo": total_efectivo,
        "total_tarjeta": total_tarjeta,
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
def corte_del_dia(request):
    empleado_rol = getattr(getattr(request.user, "empleado", None), "rol", None)
    if empleado_rol not in ("cajero", "dueño"):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied

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
        ventas = Venta.objects.filter(caja=caja, fecha__gt=ultimo_corte.fecha)
    else:
        ventas = Venta.objects.filter(caja=caja, fecha__date=hoy)

    # 5. Total general
    total_general = ventas.aggregate(total=Sum("total"))["total"] or 0

    # 6. Totales por dueño con desglose efectivo/tarjeta
    totales_dueno = {}
    resumen_duenos = {}

    for venta in ventas:
        for item in venta.detalles.all():
            if item.producto:
                empleado_dueno = item.producto.dueño
                nombre_dueno = (
                    empleado_dueno.user.get_full_name()
                    or empleado_dueno.user.username
                ) if empleado_dueno else "Sin dueño"
            else:
                nombre_dueno = item.nombre_snapshot or "PRODUCTO ELIMINADO"

            subtotal = float(item.subtotal)

            totales_dueno.setdefault(nombre_dueno, 0)
            totales_dueno[nombre_dueno] += subtotal

            if nombre_dueno not in resumen_duenos:
                resumen_duenos[nombre_dueno] = {"total": 0, "efectivo": 0, "tarjeta": 0}

            resumen_duenos[nombre_dueno]["total"] += subtotal

            if venta.metodo_pago == "efectivo":
                resumen_duenos[nombre_dueno]["efectivo"] += subtotal
            elif venta.metodo_pago == "tarjeta":
                resumen_duenos[nombre_dueno]["tarjeta"] += subtotal
            elif venta.metodo_pago == "mixto":
                total_venta = float(venta.total)
                if total_venta > 0:
                    proporcion = subtotal / total_venta
                    efectivo_neto = float(venta.pagado_efectivo) - float(venta.cambio)
                    resumen_duenos[nombre_dueno]["efectivo"] += proporcion * efectivo_neto
                    resumen_duenos[nombre_dueno]["tarjeta"]  += proporcion * float(venta.pagado_tarjeta)

    # Redondear
    for d in resumen_duenos.values():
        d["total"] = round(d["total"], 2)
        d["efectivo"] = round(d["efectivo"], 2)
        d["tarjeta"] = round(d["tarjeta"], 2)

    # 7. Crear el corte
    corte = CorteCaja.objects.create(
        caja=caja,
        empleado=request.user.empleado,
        total_general=total_general,
        total_por_dueno=totales_dueno
    )

    # ⭐ Guardar ventas del corte
    corte.ventas.set(ventas)

    # 8. Imprimir ticket térmico automáticamente
    imprimir_silencioso(generar_texto_ticket(corte))

    # 9. Limpiar sesión
    request.session.pop("sucursal_actual", None)
    request.session.pop("caja_actual", None)

    messages.success(request, "Corte del día realizado correctamente.")

    # 9. Redirigir al ticket
    return redirect("ventas:ticket_corte", corte.id)