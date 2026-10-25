"""
Precios por cantidad (Media docena, Decena, Caja) de cada producto.

Aquí viven TODAS las reglas; las usan el alta y el detalle del producto, la
Lista de precios y el POS. Las vistas solo traducen la petición y llaman a
estas funciones. Ver el modelo en inventario.models.Presentacion.

Forma de una fila (la manda el navegador y la regresa este servicio):
    {"tipo": "caja", "piezas": 24, "precio": "550"}
Media docena y Decena traen sus piezas fijas: si el navegador manda otras,
se ignoran.

Solo las dueñas ponen o cambian estos precios (ver puede_editar).
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from inventario.models import Presentacion, Producto, TipoPresentacion

PIEZAS_FIJAS = {
    TipoPresentacion.MEDIA_DOCENA: 6,
    TipoPresentacion.DECENA: 10,
}
PIEZAS_MINIMAS_CAJA = 2
PRECIO_MAXIMO = Decimal("999999999.9")   # max_digits=10, decimal_places=1


def puede_editar(empleado):
    return getattr(empleado, "rol", None) == "dueño"


@dataclass(frozen=True)
class PrecioCantidad:
    tipo: str
    piezas: int
    precio: Decimal

    @property
    def clave(self):
        return (self.tipo, self.piezas)

    @property
    def nombre(self):
        return Presentacion(tipo=self.tipo, piezas=self.piezas).nombre

    def como_dict(self):
        return {"tipo": self.tipo, "piezas": self.piezas, "precio": _texto_precio(self.precio),
                "nombre": self.nombre}


def _texto_precio(precio):
    """'550' o '27.5': sin ceros de más, como se escribió."""
    texto = format(precio.normalize(), "f")
    return texto


# ============================================================
# LEER Y VALIDAR
# ============================================================

def leer_filas(filas):
    """
    Convierte las filas que manda el navegador en PrecioCantidad validados.
    Una fila sin precio se ignora (se agregó y no se llenó). Si algo está mal
    lanza ValidationError con un mensaje por problema, en palabras simples.
    """
    if filas in (None, ""):
        return []
    if not isinstance(filas, list):
        raise ValidationError("Los precios por caja llegaron mal. Recarga la página.")

    errores = []
    leidas = []
    for fila in filas:
        if not isinstance(fila, dict):
            errores.append("Los precios por caja llegaron mal. Recarga la página.")
            continue

        tipo = fila.get("tipo")
        if tipo not in TipoPresentacion.values:
            errores.append("Ese tipo de precio no existe.")
            continue
        etiqueta = TipoPresentacion(tipo).label

        precio_texto = str(fila.get("precio") if fila.get("precio") is not None else "").strip()
        if not precio_texto:
            continue

        try:
            precio = Decimal(precio_texto)
        except InvalidOperation:
            errores.append(f"{etiqueta}: el precio no es un número.")
            continue
        if not precio.is_finite() or precio <= 0:
            errores.append(f"{etiqueta}: el precio tiene que ser mayor a $0.")
            continue
        if precio > PRECIO_MAXIMO:
            errores.append(f"{etiqueta}: el precio es demasiado grande.")
            continue
        precio = precio.quantize(Decimal("0.1"))

        if tipo in PIEZAS_FIJAS:
            piezas = PIEZAS_FIJAS[tipo]
        else:
            try:
                piezas = int(str(fila.get("piezas") or "").strip())
            except ValueError:
                errores.append("Caja: escribe cuántas piezas trae.")
                continue
            if piezas < PIEZAS_MINIMAS_CAJA:
                errores.append(f"Caja: tiene que traer {PIEZAS_MINIMAS_CAJA} piezas o más.")
                continue

        leidas.append(PrecioCantidad(tipo=tipo, piezas=piezas, precio=precio))

    vistas = set()
    for p in leidas:
        if p.clave in vistas:
            errores.append(f"{p.nombre} está dos veces. Deja solo uno.")
        vistas.add(p.clave)

    if errores:
        raise ValidationError(list(dict.fromkeys(errores)))
    return leidas


# ============================================================
# CONSULTAR
# ============================================================

def de_producto(producto):
    """Precios por cantidad actuales del producto, como dicts para el navegador."""
    return [
        PrecioCantidad(p.tipo, p.piezas, p.precio).como_dict() | {"id": p.id}
        for p in producto.presentaciones.all()
    ]


def ultimo_registrado_por(empleado):
    """
    El último producto que registró este empleado y que tiene precios por
    cantidad: para "Usar los del último que registraste" en el alta.
    """
    if empleado is None:
        return None
    return (
        Producto.objects
        .filter(registrado_por=empleado, presentaciones__isnull=False)
        .order_by("-fecha_registro", "-id")
        .prefetch_related("presentaciones")
        .distinct()
        .first()
    )


def para_venta(producto_id, presentacion_id):
    """
    El precio por cantidad con que el POS va a cobrar. Lanza ValueError (el
    POS lo convierte en un 400 con mensaje) si no es de ese producto o ya
    no existe.
    """
    try:
        return Presentacion.objects.get(pk=int(presentacion_id), producto_id=int(producto_id))
    except (Presentacion.DoesNotExist, TypeError, ValueError):
        raise ValueError("Ese precio ya no existe. Quita el producto de la cuenta y vuélvelo a pasar.")


# ============================================================
# GUARDAR
# ============================================================

def guardar_de_producto(producto, filas):
    """
    Deja al producto exactamente con estos precios por cantidad: agrega los
    nuevos, cambia el precio de los que ya tenía y quita los que ya no
    vienen. Los que no cambian conservan su id, así una caja que ya está en
    un carrito del POS sigue valiendo. Regresa {"nuevos", "cambiados",
    "quitados"}. `filas` ya vienen de leer_filas().
    """
    actuales = {(p.tipo, p.piezas): p for p in producto.presentaciones.all()}
    nuevas = {f.clave: f for f in filas}
    resumen = {"nuevos": 0, "cambiados": 0, "quitados": 0}

    quitar = [p.id for clave, p in actuales.items() if clave not in nuevas]
    if quitar:
        Presentacion.objects.filter(id__in=quitar).delete()
        resumen["quitados"] = len(quitar)

    for clave, fila in nuevas.items():
        actual = actuales.get(clave)
        if actual is None:
            Presentacion.objects.create(producto=producto, tipo=fila.tipo, piezas=fila.piezas,
                                        precio=fila.precio)
            resumen["nuevos"] += 1
        elif actual.precio != fila.precio:
            actual.precio = fila.precio
            actual.save(update_fields=["precio"])
            resumen["cambiados"] += 1

    if any(resumen.values()):
        _avisar_al_pos(producto)
    return resumen


class ListaConErrores(Exception):
    """La Lista de precios no se guardó. `errores` = {producto_id: [mensajes]}."""

    def __init__(self, errores):
        super().__init__("La lista tiene errores")
        self.errores = errores


@transaction.atomic
def guardar_lista(renglones):
    """
    Guarda la Lista de precios completa, todo o nada.

    renglones = [{"producto_id": 5, "originales": [filas como estaban al
    escanear], "presentaciones": [filas como deben quedar]}]

    Si otra persona cambió los precios por cantidad de un producto mientras
    se armaba la lista, ese renglón se marca en lugar de pisar el cambio.
    Lanza ListaConErrores si algún renglón falla; nada se guarda.
    """
    if not isinstance(renglones, list) or not renglones:
        raise ValidationError("La lista está vacía.")

    por_producto = {}
    errores = {}
    for r in renglones:
        try:
            producto_id = int(r.get("producto_id"))
        except (AttributeError, TypeError, ValueError):
            raise ValidationError("La lista llegó mal. Recarga la página.")
        if producto_id in por_producto:
            errores[producto_id] = ["Este producto está dos veces en la lista."]
            continue
        try:
            nuevas = leer_filas(r.get("presentaciones"))
            originales = leer_filas(r.get("originales"))
        except ValidationError as e:
            errores[producto_id] = e.messages
            continue
        por_producto[producto_id] = (originales, nuevas)

    productos = {
        p.id: p for p in
        Producto.objects.select_for_update().filter(id__in=por_producto.keys())
    }
    for producto_id, (originales, _) in por_producto.items():
        producto = productos.get(producto_id)
        if producto is None:
            errores[producto_id] = ["Este producto ya no existe."]
            continue
        actuales = {(p.tipo, p.piezas, p.precio) for p in producto.presentaciones.all()}
        if actuales != {(o.tipo, o.piezas, o.precio) for o in originales}:
            errores[producto_id] = [
                "Alguien más cambió los precios de este producto. Quítalo de la lista y vuelve a escanearlo."
            ]

    if errores:
        raise ListaConErrores(errores)

    total = {"productos": 0, "nuevos": 0, "cambiados": 0, "quitados": 0}
    for producto_id, (_, nuevas) in por_producto.items():
        resumen = guardar_de_producto(productos[producto_id], nuevas)
        if any(resumen.values()):
            total["productos"] += 1
        for k, v in resumen.items():
            total[k] += v
    return total


def _avisar_al_pos(producto):
    """Al confirmar, el POS recibe los precios nuevos por websocket."""
    from inventario.signals import _broadcast_producto
    transaction.on_commit(lambda: _broadcast_producto(producto))
