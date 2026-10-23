"""
Lo que debe haber en la cajita de la responsable de servicios después de
los vales y gastos. Nunca se muestra en negativo (decisión de las dueñas):
si salió más de lo que entró por ventas, la diferencia salió del fondo.
"""
from dataclasses import dataclass
from decimal import Decimal

CERO = Decimal("0.00")


@dataclass(frozen=True)
class CajitaConSalidas:
    efectivo_ventas: Decimal   # lo que le dejó el reparto de las ventas
    vales: Decimal = CERO
    gastos: Decimal = CERO

    @property
    def salidas(self):
        return self.vales + self.gastos

    @property
    def neto(self):
        return self.efectivo_ventas - self.salidas

    @property
    def debe_haber(self):
        """Efectivo que debe haber en la cajita (sin contar el fondo). Nunca negativo."""
        return max(CERO, self.neto)

    @property
    def del_fondo(self):
        """Lo que se tuvo que sacar del fondo porque no alcanzó lo de las ventas."""
        return max(CERO, -self.neto)
