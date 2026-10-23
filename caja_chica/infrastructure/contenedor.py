"""
Raíz de composición: aquí, y solo aquí, se juntan los casos de uso con los
repositorios de Django. Las vistas y api.py piden sus casos de uso a este
módulo; los tests de casos de uso los arman con repositorios en memoria.
"""
from caja_chica.application import casos_uso as cu
from caja_chica.infrastructure.repositorios import CajitasDjango, MovimientosDjango, PersonasDjango


def registrar_vale():
    return cu.RegistrarVale(PersonasDjango(), MovimientosDjango(), CajitasDjango())


def registrar_gasto():
    return cu.RegistrarGasto(MovimientosDjango(), CajitasDjango())


def cambiar_monto():
    return cu.CambiarMonto(MovimientosDjango())


def eliminar_movimiento():
    return cu.EliminarMovimiento(MovimientosDjango())


def listar_personas():
    return cu.ListarPersonas(PersonasDjango())


def lo_sin_corte_de_caja():
    return cu.LoSinCorteDeCaja(MovimientosDjango())


def resumen_de_semana():
    return cu.ResumenDeSemana(MovimientosDjango())


def salidas_del_corte():
    return cu.SalidasDelCorte(MovimientosDjango())


def salidas_del_dia():
    return cu.SalidasDelDia(MovimientosDjango())


def asignar_a_corte():
    return cu.AsignarACorte(MovimientosDjango())


def cajita_de(caja_id):
    """Dueña de la cajita de esa caja (Duena | None)."""
    return CajitasDjango().duena_de(caja_id)
