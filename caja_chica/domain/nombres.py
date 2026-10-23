"""
Nombres de las personas a las que se les da vale. No son usuarios del
sistema (no todos los empleados tienen cuenta), así que se escriben a mano;
para que no acaben "PABLO", "pablo " y "Pabblo" como tres personas:

  - Se normaliza lo que se escribe: espacios de más fuera, cada palabra con
    mayúscula inicial ("  pablo   PEREZ " → "Pablo Perez").
  - La clave para comparar ignora mayúsculas y acentos ("José" == "jose"):
    dos nombres con la misma clave son la misma persona.
  - Si la clave es nueva pero se parece a una registrada, se avisa
    (parecidos) en vez de crear otra.
"""
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from caja_chica.domain.errores import NombreInvalido

LARGO_MAXIMO = 60

# Qué tanto se tienen que parecer dos claves para avisar (0 a 1). Con 0.7:
# "pabblo"~"pablo" (0.91) y "paasloblo"~"pablo" (0.71) avisan; "ana"~"luis" no.
UMBRAL_PARECIDO = 0.7
MAX_SUGERENCIAS = 3

# Lo único que se queda de lo que escriben: letras (con acento), espacios,
# guion, punto y apóstrofo ("Ma. José", "Ana-Luisa", "O'Neil").
_NO_PERMITIDO = re.compile(r"[^\w\s.'-]|[\d_]", re.UNICODE)


def _sin_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c))


def clave_de(texto):
    """'  José  PÉREZ' → 'jose perez'. Lo que se compara para saber si es la misma persona."""
    limpio = _sin_acentos(_NO_PERMITIDO.sub(" ", texto or "")).casefold()
    return " ".join(re.sub(r"[.'-]", " ", limpio).split())


def _palabra(p):
    # "maria-jose" → "Maria-Jose": mayúscula después de cada guion o apóstrofo.
    return re.sub(r"(^|[-'])(\w)", lambda m: m.group(1) + m.group(2).upper(), p.lower())


@dataclass(frozen=True)
class NombrePersona:
    texto: str   # como se muestra: "Pablo Pérez"
    clave: str   # como se compara: "pablo perez"

    @classmethod
    def desde(cls, crudo):
        texto = " ".join(_NO_PERMITIDO.sub(" ", str(crudo or "")).split())
        if not any(c.isalpha() for c in texto):
            raise NombreInvalido("Escribe el nombre de la persona.")
        if len(texto) > LARGO_MAXIMO:
            raise NombreInvalido(f"El nombre es muy largo (máximo {LARGO_MAXIMO} letras).")
        texto = " ".join(_palabra(p) for p in texto.split(" "))
        return cls(texto=texto, clave=clave_de(texto))


def _parecido(a, b):
    return SequenceMatcher(None, a, b).ratio()


def parecidos(clave, registradas):
    """
    Las registradas que se parecen a `clave` (sin ser la misma), de la más a
    la menos parecida. `registradas`: [(id, nombre, clave)]. Si se escribió
    una sola palabra también se compara contra el primer nombre ("pabblo" ~
    "Pablo Pérez").
    """
    una_palabra = " " not in clave
    puntajes = []
    for pid, nombre, otra in registradas:
        if otra == clave:
            continue
        puntaje = _parecido(clave, otra)
        if una_palabra:
            puntaje = max(puntaje, _parecido(clave, otra.split(" ")[0]))
        if puntaje >= UMBRAL_PARECIDO:
            puntajes.append((-puntaje, nombre.casefold(), {"id": pid, "nombre": nombre}))
    return [s for *_, s in sorted(puntajes, key=lambda t: t[:2])][:MAX_SUGERENCIAS]
