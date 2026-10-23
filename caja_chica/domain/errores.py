"""
Errores de la caja chica. El mensaje es el que se le muestra al personal, así
que va en palabras simples (le habla a la cajera).
"""


class ErrorCajaChica(Exception):
    """Base: algo que el personal puede corregir. str(error) es el mensaje para la pantalla."""


class NombreInvalido(ErrorCajaChica):
    pass


class MontoInvalido(ErrorCajaChica):
    pass


class DescripcionInvalida(ErrorCajaChica):
    pass


class NombreParecido(ErrorCajaChica):
    """
    El nombre nuevo se parece a uno ya registrado (Pablo / pabblo). No se
    guarda nada: la cajera elige el registrado o confirma que es otra persona.
    """

    def __init__(self, sugerencias):
        super().__init__("Ya hay alguien con un nombre parecido. ¿Es alguno de estos?")
        self.sugerencias = sugerencias   # [{"id", "nombre"}]


class SinCajita(ErrorCajaChica):
    def __init__(self):
        super().__init__("Esta caja no tiene responsable de servicios. Avísale a una dueña.")


class SinPermiso(ErrorCajaChica):
    pass


class NoEncontrado(ErrorCajaChica):
    def __init__(self, que="Eso"):
        super().__init__(f"{que} ya no existe.")
