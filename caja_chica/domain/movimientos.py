"""
Movimientos de la caja chica: dinero que sale de la cajita de la responsable
de servicios sin ser una venta.

  VALE   se le prestó dinero a una persona (a quién y cuánto).
  GASTO  se compró algo para la tienda (qué y cuánto costó).

Los dos se le descuentan a la dueña de la cajita y salen en su corte.
"""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from enum import Enum

from caja_chica.domain.errores import DescripcionInvalida, MontoInvalido

CENT = Decimal("0.01")
MONTO_MAXIMO = Decimal("50000.00")
DESCRIPCION_MAXIMA = 150


class TipoMovimiento(str, Enum):
    VALE = "vale"
    GASTO = "gasto"


def monto_valido(crudo):
    """Lo que escribieron → Decimal a centavos. Tiene que ser más de $0 y no más de MONTO_MAXIMO."""
    try:
        monto = Decimal(str(crudo).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError):
        raise MontoInvalido("Escribe cuánto fue, solo con números.") from None
    if not monto.is_finite():
        raise MontoInvalido("Escribe cuánto fue, solo con números.")
    monto = monto.quantize(CENT, rounding=ROUND_HALF_UP)
    if monto <= 0:
        raise MontoInvalido("La cantidad tiene que ser mayor a $0.")
    if monto > MONTO_MAXIMO:
        raise MontoInvalido(f"Es demasiado (máximo ${MONTO_MAXIMO:,.2f}). Revisa que no sobre un cero.")
    return monto


def descripcion_valida(crudo):
    """' coca   para el repartidor ' → 'Coca para el repartidor'."""
    texto = " ".join(str(crudo or "").split())
    if not texto:
        raise DescripcionInvalida("Escribe qué compraste.")
    if len(texto) > DESCRIPCION_MAXIMA:
        raise DescripcionInvalida(f"Es muy largo (máximo {DESCRIPCION_MAXIMA} letras).")
    return texto[0].upper() + texto[1:]


@dataclass(frozen=True)
class Movimiento:
    """Un vale o un gasto ya registrado, como lo ven los casos de uso."""
    id: int
    tipo: TipoMovimiento
    monto: Decimal
    fecha: datetime
    caja_id: int | None
    caja_nombre: str
    descontado_a_id: int | None     # dueña de la cajita de la que salió
    descontado_a_nombre: str
    registrado_por_nombre: str
    persona_id: int | None = None   # solo vales
    persona_nombre: str = ""        # solo vales
    descripcion: str = ""           # solo gastos
    corte_id: int | None = None     # en qué corte quedó (None: todavía no se corta)
    monto_original: Decimal | None = None   # si una dueña le cambió el monto

    @property
    def concepto(self):
        """Lo que se muestra: a quién (vale) o qué (gasto)."""
        return self.persona_nombre if self.tipo is TipoMovimiento.VALE else self.descripcion
