"""
Casos de uso de la caja chica. Cada uno hace UNA cosa y recibe sus puertos
en el constructor (infrastructure/contenedor.py los arma con Django).
"""
from dataclasses import dataclass, field

from caja_chica.application.puertos import Cajitas, Movimientos, NuevoMovimiento, Personas
from caja_chica.domain.cajita import CERO
from caja_chica.domain.errores import NoEncontrado, NombreParecido, SinCajita
from caja_chica.domain.movimientos import TipoMovimiento, descripcion_valida, monto_valido
from caja_chica.domain.nombres import NombrePersona, parecidos
from caja_chica.domain.permisos import exigir_puede_corregir, exigir_puede_registrar


def _duena_de_cajita(cajitas, caja_id):
    duena = cajitas.duena_de(caja_id)
    if duena is None:
        raise SinCajita()
    return duena


# ---------------------------------------------------------------------------
# Registrar (cajera o dueña en caja)
# ---------------------------------------------------------------------------

class RegistrarVale:
    """
    Vale para una persona. El nombre se toma de la lista (persona_id) o se
    escribe; si se escribe uno nuevo que se parece a uno registrado, NO se
    guarda: NombreParecido con sugerencias, y la cajera elige el registrado o
    vuelve a mandar con es_otra_persona=True.
    """

    def __init__(self, personas: Personas, movimientos: Movimientos, cajitas: Cajitas):
        self.personas = personas
        self.movimientos = movimientos
        self.cajitas = cajitas

    def __call__(self, actor, caja_id, monto, nombre="", persona_id=None, es_otra_persona=False):
        exigir_puede_registrar(actor, caja_id)
        monto = monto_valido(monto)
        duena = _duena_de_cajita(self.cajitas, caja_id)
        persona = self._persona(actor, nombre, persona_id, es_otra_persona)
        return self.movimientos.registrar(NuevoMovimiento(
            tipo=TipoMovimiento.VALE, monto=monto, caja_id=caja_id, descontado_a=duena,
            registrado_por_id=actor.id, persona_id=persona.id,
        ))

    def _persona(self, actor, nombre, persona_id, es_otra_persona):
        if persona_id is not None:
            persona = self.personas.por_id(persona_id)
            if persona is None:
                raise NoEncontrado("Esa persona")
            return persona
        nombre = NombrePersona.desde(nombre)
        persona = self.personas.por_clave(nombre.clave)
        if persona is not None:
            return persona
        if not es_otra_persona:
            sugerencias = parecidos(nombre.clave, [(p.id, p.nombre, p.clave) for p in self.personas.todas()])
            if sugerencias:
                raise NombreParecido(sugerencias)
        return self.personas.crear(nombre, actor.id)


class RegistrarGasto:
    """'¿Compraste algo?': qué y cuánto costó."""

    def __init__(self, movimientos: Movimientos, cajitas: Cajitas):
        self.movimientos = movimientos
        self.cajitas = cajitas

    def __call__(self, actor, caja_id, monto, descripcion):
        exigir_puede_registrar(actor, caja_id)
        monto = monto_valido(monto)
        descripcion = descripcion_valida(descripcion)
        duena = _duena_de_cajita(self.cajitas, caja_id)
        return self.movimientos.registrar(NuevoMovimiento(
            tipo=TipoMovimiento.GASTO, monto=monto, caja_id=caja_id, descontado_a=duena,
            registrado_por_id=actor.id, descripcion=descripcion,
        ))


# ---------------------------------------------------------------------------
# Corregir (solo dueñas)
# ---------------------------------------------------------------------------

class CambiarMonto:
    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, actor, movimiento_id, monto):
        exigir_puede_corregir(actor)
        monto = monto_valido(monto)
        self.movimientos.obtener(movimiento_id)   # NoEncontrado si ya no está
        return self.movimientos.cambiar_monto(movimiento_id, monto, actor.id)


class EliminarMovimiento:
    """Ese dinero vuelve a contar como de la dueña de la cajita (deja de descontarse)."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, actor, movimiento_id):
        exigir_puede_corregir(actor)
        self.movimientos.obtener(movimiento_id)
        self.movimientos.eliminar(movimiento_id, actor.id)


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

class ListarPersonas:
    """Las personas registradas, sin repetidos (la clave es única), en orden alfabético."""

    def __init__(self, personas: Personas):
        self.personas = personas

    def __call__(self):
        return sorted(self.personas.todas(), key=lambda p: p.clave)


class LoSinCorteDeCaja:
    """Lo registrado en esa caja que todavía no entra en un corte (lista del modal)."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, caja_id):
        return sorted(self.movimientos.sin_corte_de_caja(caja_id), key=lambda m: m.fecha, reverse=True)


@dataclass
class ValesDePersona:
    persona: str
    vales: list = field(default_factory=list)

    @property
    def total(self):
        return sum((v.monto for v in self.vales), CERO)


@dataclass
class ResumenSemana:
    desde: object
    hasta: object
    personas: list   # [ValesDePersona], de la que más debe a la que menos
    gastos: list     # [Movimiento], del más nuevo al más viejo

    @property
    def total_vales(self):
        return sum((p.total for p in self.personas), CERO)

    @property
    def total_gastos(self):
        return sum((g.monto for g in self.gastos), CERO)


class ResumenDeSemana:
    """Vales por persona y gastos de una semana (lunes a domingo) para el dashboard."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, desde, hasta):
        por_persona = {}
        gastos = []
        for m in sorted(self.movimientos.entre_dias(desde, hasta), key=lambda m: m.fecha, reverse=True):
            if m.tipo is TipoMovimiento.VALE:
                por_persona.setdefault(m.persona_id, ValesDePersona(m.persona_nombre)).vales.append(m)
            else:
                gastos.append(m)
        personas = sorted(por_persona.values(), key=lambda p: (-p.total, p.persona.casefold()))
        return ResumenSemana(desde, hasta, personas, gastos)


@dataclass
class SalidasDeDuena:
    """Lo que salió de la cajita de una dueña (en un corte o en un día)."""
    duena_id: int
    duena_nombre: str
    vales: list = field(default_factory=list)
    gastos: list = field(default_factory=list)

    @property
    def total_vales(self):
        return sum((v.monto for v in self.vales), CERO)

    @property
    def total_gastos(self):
        return sum((g.monto for g in self.gastos), CERO)

    @property
    def total(self):
        return self.total_vales + self.total_gastos


def _por_duena(movimientos):
    """{duena_id: SalidasDeDuena}, en orden de fecha."""
    salidas = {}
    for m in sorted(movimientos, key=lambda m: (m.fecha, m.id)):
        s = salidas.setdefault(m.descontado_a_id, SalidasDeDuena(m.descontado_a_id, m.descontado_a_nombre))
        (s.vales if m.tipo is TipoMovimiento.VALE else s.gastos).append(m)
    return salidas


class SalidasDelCorte:
    """{duena_id: SalidasDeDuena} de un corte: lo que se le descuenta a su cajita."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, corte_id):
        return _por_duena(self.movimientos.del_corte(corte_id))


class SalidasDelDia:
    """{caja_id: Decimal} de lo que salió hoy de la cajita de esa dueña, caja por caja."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, duena_id, dia):
        por_caja = {}
        for m in self.movimientos.del_dia(duena_id, dia):
            por_caja[m.caja_id] = por_caja.get(m.caja_id, CERO) + m.monto
        return por_caja


class AsignarACorte:
    """Al cerrar un corte, lo de la caja chica sin corte de esa caja queda en él."""

    def __init__(self, movimientos: Movimientos):
        self.movimientos = movimientos

    def __call__(self, caja_id, corte_id, hasta, dia=None):
        return self.movimientos.asignar_corte(caja_id, corte_id, hasta, dia)

