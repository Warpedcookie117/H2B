from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
from ventas.models import CorteCaja, Venta
from django.shortcuts import redirect, render
from django.db.models import Sum, F
from django.utils.timezone import now


@login_required
def ventas_por_cajero(request):
    # now() es UTC — pasadas las 6pm hora de Monterrey ya cae en el dia
    # siguiente en UTC. localtime() lo corrige.
    hoy = timezone.localtime(timezone.now()).date()

    ventas = Venta.objects.filter(fecha__date=hoy)

    resumen = {}

    for venta in ventas:
        cajero = venta.empleado.nombre
        resumen.setdefault(cajero, {
            "total": 0,
            "tickets": 0,
            "productos": 0,
        })

        resumen[cajero]["total"] += float(venta.total)
        resumen[cajero]["tickets"] += 1
        resumen[cajero]["productos"] += sum(d.cantidad for d in venta.detalles.all())

    return render(request, "reportes/ventas_por_cajero.html", {"resumen": resumen})


@login_required
def api_ventas_hoy(request):
    empleado = getattr(request.user, "empleado", None)
    if not request.user.is_superuser and (not empleado or empleado.rol != "dueño"):
        raise PermissionDenied
    from sucursales.models import Sucursal
    # now() regresa UTC — pasadas las 6pm hora de Monterrey (UTC-6) ya cae
    # en el dia siguiente en UTC, y "ventas de hoy" se vuelve "ventas de
    # mañana" (0 resultados). localtime() lo corrige.
    hoy = timezone.localtime(now()).date()

    sucursales = Sucursal.objects.prefetch_related("cajas").all().order_by("nombre")

    # Desglose por caja de SOLO los productos de este dueño — se cruza
    # abajo con cada caja (en $0 si no vendió nada ahí hoy).
    dueno_por_caja_id = {}
    if empleado:
        from ventas.services.corte_service import resumen_ventas_dueno_por_caja
        dueno_por_caja_id = {d["caja_id"]: d for d in resumen_ventas_dueno_por_caja(empleado, hoy)}

    resultado_chart = []
    resultado_cajas = []
    resultado_mis_cajas = []

    for sucursal in sucursales:
        efectivo_sucursal = 0
        tarjeta_sucursal = 0

        for caja in sucursal.cajas.all().order_by("nombre"):
            ventas_caja = Venta.objects.filter(caja=caja, fecha__date=hoy)

            efectivo = float(ventas_caja.aggregate(total=Sum("pagado_efectivo")).get("total") or 0)
            tarjeta = float(ventas_caja.aggregate(total=Sum("pagado_tarjeta")).get("total") or 0)
            total = efectivo + tarjeta

            ultima_venta = ventas_caja.order_by("-fecha").first()
            ultima_hora = timezone.localtime(ultima_venta.fecha).strftime("%H:%M") if ultima_venta else None

            efectivo_sucursal += efectivo
            tarjeta_sucursal += tarjeta

            resultado_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": efectivo,
                "tarjeta": tarjeta,
                "total": total,
                "ultima_hora": ultima_hora,
            })

            mis = dueno_por_caja_id.get(caja.id, {"efectivo": 0, "tarjeta": 0, "total": 0})
            resultado_mis_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": mis["efectivo"],
                "tarjeta": mis["tarjeta"],
                "total": mis["total"],
            })

        resultado_chart.append({
            "nombre": sucursal.nombre,
            "efectivo": round(efectivo_sucursal, 2),
            "tarjeta": round(tarjeta_sucursal, 2),
            "total": round(efectivo_sucursal + tarjeta_sucursal, 2),
        })

    # $ vendido AHORITA (hoy) de los productos de este dueño — efectivo/tarjeta.
    # Se deriva de dueno_por_caja_id (ya consultado arriba) en vez de volver
    # a pegarle a la BD. Superusuario sin perfil de Empleado: se omite.
    mis_ventas = None
    if empleado:
        valores = dueno_por_caja_id.values()
        mis_ventas = {
            "efectivo": round(sum(d["efectivo"] for d in valores), 2),
            "tarjeta": round(sum(d["tarjeta"] for d in valores), 2),
            "total": round(sum(d["total"] for d in valores), 2),
        }

    return JsonResponse({
        "chart": resultado_chart,
        "cajas": resultado_cajas,
        "mis_ventas": mis_ventas,
        "mis_cajas": resultado_mis_cajas,
    }, safe=False)