"""
Puertos: lo que los casos de uso necesitan del mundo de afuera, sin saber
cómo se guarda. infrastructure/repositorios.py los cumple con Django; los
tests de casos de uso los cumplen en memoria.
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from caja_chica.domain.movimientos import Movimiento, TipoMovimiento
from caja_chica.domain.nombres import NombrePersona


@dataclass(frozen=True)
class Persona:
    id: int
    nombre: str
    clave: str


@dataclass(frozen=True)
class Duena:
    id: int
    nombre: str


@dataclass(frozen=True)
class NuevoMovimiento:
    tipo: TipoMovimiento
    monto: Decimal
    caja_id: int
    descontado_a: Duena
    registrado_por_id: int
    persona_id: int | None = None
    descripcion: str = ""


class Personas(Protocol):
    def todas(self) -> list[Persona]: ...
    def por_id(self, persona_id: int) -> Persona | None: ...
    def por_clave(self, clave: str) -> Persona | None: ...
    def crear(self, nombre: NombrePersona, creada_por_id: int) -> Persona:
        """Si otra cajera la acaba de crear con la misma clave, devuelve esa."""
        ...


class Movimientos(Protocol):
    def registrar(self, nuevo: NuevoMovimiento) -> Movimiento: ...
    def obtener(self, movimiento_id: int) -> Movimiento:
        """NoEncontrado si no existe o ya se eliminó."""
        ...
    def cambiar_monto(self, movimiento_id: int, monto: Decimal, actor_id: int) -> Movimiento: ...
    def eliminar(self, movimiento_id: int, actor_id: int) -> None: ...
    def sin_corte_de_caja(self, caja_id: int) -> list[Movimiento]: ...
    def del_corte(self, corte_id: int) -> list[Movimiento]: ...
    def asignar_corte(self, caja_id: int, corte_id: int, hasta, dia=None) -> int:
        """Los sin corte de esa caja hasta `hasta` (y de ese día local, si viene)."""
        ...
    def entre_dias(self, desde, hasta) -> list[Movimiento]:
        """Por día local, ambos inclusive."""
        ...
    def del_dia(self, descontado_a_id: int, dia) -> list[Movimiento]: ...


class Cajitas(Protocol):
    def duena_de(self, caja_id: int) -> Duena | None:
        """De quién es la cajita de la que sale la caja chica de esa caja (la responsable de servicios)."""
        ...
