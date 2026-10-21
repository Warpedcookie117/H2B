"""
Deudas entre dueñas: lo que una le quedó debiendo a otra por la regla de la
receptora (ver ventas/services/reparto.py). Es información sensible, así que
ya NO sale en el corte (lo ve la cajera): cada dueña la ve en SU dashboard,
solo las deudas donde ella participa.

  - "Hoy": en vivo, desde el último corte de cada caja (deudas_hoy). Se
    puede marcar "Ya se pagó" aunque no haya corte (pago en corto,
    marcar_pagada_hoy): se guarda como DeudaEntreDuenas sin corte y se le
    resta a lo que se debe.
  - Historial: lo que quedó registrado al cerrar cada corte
    (registrar_deudas_de_corte → DeudaEntreDuenas), con "Ya se pagó".

Las NO pagadas nunca se borran; de las pagadas se conservan solo las 5 más
recientes por dueña (se poda al registrar un corte).
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from sucursales.models import Caja
from ventas.models import CorteCaja, DeudaEntreDuenas, Venta
from ventas.services.reparto import desglose_y_deudas, nombre_de, ventas_para_desglose

CERO = Decimal("0.00")

# Cuántas deudas YA PAGADAS se conservan por dueña.
PAGADAS_A_CONSERVAR = 5


class DeudaCambio(Exception):
    """La deuda de hoy ya no es la que vio la dueña (entró otra venta o la otra ya la marcó)."""


def _firmado(deudor_id, acreedor_id, monto):
    """
    (pareja, monto con signo) para sumar deudas y pagos de una misma pareja:
    + si la de id menor le debe a la de id mayor, - si es al revés.
    """
    a, b = sorted((deudor_id, acreedor_id))
    return (a, b), (monto if deudor_id == a else -monto)


def _pagos_en_corto():
    """Pagos en corto que todavía no entran en ningún corte."""
    return DeudaEntreDuenas.objects.filter(
        corte__isnull=True, antes_del_corte=True, pagada=True,
        deudor__isnull=False, acreedor__isnull=False,
    )


# ---------------------------------------------------------------------------
# Ventas pendientes de corte (un solo criterio para el corte y para "hoy")
# ---------------------------------------------------------------------------

def _filtro_pendientes(caja_id, fecha_ultimo_corte, t0):
    """
    Q de las ventas de una caja que entran en su próximo corte: las
    posteriores al último corte y hasta t0. Si la caja nunca ha tenido
    corte, las de HOY (hora local) hasta t0. localtime() porque now() es
    UTC y pasadas las 6pm hora de Monterrey ya cae en el día siguiente.
    """
    if fecha_ultimo_corte is not None:
        return Q(caja_id=caja_id, fecha__gt=fecha_ultimo_corte, fecha__lte=t0)
    hoy = timezone.localtime(t0).date()
    return Q(caja_id=caja_id, fecha__date=hoy, fecha__lte=t0)


def ventas_pendientes_de_corte(caja, t0=None):
    """
    QuerySet de las ventas de `caja` que todavía no entran en ningún corte:
    (último corte de esa caja, t0]. Es el criterio de corte_del_dia, así que
    lo que ve la dueña como deudas de "hoy" es exactamente lo que va a
    quedar registrado cuando la cajera haga el corte.
    """
    t0 = t0 or timezone.now()
    ultimo = CorteCaja.objects.filter(caja=caja).order_by("-fecha").values_list("fecha", flat=True).first()
    return Venta.objects.filter(_filtro_pendientes(caja.id, ultimo, t0))


# ---------------------------------------------------------------------------
# Registro al cerrar un corte
# ---------------------------------------------------------------------------

def _podar_pagadas(empleado_ids):
    """
    Borra las deudas PAGADAS de esas dueñas que ya no están entre las
    PAGADAS_A_CONSERVAR más recientes ni de la deudora ni de la acreedora.
    Nunca toca las no pagadas ni los pagos en corto que aún no tienen corte
    (de esos depende la cuenta de "hoy").
    """
    cortadas = DeudaEntreDuenas.objects.filter(pagada=True, corte__isnull=False)
    candidatas = list(
        cortadas
        .filter(Q(deudor_id__in=empleado_ids) | Q(acreedor_id__in=empleado_ids))
        .values_list("id", "deudor_id", "acreedor_id")
    )
    if not candidatas:
        return
    # Se protegen las más recientes de TODA persona involucrada (también la
    # contraparte, aunque no haya participado en este corte).
    personas = {p for _, d, a in candidatas for p in (d, a) if p is not None}
    conservar = set()
    for pid in personas:
        conservar.update(
            cortadas
            .filter(Q(deudor_id=pid) | Q(acreedor_id=pid))
            .order_by("-fecha", "-id")
            .values_list("id", flat=True)[:PAGADAS_A_CONSERVAR]
        )
    borrar = [i for i, _, _ in candidatas if i not in conservar]
    if borrar:
        DeudaEntreDuenas.objects.filter(id__in=borrar, pagada=True).delete()


def registrar_deudas_de_corte(corte):
    """
    Guarda en DeudaEntreDuenas las deudas (neteadas por pareja) de las
    ventas del corte y poda las pagadas viejas. Llamar DESPUÉS de
    corte.ventas.set(...).

    Los pagos en corto de esa caja (marcados desde "Hoy" antes del corte)
    pasan a ser de este corte, y el corte solo registra lo que quedó
    pendiente después de ellos: deuda de 50 con 20 pagados en corto → se
    registra una pendiente de 30 (y si se pagó de más, la deuda queda al revés).

    Solo cuenta las ventas del corte que NO están en otro corte: el corte
    automático (generar_corte_para_fecha) toma todas las ventas del día,
    incluidas las que ya entraron en un corte manual, y sin esto la deuda
    se registraría dos veces. Idempotente: volver a llamarla no duplica
    (UniqueConstraint corte+deudor+acreedor con ignore_conflicts).

    Devuelve cuántas deudas calculó de las ventas (no cuántas se insertaron).
    """
    with transaction.atomic():
        if corte.caja_id is not None:
            _pagos_en_corto().filter(caja_id=corte.caja_id).update(corte=corte)
        pagos = list(corte.deudas_duenas.filter(antes_del_corte=True,
                                                deudor__isnull=False, acreedor__isnull=False))

        # Subquery explícita sobre la tabla intermedia: un
        # corte.ventas.exclude(cortes__in=...) reutiliza el JOIN del propio
        # related manager y no excluye nada.
        en_otro_corte = (CorteCaja.ventas.through.objects
                         .exclude(cortecaja_id=corte.pk)
                         .values("venta_id"))
        ids = list(corte.ventas.exclude(pk__in=en_otro_corte).values_list("pk", flat=True))
        ventas = Venta.objects.filter(pk__in=ids)
        fecha = ventas.aggregate(m=Max("fecha"))["m"]
        if fecha is None and not pagos:
            return 0

        deudas = desglose_y_deudas(ventas_para_desglose(ventas))[1] if fecha is not None else []

        # Lo que quedó pendiente por pareja = deudas de las ventas - pagos en corto.
        saldo = {}
        nombres = {}
        for d in deudas:
            k, m = _firmado(d["debe_id"], d["a_id"], d["monto"])
            saldo[k] = saldo.get(k, CERO) + m
            nombres[d["debe_id"]] = d["debe"]
            nombres[d["a_id"]] = d["a"]
        for p in pagos:
            k, m = _firmado(p.deudor_id, p.acreedor_id, p.monto)
            saldo[k] = saldo.get(k, CERO) - m
            nombres.setdefault(p.deudor_id, p.deudor_nombre)
            nombres.setdefault(p.acreedor_id, p.acreedor_nombre)

        fecha = fecha or max(p.fecha for p in pagos)
        caja_nombre = corte.caja_nombre or (corte.caja.nombre if corte.caja_id else None)
        pendientes = []
        for (a, b), m in saldo.items():
            if m == 0:
                continue
            debe, acreedora = (a, b) if m > 0 else (b, a)
            pendientes.append(DeudaEntreDuenas(
                corte=corte,
                caja_id=corte.caja_id,
                deudor_id=debe,
                acreedor_id=acreedora,
                deudor_nombre=nombres[debe][:150],
                acreedor_nombre=nombres[acreedora][:150],
                monto=abs(m),
                fecha=fecha,
                caja_nombre=caja_nombre,
            ))
        if pendientes:
            DeudaEntreDuenas.objects.bulk_create(pendientes, ignore_conflicts=True)

        personas = {p for par in saldo for p in par}
        if personas:
            _podar_pagadas(personas)
        return len(deudas)


# ---------------------------------------------------------------------------
# Lo que ve cada dueña en su dashboard
# ---------------------------------------------------------------------------

def _desde_por_pareja(ventas):
    """
    {frozenset({deudora_id, acreedora_id}): fecha de la PRIMERA venta que
    dejó deuda entre esa pareja}. `ventas` ya viene en orden de fecha. Solo
    se revisan las ventas con tarjeta: sin tarjeta el efectivo alcanza para
    todas y no queda deuda.
    """
    desde = {}
    for venta in ventas:
        if not venta.pagado_tarjeta:
            continue
        for d in desglose_y_deudas([venta])[1]:
            desde.setdefault(frozenset((d["debe_id"], d["a_id"])), venta.fecha)
    return desde


def _desde_txt(fecha, hoy):
    """'desde las 4:12 pm', 'desde la 1:05 pm' o, si no fue hoy, 'desde el 18/10 a las 4:12 pm'."""
    local = timezone.localtime(fecha)
    h12 = local.hour % 12 or 12
    hora = f"{'la' if h12 == 1 else 'las'} {h12}:{local.minute:02d} {'am' if local.hour < 12 else 'pm'}"
    if local.date() == hoy:
        return f"desde {hora}"
    return f"desde el {local:%d/%m} a {hora}"


def _cuentas_de_caja(caja, ventas, pagos, empleado, hoy):
    """
    (pendientes, pagadas) de `empleado` en una caja sin cortar:
      pendientes: lo que se debe AHORITA con cada otra dueña = deudas de las
                  ventas sin corte - lo ya pagado en corto (montos en Decimal).
      pagadas:    los pagos en corto, como items de historial.
    `ventas` en orden de fecha; `pagos` solo los de esa caja donde participa.
    """
    desde = _desde_por_pareja(ventas)
    saldo = {}
    nombres = {}
    orden = []
    for d in (desglose_y_deudas(ventas)[1] if ventas else []):
        if empleado.id not in (d["debe_id"], d["a_id"]):
            continue
        k, m = _firmado(d["debe_id"], d["a_id"], d["monto"])
        if k not in saldo:
            orden.append(k)
        saldo[k] = saldo.get(k, CERO) + m
        nombres[d["debe_id"]] = d["debe"]
        nombres[d["a_id"]] = d["a"]
    for p in pagos:
        k, m = _firmado(p.deudor_id, p.acreedor_id, p.monto)
        if k not in saldo:
            orden.append(k)
        saldo[k] = saldo.get(k, CERO) - m
        nombres.setdefault(p.deudor_id, p.deudor_nombre)
        nombres.setdefault(p.acreedor_id, p.acreedor_nombre)

    pendientes = []
    for k in orden:
        m = saldo[k]
        if m == 0:
            continue
        debe, acreedora = k if m > 0 else (k[1], k[0])
        yo_debo = debe == empleado.id
        con = acreedora if yo_debo else debe
        fecha = desde.get(frozenset(k))
        pendientes.append({
            "caja": caja.nombre, "caja_id": caja.id, "con_id": con, "con_nombre": nombres[con],
            "yo_debo": yo_debo, "monto": abs(m),
            "desde_txt": _desde_txt(fecha, hoy) if fecha is not None else "",
        })
    return pendientes, [item_historial(p, empleado) for p in pagos]


def deudas_hoy(empleado, t0=None):
    """
    Deudas EN VIVO (lo que todavía no se corta) donde participa `empleado`,
    caja por caja en todas las sucursales. Las deudas se netean por pareja
    dentro de cada caja (igual que en el corte) y se les resta lo ya pagado
    en corto; el "resumen" además las netea por persona sumando todas las
    cajas. "desde_txt" dice de cuándo es la primera venta que dejó deuda
    entre esa pareja en esa caja.

    {"items": [{"caja", "caja_id", "con_id", "con_nombre", "yo_debo", "monto", "desde_txt"}],
     "pagadas": [item_historial de los pagos en corto],
     "resumen": [{"con_id", "con_nombre", "monto"}],   # > 0 te debe, < 0 le debes
     "total_debes": float, "total_te_deben": float}

    Queries fijas sin importar cuántas cajas haya: cajas + último corte de
    cada una (1), pagos en corto (1), ventas pendientes de todas (1) y sus
    detalles (1).
    """
    t0 = t0 or timezone.now()
    hoy = timezone.localtime(t0).date()
    cajas = list(
        Caja.objects.select_related("sucursal")
        .annotate(ultimo_corte=Max("cortecaja__fecha"))
        .order_by("sucursal__nombre", "nombre", "id")
    )
    pagos_por_caja = {}
    for p in (_pagos_en_corto().filter(Q(deudor=empleado) | Q(acreedor=empleado))
              .order_by("pagada_en", "id")):
        pagos_por_caja.setdefault(p.caja_id, []).append(p)

    items = []
    pagadas = []
    if cajas:
        filtro = Q()
        for caja in cajas:
            filtro |= _filtro_pendientes(caja.id, caja.ultimo_corte, t0)
        por_caja = {}
        for venta in ventas_para_desglose(Venta.objects.filter(filtro).order_by("fecha", "id")):
            por_caja.setdefault(venta.caja_id, []).append(venta)

        for caja in cajas:
            ventas = por_caja.get(caja.id, [])
            pagos = pagos_por_caja.get(caja.id, [])
            if not ventas and not pagos:
                continue
            pendientes, pagos_items = _cuentas_de_caja(caja, ventas, pagos, empleado, hoy)
            items.extend(pendientes)
            pagadas.extend(pagos_items)

    # Neteo por persona (todas las cajas), en Decimal hasta el final.
    neto = {}
    nombres = {}
    for it in items:
        signo = -1 if it["yo_debo"] else 1
        neto[it["con_id"]] = neto.get(it["con_id"], CERO) + signo * it["monto"]
        nombres.setdefault(it["con_id"], it["con_nombre"])
    resumen = sorted(
        ({"con_id": cid, "con_nombre": nombres[cid], "monto": m} for cid, m in neto.items() if m != 0),
        key=lambda r: (-abs(r["monto"]), r["con_nombre"].casefold()),
    )
    total_debes = sum((-r["monto"] for r in resumen if r["monto"] < 0), CERO)
    total_te_deben = sum((r["monto"] for r in resumen if r["monto"] > 0), CERO)

    # float al final: JsonResponse manda Decimal como string y el JS espera número.
    for it in items:
        it["monto"] = float(it["monto"])
    for r in resumen:
        r["monto"] = float(r["monto"])
    return {
        "items": items,
        "pagadas": pagadas,
        "resumen": resumen,
        "total_debes": float(total_debes),
        "total_te_deben": float(total_te_deben),
    }


def marcar_pagada_hoy(empleado, caja_id, con_id, monto):
    """
    "Ya se pagó" en una deuda de HOY (todavía sin corte) entre `empleado` y
    la dueña `con_id`, en esa caja: guarda un pago en corto por lo que se
    debe AHORITA. `monto` (Decimal) es lo que la dueña vio en pantalla; si
    ya no coincide (entró otra venta o la otra dueña la acaba de marcar)
    → DeudaCambio y no se guarda nada. Caja inexistente → Caja.DoesNotExist;
    sin deuda entre ellas en esa caja → DeudaEntreDuenas.DoesNotExist.
    """
    t0 = timezone.now()
    with transaction.atomic():
        # Bloquea la caja: dos dueñas picando a la vez no guardan dos pagos.
        caja = Caja.objects.select_for_update().get(pk=caja_id)
        ventas = list(ventas_para_desglose(ventas_pendientes_de_corte(caja, t0).order_by("fecha", "id")))
        pagos = list(_pagos_en_corto().filter(caja_id=caja.id)
                     .filter(Q(deudor=empleado) | Q(acreedor=empleado)))
        pendientes, _ = _cuentas_de_caja(caja, ventas, pagos, empleado, timezone.localtime(t0).date())

        item = next((it for it in pendientes if it["con_id"] == con_id), None)
        if item is None:
            raise DeudaEntreDuenas.DoesNotExist("No hay deuda pendiente con esa dueña en esa caja.")
        if abs(item["monto"] - monto) >= Decimal("0.005"):
            raise DeudaCambio()

        mio = nombre_de(empleado)
        if item["yo_debo"]:
            deudor, acreedor = (empleado.id, mio), (con_id, item["con_nombre"])
        else:
            deudor, acreedor = (con_id, item["con_nombre"]), (empleado.id, mio)
        return DeudaEntreDuenas.objects.create(
            corte=None,
            caja=caja,
            antes_del_corte=True,
            deudor_id=deudor[0],
            acreedor_id=acreedor[0],
            deudor_nombre=deudor[1][:150],
            acreedor_nombre=acreedor[1][:150],
            monto=item["monto"],
            fecha=t0,
            caja_nombre=caja.nombre,
            pagada=True,
            pagada_por=empleado,
            pagada_en=t0,
        )


def _de(empleado):
    """Deudas donde participa `empleado` (como deudora o como acreedora)."""
    return DeudaEntreDuenas.objects.filter(Q(deudor=empleado) | Q(acreedor=empleado))


def item_historial(deuda, empleado):
    """
    Una deuda registrada vista por `empleado`. "aviso" aparece cuando la
    marcó como pagada la OTRA persona, para que esta lo confirme.
    """
    yo_debo = deuda.deudor_id == empleado.id
    con_nombre = deuda.acreedor_nombre if yo_debo else deuda.deudor_nombre
    pagada_por_mi = deuda.pagada and deuda.pagada_por_id == empleado.id
    aviso = None
    if deuda.pagada and deuda.pagada_por_id is not None and not pagada_por_mi:
        aviso = (f"{con_nombre} dice que ya le pagaste" if yo_debo
                 else f"{con_nombre} dice que ya te pagó")
    return {
        "id": deuda.id,
        "fecha": timezone.localtime(deuda.fecha).isoformat(),
        "fecha_txt": timezone.localtime(deuda.fecha).strftime("%d/%m"),
        "caja": deuda.caja_nombre or "",
        "yo_debo": yo_debo,
        "con_nombre": con_nombre,
        "monto": float(deuda.monto),
        "pagada": deuda.pagada,
        "pagada_por_mi": pagada_por_mi,
        "aviso": aviso,
    }


def historial(empleado):
    """
    Deudas registradas en cortes anteriores donde participa `empleado`:
    todas las NO pagadas + las últimas PAGADAS_A_CONSERVAR pagadas, de la
    más reciente a la más vieja. Los pagos en corto que todavía no tienen
    corte salen en "hoy", no aquí. 2 queries.
    """
    cortadas = _de(empleado).filter(corte__isnull=False)
    pagadas = list(
        cortadas.filter(pagada=True).order_by("-fecha", "-id")
        .values_list("id", flat=True)[:PAGADAS_A_CONSERVAR]
    )
    deudas = (
        cortadas
        .filter(Q(pagada=False) | Q(id__in=pagadas))
        .order_by("-fecha", "-id")
    )
    return [item_historial(d, empleado) for d in deudas]


def marcar_pagada(deuda_id, empleado, pagada):
    """
    Marca (pagada=True) o desmarca (False) una deuda. Puede hacerlo
    cualquiera de las dos: la deudora o la acreedora; si `empleado` no es
    ninguna → DeudaEntreDuenas.DoesNotExist (la vista responde 404, no 403,
    para no revelar que la deuda existe).

    Fija el valor final, no alterna: repetir la misma llamada no cambia
    nada. Si la otra persona la vuelve a marcar como pagada, pasa a ser
    ella quien la marcó (el aviso cambia de lado).

    Desmarcar un pago en corto que todavía no tiene corte lo BORRA (la
    deuda vuelve a salir pendiente en "hoy") y devuelve None.
    """
    with transaction.atomic():
        deuda = _de(empleado).select_for_update().get(pk=deuda_id)
        if pagada:
            if not (deuda.pagada and deuda.pagada_por_id == empleado.id):
                deuda.pagada = True
                deuda.pagada_por = empleado
                deuda.pagada_en = timezone.now()
                deuda.save(update_fields=["pagada", "pagada_por", "pagada_en"])
        elif deuda.corte_id is None:
            deuda.delete()
            return None
        elif deuda.pagada or deuda.pagada_por_id is not None or deuda.pagada_en is not None:
            deuda.pagada = False
            deuda.pagada_por = None
            deuda.pagada_en = None
            deuda.save(update_fields=["pagada", "pagada_por", "pagada_en"])
    return deuda
