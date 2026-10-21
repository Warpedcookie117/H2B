import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from ventas.models import CorteCaja, DeudaEntreDuenas, Venta
from django.shortcuts import redirect, render
from django.utils.timezone import now
from ventas.services.reparto import totales_caja
from sucursales.models import Caja
from ventas.services.deudas_service import (
    DeudaCambio, deudas_hoy, historial, item_historial, marcar_pagada, marcar_pagada_hoy,
)


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

            mis = dueno_por_caja_id.get(caja.id, {"efectivo": 0, "tarjeta": 0, "total": 0, "saldo": 0})
            resultado_mis_cajas.append({
                "sucursal": sucursal.nombre,
                "caja": caja.nombre,
                "efectivo": mis["efectivo"],   # en SU caja
                "tarjeta": mis["tarjeta"],     # en SU Clip
                "total": mis["total"],         # lo que vendió
                "saldo": mis["saldo"],         # > 0 le deben, < 0 debe
            })

        resultado_chart.append({
            "nombre": sucursal.nombre,
            "efectivo": round(efectivo_sucursal, 2),
            "tarjeta": round(tarjeta_sucursal, 2),
            "total": round(total_sucursal, 2),
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
            "saldo": round(sum(d["saldo"] for d in valores), 2),
        }

    # Deudas con las otras dueñas: solo las suyas (es información sensible,
    # ya no sale en el corte). "hoy" en vivo desde el último corte de cada
    # caja; "historial" lo registrado en cortes anteriores.
    mis_deudas = None
    if empleado:
        mis_deudas = {"hoy": deudas_hoy(empleado), "historial": historial(empleado)}

    return JsonResponse({
        "chart": resultado_chart,
        "cajas": resultado_cajas,
        "mis_ventas": mis_ventas,
        "mis_cajas": resultado_mis_cajas,
        "mis_deudas": mis_deudas,
    }, safe=False)


@login_required
@require_POST
def api_deuda_pagada(request, deuda_id):
    """
    Marca / desmarca como pagada una deuda entre dueñas. Body JSON
    {"pagada": true|false}. Cualquiera de las dos (deudora o acreedora)
    puede hacerlo; una deuda ajena responde 404 (no 403) para no revelar
    que existe. Devuelve el item de historial ya actualizado.
    """
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"status": "error", "error": "Solo dueñas."}, status=403)

    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"status": "error", "error": "JSON inválido."}, status=400)
    pagada = body.get("pagada") if isinstance(body, dict) else None
    if not isinstance(pagada, bool):
        return JsonResponse({"status": "error", "error": "Falta 'pagada' (true/false)."}, status=400)

    try:
        deuda = marcar_pagada(deuda_id, empleado, pagada)
    except DeudaEntreDuenas.DoesNotExist:
        return JsonResponse({"status": "error", "error": "Deuda no encontrada."}, status=404)

    # None: era un pago en corto de hoy y se desmarcó (la deuda vuelve a "hoy").
    return JsonResponse({"status": "ok", "deuda": item_historial(deuda, empleado) if deuda else None})


@login_required
@require_POST
def api_deuda_hoy_pagada(request):
    """
    "Ya se pagó" en una deuda de HOY (sin corte todavía). Body JSON
    {"caja_id": int, "con_id": int, "monto": número}: monto es lo que vio
    la dueña en pantalla; si la deuda ya cambió responde 409 sin guardar.
    """
    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse({"status": "error", "error": "Solo dueñas."}, status=403)

    try:
        body = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"status": "error", "error": "JSON inválido."}, status=400)
    if not isinstance(body, dict):
        body = {}
    caja_id, con_id, monto = body.get("caja_id"), body.get("con_id"), body.get("monto")
    if (not all(isinstance(x, int) and not isinstance(x, bool) for x in (caja_id, con_id))
            or not isinstance(monto, (int, float)) or isinstance(monto, bool)):
        return JsonResponse({"status": "error", "error": "Faltan caja_id, con_id o monto."}, status=400)
    try:
        monto = Decimal(str(monto))
    except InvalidOperation:
        return JsonResponse({"status": "error", "error": "Monto inválido."}, status=400)
    if not monto.is_finite():
        return JsonResponse({"status": "error", "error": "Monto inválido."}, status=400)

    try:
        marcar_pagada_hoy(empleado, caja_id, con_id, monto)
    except (Caja.DoesNotExist, DeudaEntreDuenas.DoesNotExist):
        return JsonResponse({"status": "error", "error": "Esa cuenta ya no está."}, status=404)
    except DeudaCambio:
        return JsonResponse({"status": "error", "error": "La cuenta cambió."}, status=409)

    return JsonResponse({"status": "ok"})