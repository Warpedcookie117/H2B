from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from caja_chica import api as caja_chica
from ventas.models import Venta, CorteCaja
from ventas.services.reparto import (
    CONCEPTO_SIN_REGISTRO,
    desglose_por_dueno,
    reparto_venta,
    totales_caja,
    ventas_para_desglose,
)


def ventas_pendientes_de_corte(caja, t0=None):
    """
    QuerySet de las ventas de `caja` que entran en su próximo corte: las
    posteriores al último corte de esa caja y hasta t0. Si la caja nunca ha
    tenido corte, las de HOY (hora local) hasta t0. localtime() porque now()
    es UTC y pasadas las 6pm hora de Monterrey ya cae en el día siguiente.
    """
    t0 = t0 or timezone.now()
    ultimo = CorteCaja.objects.filter(caja=caja).order_by("-fecha").values_list("fecha", flat=True).first()
    if ultimo is not None:
        return Venta.objects.filter(caja_id=caja.id, fecha__gt=ultimo, fecha__lte=t0)
    hoy = timezone.localtime(t0).date()
    return Venta.objects.filter(caja_id=caja.id, fecha__date=hoy, fecha__lte=t0)


CAMPOS_RESUMEN = ("efectivo", "tarjeta", "total", "saldo", "productos", "servicios", "sin_registro",
                  "salidas", "en_caja", "del_fondo")


def resumen_ventas_dueno_por_caja(empleado, fecha):
    """
    Desglose POR CAJA de lo de `empleado` en `fecha`: una fila por caja
    donde hubo al menos una venta suya. Filtra por fecha de calendario (no
    por "desde el último corte"), así que no le afecta si la caja ya se
    cortó o no.

    Es su fila del corte (ventas/services/reparto.py, la misma fuente): ya
    con el descuento, efectivo neto (sin el cambio) y pagos mixtos a
    centavos exactos. A la responsable de servicios se le suman los
    servicios y el "Prod. sin registro" como en el corte, porque son suyos
    y su dinero está en su caja y en su Clip:
    total == productos + servicios + sin_registro.

    "efectivo" es lo que quedó en SU caja, "tarjeta" lo que entró a SU Clip
    y "saldo" lo que le deben (> 0) o debe (< 0) por cobros hechos en el
    Clip de otra (solo ventas de antes del pago en seco). Se cumple
    efectivo + tarjeta + saldo == total.

    Caja chica: "salidas" son los vales y gastos de ese día que salieron de
    su cajita (solo la responsable de servicios tiene); "en_caja" es lo que
    debe haber ya sin ellos y "del_fondo" lo que no alcanzó (como el corte:
    caja_chica.CajitaConSalidas, nunca negativo).

    Devuelve floats (redondeados a 2) porque la consume la API JSON.
    """
    ventas = ventas_para_desglose(
        Venta.objects
        .filter(fecha__date=fecha, caja__isnull=False)
        .filter(Q(detalles__producto__dueño=empleado)
                | Q(caja__sucursal__dueño_servicios=empleado, detalles__atributos_snapshot__tipo="servicio"))
        .distinct()
    )
    sin_registro = CONCEPTO_SIN_REGISTRO.casefold()

    por_caja = {}

    def fila_de(caja):
        return por_caja.setdefault(caja.id, {
            "caja_id": caja.id,
            "sucursal": caja.sucursal.nombre if caja.sucursal_id else "",
            "caja": caja.nombre,
            **{c: Decimal("0") for c in CAMPOS_RESUMEN},
        })

    for venta in ventas:
        acc = fila_de(venta.caja)

        for fila in reparto_venta(venta):
            if fila["grupo"].cajon_id != empleado.id:
                continue
            acc["efectivo"] += fila["efectivo"]
            acc["tarjeta"] += fila["tarjeta"]
            acc["total"] += fila["total"]
            acc["saldo"] += fila["saldo"]
            if fila["concepto"] is None:
                acc["productos"] += fila["total"]
            elif fila["concepto"].casefold() == sin_registro:
                acc["sin_registro"] += fila["total"]
            else:
                acc["servicios"] += fila["total"]

    salidas = caja_chica.salidas_del_dia(empleado.id, fecha)
    if salidas:
        from sucursales.models import Caja
        for caja in Caja.objects.select_related("sucursal").filter(id__in=salidas):
            fila_de(caja)["salidas"] = salidas[caja.id]
    for d in por_caja.values():
        cajita = caja_chica.CajitaConSalidas(d["efectivo"], gastos=d["salidas"])
        d["en_caja"], d["del_fondo"] = cajita.debe_haber, cajita.del_fondo
        for c in CAMPOS_RESUMEN:
            d[c] = round(float(d[c]), 2)

    return sorted(por_caja.values(), key=lambda d: (d["sucursal"], d["caja"]))


def sumar_resumen_dueno(por_caja):
    """Las filas de resumen_ventas_dueno_por_caja sumadas (todas sus cajas)."""
    return {c: round(sum(d[c] for d in por_caja), 2) for c in CAMPOS_RESUMEN}


def resumen_ventas_dueno_por_fecha(empleado, fecha):
    """
    Lo de `empleado` en `fecha` sumando TODAS sus cajas. Ver
    resumen_ventas_dueno_por_caja para el desglose caja por caja.
    """
    return sumar_resumen_dueno(resumen_ventas_dueno_por_caja(empleado, fecha))


def generar_corte_para_fecha(caja, fecha):
    """
    Corte automático de un día que la cajera no cerró. Solo toma las ventas
    de ese día que NO están ya en otro corte: antes tomaba el día completo y
    repetía las de un corte manual previo (en oct-2026, 119 ventas en dos
    cortes y $44k de más al sumar tickets). Si no queda ninguna venta sin
    cortar, no crea nada y devuelve None.
    """
    ventas = Venta.objects.filter(caja=caja, fecha__date=fecha, cortes__isnull=True)
    if not ventas.exists():
        return None

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
        # Vales y gastos de ese día que no tenían corte.
        caja_chica.al_cerrar_corte(corte, hasta=corte.fecha, dia=fecha)

    return corte


def efectivo_del_corte(corte, filas):
    """
    Lo del efectivo de un corte, ya con la caja chica: los vales y gastos
    salen de la cajita de la responsable de servicios (caja_chica.api), así
    que a su cajón se le restan. Ningún cajón se muestra en negativo: si
    salió más de lo que entró por ventas, la diferencia salió del fondo.
    `filas` = desglose_por_dueno de las ventas del corte. Lo usan la vista
    web del corte y el ticket térmico, para que digan lo mismo.

      cajones: [{"nombre", "especial", "servicios", "efectivo_ventas",
                 "vales", "gastos", "debe_haber", "del_fondo"}]
               dueñas primero, filas sin dueña al final; se omiten las que
               no tuvieron efectivo ni caja chica.
      gastos / vales: [Movimiento] de ese corte (todas las cajitas).
      total_vales, total_gastos, total_debe_haber, total_del_fondo
    """
    salidas = caja_chica.salidas_del_corte(corte.pk) if corte.pk else {}
    duenas, especiales = [], []
    vistas = set()
    for f in filas:
        s = None if f["especial"] else salidas.get(f["empleado_id"])
        if f["efectivo"] == 0 and s is None:
            continue
        c = caja_chica.CajitaConSalidas(f["efectivo"], s.total_vales if s else caja_chica.CERO,
                                        s.total_gastos if s else caja_chica.CERO)
        (especiales if f["especial"] else duenas).append(
            _cajon(f["nombre"], f["especial"], bool(f["servicios"]), c))
        vistas.add(f["empleado_id"])
    # La dueña de la cajita sin ventas en efectivo en este corte también sale.
    for duena_id, s in salidas.items():
        if duena_id not in vistas:
            duenas.append(_cajon(s.duena_nombre, False, False,
                                 caja_chica.CajitaConSalidas(caja_chica.CERO, s.total_vales, s.total_gastos)))
    cajones = duenas + especiales
    return {
        "cajones": cajones,
        "gastos": [g for s in salidas.values() for g in s.gastos],
        "vales": [v for s in salidas.values() for v in s.vales],
        "total_vales": sum((s.total_vales for s in salidas.values()), caja_chica.CERO),
        "total_gastos": sum((s.total_gastos for s in salidas.values()), caja_chica.CERO),
        "total_debe_haber": sum((c["debe_haber"] for c in cajones), caja_chica.CERO),
        "total_del_fondo": sum((c["del_fondo"] for c in cajones), caja_chica.CERO),
    }


def _cajon(nombre, especial, servicios, cajita):
    return {
        "nombre": nombre, "especial": especial, "servicios": servicios,
        "efectivo_ventas": cajita.efectivo_ventas, "vales": cajita.vales, "gastos": cajita.gastos,
        "debe_haber": cajita.debe_haber, "del_fondo": cajita.del_fondo,
    }
