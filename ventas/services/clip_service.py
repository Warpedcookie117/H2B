"""
En qué Clip se cobra la tarjeta de una cuenta (regla de las dueñas, oct-2026).

La que más vende en la cuenta (la receptora) cobra la tarjeta en SU Clip y,
de su cajita, les paga en efectivo a las demás en ese momento (pago en seco,
ver reparto._repartir_fisico). Si su cajita no tiene con qué, la tarjeta se
cobra en el Clip de la responsable de servicios de la sucursal (su cajita es
la del fondo) y ella les paga a todas. Así ninguna otra cajita queda en
negativo en el corte.

"Lo que tiene su cajita" es la misma cuenta del corte: su efectivo en esa
caja desde el último corte. No cuenta el fondo (no está configurado) ni lo
que se saque a mano fuera del sistema. El efectivo que entra en la misma
venta también cuenta: si el cliente paga parte en efectivo, con eso se les
paga a las demás primero.
"""
from ventas.services.corte_service import ventas_pendientes_de_corte
from ventas.services.reparto import (
    CERO,
    desglose_por_dueno,
    nombre_de,
    receptora_de_carrito,
    ventas_para_desglose,
)


def responsable_de_cajita(caja):
    """Dueña de la cajita de default (la del fondo): la responsable de servicios de la sucursal."""
    return caja.sucursal.dueño_servicios if caja is not None else None


def efectivo_en_cajita(empleado_id, caja):
    """Efectivo de esa dueña en su cajita de `caja` desde el último corte, como lo imprimiría el corte."""
    filas = desglose_por_dueno(ventas_para_desglose(ventas_pendientes_de_corte(caja)))
    return next((f["efectivo"] for f in filas if f["empleado_id"] == empleado_id), CERO)


def opciones_de_clip(carrito, caja):
    """
    Lo que necesita el modal de cobro para decir en qué Clip se cobra, antes
    de saber cuánto pagan con tarjeta:
      {"empleado_id", "nombre"}  la que más vende (el Clip normal)
      "respaldo":  {"empleado_id", "nombre"} de la responsable de servicios,
                   o None si nunca hace falta
      "le_falta":  efectivo que tiene que entrar en esta venta para que la
                   cajita de la que más vende alcance a pagarles a las demás
    Se usa el respaldo cuando lo que entra en efectivo (total - tarjeta) es
    menor que "le_falta" (ver clip_que_toca). None si nadie en la cuenta
    tiene caja (todo sin dueña).
    """
    r = receptora_de_carrito(carrito, caja)
    if r is None:
        return None
    emp = r["empleado"]
    opciones = {"empleado_id": emp.id, "nombre": r["nombre"], "respaldo": None, "le_falta": 0.0}
    responsable = responsable_de_cajita(caja)
    if responsable is None or responsable.id == emp.id or r["para_las_demas"] <= 0:
        return opciones
    le_falta = r["para_las_demas"] - efectivo_en_cajita(emp.id, caja)
    if le_falta > 0:
        opciones["respaldo"] = {"empleado_id": responsable.id, "nombre": nombre_de(responsable)}
        opciones["le_falta"] = float(le_falta)
    return opciones


def clip_que_toca(opciones, efectivo_que_entra):
    """empleado_id del Clip donde se cobra, según lo que entra en efectivo en la venta."""
    if opciones["respaldo"] is not None and efectivo_que_entra < opciones["le_falta"]:
        return opciones["respaldo"]["empleado_id"]
    return opciones["empleado_id"]


def clip_de_la_venta(carrito, caja, efectivo_que_entra, mostrado_id=None):
    """
    empleado_id que se guarda en Venta.clip_de al cobrar con tarjeta. Si el
    POS manda el Clip que le mostró a la cajera (ahí ya pasaron la tarjeta)
    y es uno de los posibles para este carrito, se respeta; si no viene o no
    es válido, se calcula con lo que entró en efectivo. None si nadie en la
    cuenta tiene caja.
    """
    opciones = opciones_de_clip(carrito, caja)
    if opciones is None:
        return None
    posibles = {opciones["empleado_id"]}
    if opciones["respaldo"] is not None:
        posibles.add(opciones["respaldo"]["empleado_id"])
    if mostrado_id in posibles:
        return mostrado_id
    return clip_que_toca(opciones, efectivo_que_entra)
