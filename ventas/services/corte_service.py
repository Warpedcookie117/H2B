from ventas.models import Venta, CorteCaja
from django.db.models import Sum
from sucursales.models import Sucursal


def resumen_ventas_dueno_por_caja(empleado, fecha):
    """
    Desglose POR CAJA de lo vendido de los productos de `empleado` en
    `fecha` — efectivo/tarjeta/total, una fila por caja donde hubo al
    menos una venta suya. Filtra por fecha de calendario (no por "desde
    el último corte"), así que no le afecta si la caja ya se cortó o no.

    Mismo criterio de prorrateo para pagos mixtos que ticket_corte_views:
    cada renglón reparte su subtotal entre efectivo y tarjeta según el %
    que representa del total de SU venta (una venta puede traer productos
    de varios dueños y pagarse mitad efectivo, mitad tarjeta).
    """
    ventas = (
        Venta.objects
        .filter(detalles__producto__dueño=empleado, fecha__date=fecha)
        .distinct()
        .select_related("caja", "caja__sucursal")
        .prefetch_related("detalles__producto")
    )

    por_caja = {}

    for venta in ventas:
        if not venta.caja:
            continue

        acc = por_caja.setdefault(venta.caja_id, {
            "caja_id": venta.caja_id,
            "sucursal": venta.caja.sucursal.nombre if venta.caja.sucursal_id else "",
            "caja": venta.caja.nombre,
            "efectivo": 0.0,
            "tarjeta": 0.0,
            "total": 0.0,
        })

        for item in venta.detalles.all():
            if not item.producto or item.producto.dueño_id != empleado.id:
                continue

            subtotal = float(item.subtotal)
            acc["total"] += subtotal

            if venta.metodo_pago == "efectivo":
                acc["efectivo"] += subtotal
            elif venta.metodo_pago == "tarjeta":
                acc["tarjeta"] += subtotal
            elif venta.metodo_pago == "mixto":
                total_venta = float(venta.total)
                if total_venta > 0:
                    proporcion = subtotal / total_venta
                    efectivo_neto = float(venta.pagado_efectivo) - float(venta.cambio)
                    acc["efectivo"] += proporcion * efectivo_neto
                    acc["tarjeta"] += proporcion * float(venta.pagado_tarjeta)

    for d in por_caja.values():
        d["efectivo"] = round(d["efectivo"], 2)
        d["tarjeta"] = round(d["tarjeta"], 2)
        d["total"] = round(d["total"], 2)

    return sorted(por_caja.values(), key=lambda d: (d["sucursal"], d["caja"]))


def resumen_ventas_dueno_por_fecha(empleado, fecha):
    """
    Efectivo/tarjeta/total vendido de los productos de `empleado` en
    `fecha`, sumando TODAS sus cajas. Ver resumen_ventas_dueno_por_caja
    para el desglose caja por caja.
    """
    por_caja = resumen_ventas_dueno_por_caja(empleado, fecha)
    return {
        "efectivo": round(sum(d["efectivo"] for d in por_caja), 2),
        "tarjeta": round(sum(d["tarjeta"] for d in por_caja), 2),
        "total": round(sum(d["total"] for d in por_caja), 2),
    }


def generar_corte_para_fecha(caja, fecha):
    ventas = Venta.objects.filter(caja=caja, fecha__date=fecha)

    # Nombre del responsable de servicios configurado para esta sucursal
    try:
        suc = Sucursal.objects.select_related("dueño_servicios__user").get(id=caja.sucursal_id)
        ds = suc.dueño_servicios
        nombre_servicios = (ds.user.get_full_name() or ds.user.username) if ds else "Servicios"
    except Sucursal.DoesNotExist:
        nombre_servicios = "Servicios"

    total_general = ventas.aggregate(total=Sum("total"))["total"] or 0

    totales_dueno = {}
    for venta in ventas:
        for item in venta.detalles.all():
            # ⭐ Fix — usar snapshot si producto fue eliminado
            if item.producto:
                empleado_dueno = item.producto.dueño
                nombre = (
                    empleado_dueno.user.get_full_name()
                    or empleado_dueno.user.username
                ) if empleado_dueno else "Sin dueño"
            elif item.atributos_snapshot and item.atributos_snapshot.get("tipo") == "servicio":
                nombre = nombre_servicios
            else:
                nombre = item.nombre_snapshot or "PRODUCTO ELIMINADO"

            totales_dueno.setdefault(nombre, 0)
            totales_dueno[nombre] += float(item.subtotal)

    corte = CorteCaja.objects.create(
        caja=caja,
        empleado=None,
        caja_nombre=caja.nombre,
        total_general=total_general,
        total_por_dueno=totales_dueno
    )

    # ⭐ Fix — ManyToMany en CorteCaja, no FK en Venta
    corte.ventas.set(ventas)

    return corte