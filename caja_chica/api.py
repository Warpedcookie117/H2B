"""
Lo ÚNICO de la caja chica que usan las otras apps (el corte de ventas y el
dashboard de las dueñas). Si cambia cómo se guarda la caja chica, esto no
cambia.
"""
from caja_chica.domain.cajita import CERO, CajitaConSalidas  # noqa: F401  (se re-exporta)
from caja_chica.domain.semanas import semana_de
from caja_chica.infrastructure import contenedor


def al_cerrar_corte(corte, hasta, dia=None):
    """
    Liga al corte lo de la caja chica de su caja que no tenía corte, hasta
    `hasta` (y de ese día local si viene: el corte automático es de un día).
    """
    if corte.caja_id is None:
        return 0
    return contenedor.asignar_a_corte()(corte.caja_id, corte.id, hasta, dia)


def salidas_del_corte(corte_id):
    """{duena_id: SalidasDeDuena} de lo que salió de cada cajita en ese corte."""
    return contenedor.salidas_del_corte()(corte_id)


def salidas_del_dia(duena_id, dia):
    """{caja_id: Decimal} de lo que salió ese día de la cajita de esa dueña."""
    return contenedor.salidas_del_dia()(duena_id, dia)


def semanas_para_dashboard(hoy):
    """[esta semana, la pasada] como ResumenSemana (lunes a domingo)."""
    resumen = contenedor.resumen_de_semana()
    return [resumen(*semana_de(hoy, atras=n)) for n in (0, 1)]
