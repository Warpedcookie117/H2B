"""Semanas de lunes a domingo: los vales se revisan el domingo."""
from datetime import timedelta


def semana_de(dia, atras=0):
    """(lunes, domingo) de la semana de `dia`; atras=1 es la semana anterior."""
    lunes = dia - timedelta(days=dia.weekday()) - timedelta(weeks=atras)
    return lunes, lunes + timedelta(days=6)
