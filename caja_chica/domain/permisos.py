"""
Quién puede hacer qué (decisión de las dueñas, oct-2026):
  - Registrar vales y gastos: cualquiera que esté en una caja (cajera o dueña).
  - Cambiar el monto o eliminar: solo las dueñas. La cajera no puede borrar.
"""
from dataclasses import dataclass

from caja_chica.domain.errores import SinPermiso

ROLES_EN_CAJA = ("cajero", "dueño")
ROL_DUENA = "dueño"


@dataclass(frozen=True)
class Actor:
    """Quien hace la acción (el Empleado de la sesión)."""
    id: int
    nombre: str
    rol: str


def exigir_puede_registrar(actor, caja_id):
    if actor.rol not in ROLES_EN_CAJA:
        raise SinPermiso("Solo quien está en caja puede registrar vales y gastos.")
    if caja_id is None:
        raise SinPermiso("Entra a una caja para registrar vales y gastos.")


def exigir_puede_corregir(actor):
    if actor.rol != ROL_DUENA:
        raise SinPermiso("Solo una dueña puede cambiar o borrar un vale o un gasto.")
