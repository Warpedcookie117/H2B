"""
Repositorios de Django: cumplen los puertos de application/puertos.py y
traducen entre los modelos y las entidades del dominio. Aquí sí se sabe de
la base de datos; en los casos de uso no.
"""
from django.db import IntegrityError, transaction
from django.utils import timezone

from caja_chica.application.puertos import Duena, Persona
from caja_chica.domain.errores import NoEncontrado
from caja_chica.domain.movimientos import Movimiento, TipoMovimiento
from caja_chica.models import MovimientoCaja, PersonaVale


def _nombre_de_empleado(emp):
    if emp is None:
        return ""
    return (emp.user.first_name or "").strip() or emp.user.username


def _a_persona(p):
    return Persona(id=p.id, nombre=p.nombre, clave=p.clave)


def _a_movimiento(m):
    return Movimiento(
        id=m.id,
        tipo=TipoMovimiento(m.tipo),
        monto=m.monto,
        fecha=m.fecha,
        caja_id=m.caja_id,
        caja_nombre=m.caja_nombre,
        descontado_a_id=m.descontado_a_id,
        descontado_a_nombre=m.descontado_a_nombre,
        registrado_por_nombre=m.registrado_por_nombre,
        persona_id=m.persona_id,
        persona_nombre=m.persona.nombre if m.persona_id else "",
        descripcion=m.descripcion,
        corte_id=m.corte_id,
        monto_original=m.monto_original,
    )


class PersonasDjango:

    def todas(self):
        return [_a_persona(p) for p in PersonaVale.objects.all()]

    def por_id(self, persona_id):
        p = PersonaVale.objects.filter(pk=persona_id).first()
        return _a_persona(p) if p else None

    def por_clave(self, clave):
        p = PersonaVale.objects.filter(clave=clave).first()
        return _a_persona(p) if p else None

    def crear(self, nombre, creada_por_id):
        try:
            with transaction.atomic():
                p = PersonaVale.objects.create(nombre=nombre.texto, clave=nombre.clave,
                                               creada_por_id=creada_por_id)
        except IntegrityError:
            # Otra cajera la acaba de crear: es la misma persona.
            p = PersonaVale.objects.get(clave=nombre.clave)
        return _a_persona(p)


class MovimientosDjango:

    def _vivos(self):
        return MovimientoCaja.objects.filter(eliminado_en__isnull=True).select_related("persona")

    def registrar(self, nuevo):
        from sucursales.models import Caja
        from tienda_temp.models import Empleado

        caja = Caja.objects.filter(pk=nuevo.caja_id).first()
        quien = Empleado.objects.select_related("user").filter(pk=nuevo.registrado_por_id).first()
        m = MovimientoCaja.objects.create(
            tipo=nuevo.tipo.value,
            monto=nuevo.monto,
            persona_id=nuevo.persona_id,
            descripcion=nuevo.descripcion,
            caja=caja,
            caja_nombre=caja.nombre if caja else "",
            descontado_a_id=nuevo.descontado_a.id,
            descontado_a_nombre=nuevo.descontado_a.nombre[:150],
            registrado_por=quien,
            registrado_por_nombre=_nombre_de_empleado(quien)[:150],
        )
        return self.obtener(m.pk)

    def obtener(self, movimiento_id):
        m = self._vivos().filter(pk=movimiento_id).first()
        if m is None:
            raise NoEncontrado("Ese vale o gasto")
        return _a_movimiento(m)

    def cambiar_monto(self, movimiento_id, monto, actor_id):
        with transaction.atomic():
            m = self._vivos().select_for_update().get(pk=movimiento_id)
            if m.monto != monto:
                if m.monto_original is None:
                    m.monto_original = m.monto
                m.monto = monto
                m.editado_por_id = actor_id
                m.editado_en = timezone.now()
                m.save(update_fields=["monto", "monto_original", "editado_por", "editado_en"])
        return self.obtener(movimiento_id)

    def eliminar(self, movimiento_id, actor_id):
        self._vivos().filter(pk=movimiento_id).update(eliminado_por_id=actor_id, eliminado_en=timezone.now())

    def sin_corte_de_caja(self, caja_id):
        return [_a_movimiento(m) for m in self._vivos().filter(caja_id=caja_id, corte__isnull=True)]

    def del_corte(self, corte_id):
        return [_a_movimiento(m) for m in self._vivos().filter(corte_id=corte_id)]

    def asignar_corte(self, caja_id, corte_id, hasta, dia=None):
        # Los eliminados también se ligan: si una dueña los regresa a mano en
        # el admin, ya saben a qué corte pertenecen.
        qs = MovimientoCaja.objects.filter(caja_id=caja_id, corte__isnull=True, fecha__lte=hasta)
        if dia is not None:
            qs = qs.filter(fecha__date=dia)
        return qs.update(corte_id=corte_id)

    def entre_dias(self, desde, hasta):
        return [_a_movimiento(m) for m in self._vivos().filter(fecha__date__gte=desde, fecha__date__lte=hasta)]

    def del_dia(self, descontado_a_id, dia):
        return [_a_movimiento(m) for m in self._vivos().filter(descontado_a_id=descontado_a_id, fecha__date=dia)]


class CajitasDjango:
    """La cajita de la caja chica es la de la responsable de servicios de la sucursal de esa caja."""

    def duena_de(self, caja_id):
        from sucursales.models import Caja

        caja = (Caja.objects.select_related("sucursal__dueño_servicios__user")
                .filter(pk=caja_id).first())
        emp = caja.sucursal.dueño_servicios if caja and caja.sucursal_id else None
        if emp is None:
            return None
        return Duena(id=emp.id, nombre=_nombre_de_empleado(emp))
