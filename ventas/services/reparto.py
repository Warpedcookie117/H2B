"""
Reparto del dinero de las ventas entre las dueñas. ÚNICA fuente de verdad
para dashboard, corte de caja y el modal de cambio del POS: si cada pantalla
prorrateara por su cuenta (con floats y redondeos distintos) las cifras no
cuadrarían entre sí ni con lo que hay físicamente en la caja.

Idea central: lo que le TOCA a cada dueña de una venta es su parte del
total (ya con descuento), en proporción a su BASE (Σ subtotal de sus
renglones) con el método de mayor residuo a centavos. Dónde queda
físicamente el dinero sigue la regla de las dueñas: la que más vendió en la
cuenta recibe el billete, da el cambio y cobra la tarjeta en SU Clip; a las
demás se les pasa lo suyo en efectivo, y si no alcanza queda como deuda
(ver _repartir_fisico). Cada columna suma EXACTAMENTE el monto de la venta,
así que el desglose de un corte suma exacto lo de totales_caja().

Todo en Decimal. Este módulo solo importa modelos (ventas, inventario) para
que corte_service / ticket_service / pos_service puedan importarlo sin ciclos.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from django.db.models import Count, DecimalField, F, Prefetch, Sum

from inventario.models import Producto
from ventas.models import Venta, VentaDetalle

CENT = Decimal("0.01")
CERO = Decimal("0.00")

_PREFIJO_SERVICIO = "servicio:"

NOMBRE_SERVICIOS_SIN_RESPONSABLE = "Servicios (sin responsable)"
NOMBRE_SIN_ASIGNAR = "Sin asignar"
NOMBRE_SIN_DUENO = "Sin dueño"
NOMBRE_PRODUCTO_ELIMINADO = "PRODUCTO ELIMINADO"

# Concepto con el que el POS guarda el cobro rápido (static/js/pos/carrito.js).
# Viaja como servicio, pero en el corte se reporta aparte de los servicios.
CONCEPTO_SIN_REGISTRO = "Prod. sin registro"

# Orden de las filas especiales al final del desglose.
_ORDEN_ESPECIALES = {"sin_dueno": 0, "servicios_sin_responsable": 1, "sin_asignar": 2}


def _dec(valor):
    """
    A Decimal de 2 decimales. Los objetos Venta recién creados por
    POSService traen floats en memoria (no se refrescan de la BD), así que
    todo monto pasa por aquí antes de operar.
    """
    if valor is None:
        return CERO
    if not isinstance(valor, Decimal):
        valor = Decimal(str(valor))
    return valor.quantize(CENT, rounding=ROUND_HALF_UP)


def _centavos(valor):
    """Decimal de 2 decimales → entero de centavos (exacto)."""
    return int(_dec(valor) * 100)


# ---------------------------------------------------------------------------
# Totales de caja
# ---------------------------------------------------------------------------

def efectivo_neto(venta):
    """Efectivo que realmente se quedó en la caja: lo recibido menos el cambio."""
    return max(CERO, _dec(venta.pagado_efectivo) - _dec(venta.cambio))


def totales_caja(ventas_qs):
    """
    Totales de un conjunto de ventas en UN solo aggregate. Sirve con un
    QuerySet normal o con corte.ventas.all(). Efectivo = Σ(recibido - cambio),
    que es lo que debe haber en el cajón.
    """
    agg = ventas_qs.aggregate(
        efectivo=Sum(
            F("pagado_efectivo") - F("cambio"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        ),
        tarjeta=Sum("pagado_tarjeta"),
        total=Sum("total"),
        num_ventas=Count("pk"),
    )
    return {
        # SQLite suma en float: el quantize devuelve los centavos exactos.
        "efectivo": _dec(agg["efectivo"]),
        "tarjeta": _dec(agg["tarjeta"]),
        "total": _dec(agg["total"]),
        "num_ventas": agg["num_ventas"] or 0,
    }


def ventas_para_desglose(ventas_qs):
    """
    Precarga todo lo que necesita el reparto en 2 queries (ventas + detalles),
    sin importar cuántas ventas haya. El Prefetch NO se filtra por dueña: la
    proporción de cada una depende de TODOS los renglones de la venta.
    """
    return ventas_qs.select_related("caja__sucursal__dueño_servicios__user").prefetch_related(
        Prefetch("detalles", queryset=VentaDetalle.objects.select_related("producto__dueño__user"))
    )


# ---------------------------------------------------------------------------
# Clasificación de renglones
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Grupo:
    clave: tuple          # ("empleado", id) | ("sin_dueno", nombre) | ("servicios_sin_responsable",) | ("sin_asignar",)
    nombre: str           # nombre visible
    cajon_id: int | None  # id de la Empleado dueña del cajón físico; None para especiales
    tipo: str             # "producto" | "servicio" | "especial"


GRUPO_SIN_ASIGNAR = Grupo(("sin_asignar",), NOMBRE_SIN_ASIGNAR, None, "especial")
GRUPO_SERVICIOS_SIN_RESPONSABLE = Grupo(
    ("servicios_sin_responsable",), NOMBRE_SERVICIOS_SIN_RESPONSABLE, None, "especial"
)


def nombre_de(emp):
    return (emp.user.first_name or "").strip() or emp.user.username


def _tipo_snapshot(item):
    snap = item.atributos_snapshot
    return snap.get("tipo") if isinstance(snap, dict) else None


def _concepto_servicio(item):
    """'Servicio: Copias' → 'Copias'. Sin prefijo se deja tal cual; vacío → 'Servicio'."""
    nombre = (item.nombre_snapshot or "").strip()
    if nombre[:len(_PREFIJO_SERVICIO)].casefold() == _PREFIJO_SERVICIO:
        nombre = nombre[len(_PREFIJO_SERVICIO):].strip()
    return nombre or "Servicio"


def _clasificar(item, venta):
    """
    (Grupo, Empleado dueña del cajón | None, concepto | None), o None si es
    regalo. Devuelve la Empleado para poder leer prioridad_cambio y username
    sin meterlos en Grupo (que es contrato público).
    """
    tipo = _tipo_snapshot(item)
    if tipo == "regalo":
        return None

    if tipo == "servicio":
        concepto = _concepto_servicio(item)
        caja = venta.caja
        ds = caja.sucursal.dueño_servicios if caja is not None else None
        if ds is not None:
            return Grupo(("empleado", ds.id), nombre_de(ds), ds.id, "servicio"), ds, concepto
        return GRUPO_SERVICIOS_SIN_RESPONSABLE, None, concepto

    producto = item.producto
    if producto is not None and producto.dueño is not None:
        d = producto.dueño
        return Grupo(("empleado", d.id), nombre_de(d), d.id, "producto"), d, None

    if producto is None:
        # Producto borrado: igual que el corte histórico, se agrupa por su snapshot.
        nombre = item.nombre_snapshot or NOMBRE_PRODUCTO_ELIMINADO
    else:
        nombre = NOMBRE_SIN_DUENO
    return Grupo(("sin_dueno", nombre), nombre, None, "especial"), None, None


def grupo_de_renglon(item, venta):
    """Grupo al que va el dinero de un renglón; None si es regalo."""
    r = _clasificar(item, venta)
    return r[0] if r is not None else None


# ---------------------------------------------------------------------------
# Reparto de una venta
# ---------------------------------------------------------------------------

def _clave_prioridad(emp):
    # Vacío va después de cualquier número (incluido 0), sin depender de un tope.
    p = emp.prioridad_cambio if emp is not None else None
    return (p is None, p or 0)


def _bases_por_cajon(filas):
    bases = {}
    for f in filas:
        cid = f["grupo"].cajon_id
        if cid is not None:
            bases[cid] = bases.get(cid, CERO) + f["base"]
    return bases


def _orden_receptora(filas, empleados):
    """
    cajon_ids ordenados para elegir quién recibe el pago y da el cambio: la
    que más vendió en la cuenta (por BASE, no por efectivo); empate →
    prioridad_cambio, luego nombre, luego id. El primero es la receptora.
    """
    bases = _bases_por_cajon(filas)
    return sorted(
        bases,
        key=lambda cid: (
            -bases[cid],
            _clave_prioridad(empleados[cid]),
            nombre_de(empleados[cid]).casefold(),
            cid,
        ),
    )


def _clave_fila(fila, bases_cajon, empleados):
    """
    Orden total y determinista de las filas: cajones en el mismo orden que la
    receptora, especiales al final. Desempata los centavos sobrantes.
    """
    g = fila["grupo"]
    concepto = fila["concepto"] or ""
    if g.cajon_id is not None:
        emp = empleados[g.cajon_id]
        return (0, -bases_cajon[g.cajon_id], _clave_prioridad(emp), g.nombre.casefold(),
                g.cajon_id, g.tipo, concepto, repr(g.clave))
    return (1, -fila["base"], (True, 0), g.nombre.casefold(), 0, g.tipo, concepto, repr(g.clave))


def _repartir(monto, bases_cent):
    """
    Mayor residuo en centavos enteros: piso de la parte exacta de cada fila
    y los centavos que faltan, uno por fila, a las de mayor residuo. Las filas
    ya vienen en orden de desempate (sorted es estable). Aritmética entera
    para que el resultado no dependa de la precisión de Decimal.
    """
    a = _centavos(monto)
    w = sum(bases_cent)
    partes, residuos = [], []
    for b in bases_cent:
        q, r = divmod(a * b, w)
        partes.append(q)
        residuos.append(r)
    faltan = a - sum(partes)  # Σresiduos / w, siempre en [0, len(filas))
    for i in sorted(range(len(partes)), key=lambda i: -residuos[i])[:faltan]:
        partes[i] += 1
    return [Decimal(p) * CENT for p in partes]


def _reparto(venta):
    """reparto_venta + el mapa cajon_id → Empleado (para prioridad y username)."""
    subgrupos = {}
    empleados = {}
    for item in venta.detalles.all():
        r = _clasificar(item, venta)
        if r is None:
            continue
        grupo, emp, concepto = r
        if emp is not None:
            empleados[emp.id] = emp
        fila = subgrupos.get((grupo.clave, grupo.tipo, concepto))
        if fila is None:
            fila = subgrupos[(grupo.clave, grupo.tipo, concepto)] = {
                "grupo": grupo, "concepto": concepto, "cantidad": 0, "base": CERO,
            }
        fila["cantidad"] += item.cantidad
        fila["base"] += _dec(item.subtotal)

    total = _dec(venta.total)
    neto = efectivo_neto(venta)
    tarjeta = _dec(venta.pagado_tarjeta)
    filas = list(subgrupos.values())
    # W = Σ renglones, NO venta.subtotal: con ofertas nxprecio no cuadran.
    w = sum((f["base"] for f in filas), CERO)

    if w <= 0:
        if total > 0 or neto > 0 or tarjeta > 0:
            # Dinero sin renglones que lo expliquen: no se pierde, se reporta.
            return [{"grupo": GRUPO_SIN_ASIGNAR, "concepto": None, "cantidad": 0, "base": CERO,
                     "total": total, "efectivo": neto, "tarjeta": tarjeta, "saldo": CERO}], empleados
        return [], empleados

    bases_cajon = _bases_por_cajon(filas)
    filas.sort(key=lambda f: _clave_fila(f, bases_cajon, empleados))
    bases_cent = [_centavos(f["base"]) for f in filas]
    for fila, t in zip(filas, _repartir(total, bases_cent)):
        fila["total"] = t

    if not bases_cajon:
        # Nadie con caja ni Clip propio (todo especial): proporcional.
        for fila, e, c in zip(filas, _repartir(neto, bases_cent), _repartir(tarjeta, bases_cent)):
            fila["efectivo"], fila["tarjeta"] = e, c
    else:
        _repartir_fisico(filas, _orden_receptora(filas, empleados)[0], neto, tarjeta)

    for fila in filas:
        # > 0: a esta fila le deben (cobró menos de lo que vendió);
        # < 0: debe (su Clip recibió más de lo suyo). Σ saldos == 0 si la venta cuadra.
        fila["saldo"] = fila["total"] - fila["efectivo"] - fila["tarjeta"]
    return filas, empleados


def _pesos(filas, idx):
    """Pesos en centavos de esas filas: su total; si todo es 0, su base."""
    pesos = [_centavos(filas[i]["total"]) for i in idx]
    if sum(pesos) == 0:
        pesos = [_centavos(filas[i]["base"]) for i in idx]
    return pesos


def _repartir_fisico(filas, receptora, neto, tarjeta):
    """
    Dónde queda físicamente el dinero de UNA venta. Regla de las dueñas: la
    que más vendió en la cuenta (la receptora) recibe el billete Y cobra la
    tarjeta en SU Clip. Con el efectivo se completa lo de las demás:

      - Toda la tarjeta va a la receptora (a su Clip).
      - Cada otra fila recibe su total en efectivo, si alcanza; si no
        alcanza (p. ej. todo se pagó con tarjeta), el efectivo que hay se
        reparte entre ellas en proporción y lo que falta queda como saldo:
        la receptora se lo debe (lo tiene en su Clip).
      - Lo que sobra del efectivo se queda en la caja de la receptora.

    Σ efectivo == neto y Σ tarjeta == tarjeta, exactos.
    """
    de_r = [i for i, f in enumerate(filas) if f["grupo"].cajon_id == receptora]
    otras = [i for i, f in enumerate(filas) if f["grupo"].cajon_id != receptora]
    pesos_r = _pesos(filas, de_r)

    for i, c in zip(de_r, _repartir(tarjeta, pesos_r)):
        filas[i]["tarjeta"] = c
    for i in otras:
        filas[i]["tarjeta"] = CERO

    total = sum((f["total"] for f in filas), CERO)
    necesitan = sum((filas[i]["total"] for i in otras), CERO)
    if neto >= necesitan:
        for i in otras:
            filas[i]["efectivo"] = filas[i]["total"]
        for i, e in zip(de_r, _repartir(neto - necesitan, pesos_r)):
            filas[i]["efectivo"] = e
        if neto + tarjeta == total:
            # Venta que cuadra: cada fila de la receptora se completa con
            # tarjeta (total - efectivo). Redondear efectivo y tarjeta por
            # separado podía dejar una fila en +0.01 y otra en -0.01.
            for i in de_r:
                filas[i]["tarjeta"] = filas[i]["total"] - filas[i]["efectivo"]
    else:
        for i, e in zip(otras, _repartir(neto, _pesos(filas, otras))):
            filas[i]["efectivo"] = e
        for i in de_r:
            filas[i]["efectivo"] = CERO


def reparto_venta(venta):
    """
    Filas por subgrupo (grupo, tipo, concepto) con su parte de la venta
    ("total", ya con descuento) y dónde quedó físicamente su dinero:
    "efectivo" (en su caja), "tarjeta" (en su Clip) y "saldo" (lo que le
    deben, o si es negativo lo que debe). Orden de desempate: receptora
    primero, especiales al final. Σ de cada columna == monto de la venta.
    """
    return _reparto(venta)[0]


# ---------------------------------------------------------------------------
# Desglose de un conjunto de ventas (dashboard / corte)
# ---------------------------------------------------------------------------

def _nombres_unicos(filas, empleados):
    """
    Dos dueñas con el mismo nombre → "Nombre (username)". Si una especial
    (p. ej. un producto borrado que se llamaba igual que una dueña) choca,
    se le agrega un número: desglose_como_dict no debe perder ninguna fila.
    """
    conteo = {}
    for f in filas:
        if not f["especial"]:
            k = f["nombre"].casefold()
            conteo[k] = conteo.get(k, 0) + 1
    for f in filas:
        if not f["especial"] and conteo[f["nombre"].casefold()] > 1:
            f["nombre"] = f"{f['nombre']} ({empleados[f['empleado_id']].user.username})"

    usados = {f["nombre"] for f in filas if not f["especial"]}
    for f in filas:
        if f["especial"]:
            base, n = f["nombre"], 2
            while f["nombre"] in usados:
                f["nombre"] = f"{base} ({n})"
                n += 1
            usados.add(f["nombre"])


def desglose_por_dueno(ventas):
    """
    Una fila por dueña (sus servicios se suman en SU fila) y filas especiales
    al final. Por construcción Σ filas == totales_caja de esas ventas.
    Pasar ventas de ventas_para_desglose() para que sean 2 queries en total.
    "productos" = total de todo lo que no es servicio, así que siempre
    total == productos + servicios.total. "efectivo" es lo que quedó en su
    caja, "tarjeta" lo que entró a su Clip y "saldo" lo que le deben (> 0)
    o debe (< 0) por cobros hechos en el Clip de otra.
    """
    return desglose_y_deudas(ventas)[0]


def desglose_y_deudas(ventas):
    """
    (filas de desglose_por_dueno, deudas entre dueñas). Las deudas salen de
    las ventas donde el Clip de la receptora recibió más de lo suyo: ella le
    debe a cada otra lo que no le alcanzó en efectivo. Se netean por pareja:
    [{"debe": nombre, "a": nombre, "debe_id": id, "a_id": id, "monto": Decimal}]
    con monto > 0; debe_id / a_id son ids de Empleado (solo hay deudas entre
    dueñas, nunca con filas especiales).
    """
    acc = {}
    empleados = {}
    debe = {}   # (clave deudora, clave acreedora) → Decimal
    for venta in ventas:
        filas_venta, emps = _reparto(venta)
        empleados.update(emps)
        receptora = None
        if any(f["grupo"].cajon_id is not None for f in filas_venta):
            receptora = ("empleado", _orden_receptora(filas_venta, emps)[0])
        for f in filas_venta:
            g = f["grupo"]
            fila = acc.get(g.clave)
            if fila is None:
                fila = acc[g.clave] = {
                    "clave": g.clave, "empleado_id": g.cajon_id, "nombre": g.nombre,
                    "especial": g.cajon_id is None,
                    "total": CERO, "efectivo": CERO, "tarjeta": CERO, "saldo": CERO,
                    "productos": CERO, "servicios": None,
                }
            fila["total"] += f["total"]
            fila["efectivo"] += f["efectivo"]
            fila["tarjeta"] += f["tarjeta"]
            fila["saldo"] += f["saldo"]
            # Solo deudas entre dueñas: lo de grupos sin dueña no es de nadie
            # (el modal lo reporta como "sin dueña", no como deuda).
            if (receptora is not None and g.cajon_id is not None
                    and g.clave != receptora and f["saldo"] > 0):
                debe[(receptora, g.clave)] = debe.get((receptora, g.clave), CERO) + f["saldo"]
            if f["concepto"] is None:
                fila["productos"] += f["total"]
                continue
            serv = fila["servicios"]
            if serv is None:
                serv = fila["servicios"] = {"total": CERO, "efectivo": CERO, "tarjeta": CERO,
                                            "conceptos": {}}
            serv["total"] += f["total"]
            serv["efectivo"] += f["efectivo"]
            serv["tarjeta"] += f["tarjeta"]
            c = serv["conceptos"].setdefault(f["concepto"], {"concepto": f["concepto"],
                                                              "cantidad": 0, "total": CERO})
            c["cantidad"] += f["cantidad"]
            c["total"] += f["total"]

    filas = list(acc.values())
    for fila in filas:
        serv = fila["servicios"]
        if serv is not None:
            serv["conceptos"] = sorted(
                serv["conceptos"].values(),
                key=lambda c: (-c["total"], c["concepto"]),
            )
            # La responsable quiere ver por separado lo cobrado como "Prod. sin
            # registro" (cobro rápido) y los servicios de verdad, por concepto.
            # "conceptos" y "total" siguen incluyendo ambos.
            es_sr = lambda c: c["concepto"].casefold() == CONCEPTO_SIN_REGISTRO.casefold()
            serv["sin_registro"] = next((c for c in serv["conceptos"] if es_sr(c)), None)
            serv["solo_servicios"] = [c for c in serv["conceptos"] if not es_sr(c)]
            serv["solo_servicios_total"] = sum((c["total"] for c in serv["solo_servicios"]), CERO)

    _nombres_unicos(filas, empleados)
    filas.sort(key=lambda f: (
        (1, _ORDEN_ESPECIALES.get(f["clave"][0], 9), f["nombre"].casefold(), "")
        if f["especial"] else
        (0, 0, f["nombre"].casefold(), str(f["empleado_id"]))
    ))

    # Neteo por pareja: si Anais le debe 60 a Yare y Yare le debe 20 a
    # Anais, queda "Anais le debe 40 a Yare".
    nombre = {f["clave"]: f["nombre"] for f in filas}
    deudas = []
    for (a, b), monto in debe.items():
        if (b, a) in debe and (b, a) < (a, b):
            continue  # la pareja ya se procesó desde el otro lado
        neto = monto - debe.get((b, a), CERO)
        if neto > 0:
            deudas.append({"debe": nombre[a], "a": nombre[b],
                           "debe_id": a[1], "a_id": b[1], "monto": neto})
        elif neto < 0:
            deudas.append({"debe": nombre[b], "a": nombre[a],
                           "debe_id": b[1], "a_id": a[1], "monto": -neto})
    deudas.sort(key=lambda d: (-d["monto"], d["debe"].casefold(), d["a"].casefold()))
    return filas, deudas


def desglose_como_dict(filas):
    """{nombre: fila} en el mismo orden (los nombres ya son únicos)."""
    return {fila["nombre"]: fila for fila in filas}


# ---------------------------------------------------------------------------
# Modal de cambio del POS
# ---------------------------------------------------------------------------

def _nombres_por_cajon(cids, empleados):
    """{cajon_id: nombre}. Mismo nombre para dos dueñas en la cuenta → se distinguen por username."""
    nombres = {cid: nombre_de(empleados[cid]) for cid in cids}
    repetidos = {n.casefold() for n in nombres.values()
                 if sum(1 for m in nombres.values() if m.casefold() == n.casefold()) > 1}
    for cid, n in nombres.items():
        if n.casefold() in repetidos:
            nombres[cid] = f"{n} ({empleados[cid].user.username})"
    return nombres


def clip_de_carrito(carrito, caja):
    """
    Aviso del modal de cobro, ANTES de cobrar: en qué Clip se cobra la
    tarjeta. Es el de la receptora (la que más vende en la cuenta), con la
    misma regla que el reparto de la venta ya guardada: base = precio ×
    cantidad de sus renglones (regalos no cuentan, servicios van a la
    responsable de servicios de la sucursal). Solo lee, no guarda nada.

    carrito: lo mismo que el POS manda a procesar_venta.
    Devuelve {"empleado_id", "nombre"}, o None si nadie en la cuenta tiene
    caja (todo sin dueña).
    """
    ids = {item.get("producto_id") for item in carrito
           if not item.get("es_servicio") and not item.get("es_regalo")}
    productos = Producto.objects.select_related("dueño__user").in_bulk([i for i in ids if i])
    responsable = caja.sucursal.dueño_servicios if caja is not None else None

    filas = []
    empleados = {}
    for item in carrito:
        if item.get("es_regalo"):
            continue
        if item.get("es_servicio"):
            emp = responsable
        else:
            producto = productos.get(item.get("producto_id"))
            emp = producto.dueño if producto is not None else None
        if emp is None:
            continue
        empleados[emp.id] = emp
        # Misma aritmética que POSService.crear_venta (float) antes de guardarse a centavos.
        base = _dec(float(item["precio_aplicado"]) * int(item["cantidad"]))
        filas.append({"grupo": Grupo(("empleado", emp.id), nombre_de(emp), emp.id, "producto"),
                      "base": base})

    if not filas:
        return None
    receptora = _orden_receptora(filas, empleados)[0]
    return {"empleado_id": receptora, "nombre": _nombres_por_cajon(empleados, empleados)[receptora]}


def reparto_efectivo_venta(venta_id):
    """
    Qué hacer físicamente con el dinero de UNA venta (modal del POS). La
    receptora (la que más vendió en la cuenta) recibe el billete, da el
    cambio y cobra la tarjeta en SU Clip; de su caja se le pasa a cada otra
    dueña lo suyo en efectivo. Si el efectivo no alcanza (p. ej. todo con
    tarjeta), la receptora queda debiendo lo que falta. Lo de grupos
    especiales (sin dueña) se queda en la caja de la receptora.

    Lee la venta de la BD (2 queries) porque el objeto en memoria tras
    POSService.crear_venta trae floats. Devuelve solo tipos JSON:
      por_duena: lo que le toca a cada quien de esta venta (ya con descuento)
      pasar:     efectivo que sale de la caja de la receptora a cada otra
      clip:      {"empleado_id","nombre","monto"} | None
      deudas:    [{"empleado_id","nombre","monto"}] lo que la receptora debe
    INVARIANTE: neto == queda_receptora + Σpasar + sin_cajon.
    """
    venta = ventas_para_desglose(Venta.objects.filter(pk=venta_id)).first()
    if venta is None:
        return None

    filas, empleados = _reparto(venta)
    neto = efectivo_neto(venta)
    tarjeta = _dec(venta.pagado_tarjeta)
    resultado = {
        "version": 2,
        "caso": "sin_efectivo",
        "recibido": float(_dec(venta.pagado_efectivo)),
        "cambio": float(_dec(venta.cambio)),
        "neto": float(neto),
        "tarjeta": float(tarjeta),
        "receptora": None,
        "por_duena": [],
        "queda_receptora": 0.0,
        "pasar": [],
        "clip": None,
        "deudas": [],
        "sin_cajon": 0.0,
    }

    # Acumulado por caja (dueña) y por fila especial.
    cajon = {}
    especiales = {}
    for f in filas:
        cid = f["grupo"].cajon_id
        destino = cajon.setdefault(cid, {}) if cid is not None \
            else especiales.setdefault(f["grupo"].nombre, {})
        for k in ("total", "efectivo", "tarjeta", "saldo"):
            destino[k] = destino.get(k, CERO) + f[k]

    sin_cajon = sum((e["efectivo"] for e in especiales.values()), CERO)
    por_especial = [{"empleado_id": None, "nombre": n, "total": float(e["total"])}
                    for n, e in especiales.items()]

    if not cajon:
        # Sin dinero (p. ej. solo regalos) no hay nada que avisar.
        caso = "sin_duena" if (neto > 0 or tarjeta > 0) else "sin_efectivo"
        resultado.update(caso=caso, sin_cajon=float(sin_cajon), por_duena=por_especial)
        return resultado

    nombres = _nombres_por_cajon(cajon, empleados)
    orden = _orden_receptora(filas, empleados)
    receptora, demas = orden[0], orden[1:]
    pasar = sorted(
        (cid for cid in demas if cajon[cid]["efectivo"] > 0),
        key=lambda cid: (-cajon[cid]["efectivo"], nombres[cid].casefold(), cid),
    )
    deudas = sorted(
        (cid for cid in demas if cajon[cid]["saldo"] > 0),
        key=lambda cid: (-cajon[cid]["saldo"], nombres[cid].casefold(), cid),
    )

    if neto == 0:
        caso = "sin_efectivo"
    elif pasar or sin_cajon:
        caso = "varias"
    else:
        caso = "una"   # no hay que pasarle efectivo a nadie

    resultado.update(
        caso=caso,
        receptora={"empleado_id": receptora, "nombre": nombres[receptora]},
        por_duena=[{"empleado_id": cid, "nombre": nombres[cid], "total": float(cajon[cid]["total"])}
                   for cid in orden] + por_especial,
        queda_receptora=float(cajon[receptora]["efectivo"]),
        pasar=[{"empleado_id": cid, "nombre": nombres[cid], "efectivo": float(cajon[cid]["efectivo"])}
               for cid in pasar],
        clip=({"empleado_id": receptora, "nombre": nombres[receptora], "monto": float(tarjeta)}
              if tarjeta > 0 else None),
        deudas=[{"empleado_id": cid, "nombre": nombres[cid], "monto": float(cajon[cid]["saldo"])}
                for cid in deudas],
        sin_cajon=float(sin_cajon),
    )
    return resultado
