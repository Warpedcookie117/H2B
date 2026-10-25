from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.utils import timezone
from ventas.models import CorteCaja, Venta
from django.shortcuts import redirect, render
from django.utils.timezone import now
from ventas.services.reparto import totales_caja


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
        resumen[cajero]["productos"] += sum(d.piezas for d in venta.detalles.all())

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

    # Desglose por caja de lo de este dueño (su fila del corte, con servicios
    # si es la responsable) — se cruza abajo con cada caja (en $0 si no
    # vendió nada ahí hoy).
    from ventas.services.corte_service import resumen_ventas_dueno_por_caja, sumar_resumen_dueno
    dueno_por_caja_id = {}
    if empleado:
        dueno_por_caja_id = {d["caja_id"]: d for d in resumen_ventas_dueno_por_caja(empleado, hoy)}

    resultado_chart = []
    resultado_cajas = []
    resultado_mis_cajas = []

    for sucursal in sucursales:
        efectivo_sucursal = 0
        tarjeta_sucursal = 0
        total_sucursal = 0

        for caja in sucursal.cajas.all().order_by("nombre"):
            ventas_caja = Venta.objects.filter(caja=caja, fecha__date=hoy)

            # totales_caja (reparto.py, el mismo cálculo que el corte):
            # efectivo NETO = pagado_efectivo - cambio (lo que físicamente
            # queda en el cajón); total = Σ venta.total, ya con descuento.
            # float() porque JsonResponse manda Decimal como string y el
            # JS del dashboard espera número.
            t = totales_caja(ventas_caja)
            efectivo = float(t["efectivo"])
            tarjeta = float(t["tarjeta"])
            total = float(t["total"])

            ultima_venta = ventas_caja.order_by("-fecha").first()
            ultima_hora = timezone.localtime(ultima_venta.fecha).strftime("%H:%M") if ultima_venta else None

            efectivo_sucursal += efectivo
            tarjeta_sucursal += tarjeta
            total_sucursal += total

            resultado_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": efectivo,
                "tarjeta": tarjeta,
                "total": total,
                "ultima_hora": ultima_hora,
            })

            mis = dueno_por_caja_id.get(caja.id, {"efectivo": 0, "tarjeta": 0, "total": 0, "saldo": 0, "en_caja": 0})
            resultado_mis_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": mis["efectivo"],   # en SU caja
                "tarjeta": mis["tarjeta"],     # en SU Clip
                "total": mis["total"],         # lo que vendió
                "saldo": mis["saldo"],         # > 0 le deben, < 0 debe
                "en_caja": mis["en_caja"],     # efectivo ya sin vales y gastos (caja chica)
            })

        resultado_chart.append({
            "nombre": sucursal.nombre,
            "efectivo": round(efectivo_sucursal, 2),
            "tarjeta": round(tarjeta_sucursal, 2),
            "total": round(total_sucursal, 2),
        })

    # $ vendido AHORITA (hoy) de este dueño — efectivo/tarjeta/total y, para
    # la responsable de servicios, productos/servicios/sin_registro. Se
    # deriva de dueno_por_caja_id (ya consultado arriba) en vez de volver a
    # pegarle a la BD. Superusuario sin perfil de Empleado: se omite.
    mis_ventas = None
    if empleado:
        mis_ventas = sumar_resumen_dueno(dueno_por_caja_id.values())

    return JsonResponse({
        "chart": resultado_chart,
        "cajas": resultado_cajas,
        "mis_ventas": mis_ventas,
        "mis_cajas": resultado_mis_cajas,
    }, safe=False)