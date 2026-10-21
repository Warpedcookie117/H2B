import logging
from decimal import Decimal

from django.db import transaction

from ventas.models import Venta, CorteCaja
from ventas.services.reparto import (
    desglose_por_dueno,
    reparto_venta,
    totales_caja,
    ventas_para_desglose,
)
from ventas.services.deudas_service import registrar_deudas_de_corte

logger = logging.getLogger(__name__)


def resumen_ventas_dueno_por_caja(empleado, fecha):
    """
    Desglose POR CAJA de lo vendido de los productos de `empleado` en
    `fecha` — efectivo/tarjeta/total/saldo, una fila por caja donde hubo al
    menos una venta suya. Filtra por fecha de calendario (no por "desde
    el último corte"), así que no le afecta si la caja ya se cortó o no.

    Los montos salen de ventas/services/reparto.py (la misma fuente que el
    corte de caja): ya con el descuento aplicado, efectivo neto (sin el
    cambio) y pagos mixtos repartidos a centavos exactos. Solo cuenta sus
    PRODUCTOS: los servicios que cobra como responsable de la sucursal no
    entran aquí ("¿Cuánto llevo yo?" es lo de su mercancía).

    "efectivo" es lo que quedó en SU caja, "tarjeta" lo que entró a SU Clip
    y "saldo" lo que le deben (> 0) o debe (< 0) por cobros hechos en el
    Clip de otra (regla de la receptora, ver reparto._repartir_fisico). Ya
    no se cumple efectivo + tarjeta == total; sí efectivo + tarjeta + saldo.

    Devuelve floats (redondeados a 2) porque la consume la API JSON.
    """
    ventas = ventas_para_desglose(
        Venta.objects
        .filter(detalles__producto__dueño=empleado, fecha__date=fecha, caja__isnull=False)
        .distinct()
    )

    por_caja = {}

    for venta in ventas:
        acc = por_caja.setdefault(venta.caja_id, {
            "caja_id": venta.caja_id,
            "sucursal": venta.caja.sucursal.nombre if venta.caja.sucursal_id else "",
            "caja": venta.caja.nombre,
            "efectivo": Decimal("0"),
            "tarjeta": Decimal("0"),
            "total": Decimal("0"),
            "saldo": Decimal("0"),
        })

        for fila in reparto_venta(venta):
            grupo = fila["grupo"]
            if grupo.tipo != "producto" or grupo.cajon_id != empleado.id:
                continue
            acc["efectivo"] += fila["efectivo"]
            acc["tarjeta"] += fila["tarjeta"]
            acc["total"] += fila["total"]
            acc["saldo"] += fila["saldo"]

    for d in por_caja.values():
        d["efectivo"] = round(float(d["efectivo"]), 2)
        d["tarjeta"] = round(float(d["tarjeta"]), 2)
        d["total"] = round(float(d["total"]), 2)
        d["saldo"] = round(float(d["saldo"]), 2)

    return sorted(por_caja.values(), key=lambda d: (d["sucursal"], d["caja"]))


def resumen_ventas_dueno_por_fecha(empleado, fecha):
    """
    Efectivo/tarjeta/total/saldo de los productos de `empleado` en
    `fecha`, sumando TODAS sus cajas. Ver resumen_ventas_dueno_por_caja
    para el desglose caja por caja.
    """
    por_caja = resumen_ventas_dueno_por_caja(empleado, fecha)
    return {
        "efectivo": round(sum(d["efectivo"] for d in por_caja), 2),
        "tarjeta": round(sum(d["tarjeta"] for d in por_caja), 2),
        "total": round(sum(d["total"] for d in por_caja), 2),
        "saldo": round(sum(d["saldo"] for d in por_caja), 2),
    }


def generar_corte_para_fecha(caja, fecha):
    ventas = Venta.objects.filter(caja=caja, fecha__date=fecha)

    total_general = totales_caja(ventas)["total"]

    # Mismo desglose que el ticket de corte (reparto.py): montos ya con
    # descuento, servicios dentro de la fila de la responsable de servicios.
    totales_dueno = {
        f["nombre"]: float(f["total"])
        for f in desglose_por_dueno(ventas_para_desglose(ventas))
    }

    with transaction.atomic():
        corte = CorteCaja.objects.create(
            caja=caja,
            empleado=None,
            caja_nombre=caja.nombre,
            total_general=total_general,
            total_por_dueno=totales_dueno
        )

        # ⭐ Fix — ManyToMany en CorteCaja, no FK en Venta
        corte.ventas.set(ventas)

        # Deudas entre dueñas → historial del dashboard. Solo cuenta las
        # ventas que no estén ya en otro corte (este corte automático toma
        # todo el día, incluidas ventas de un corte manual previo). Si falla
        # NO se tumba el corte: el corte es lo importante; el registro usa
        # su propio savepoint y se puede repetir (es idempotente).
        try:
            registrar_deudas_de_corte(corte)
        except Exception:
            logger.exception("registrar_deudas_de_corte falló corte=%s", corte.pk)

    return corte
