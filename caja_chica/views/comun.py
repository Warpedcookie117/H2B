"""Lo que comparten las vistas de la caja chica: quién es el actor y cómo se ve un movimiento en JSON."""
from django.utils import timezone

from caja_chica.domain.movimientos import TipoMovimiento
from caja_chica.domain.permisos import Actor


def actor_de(request):
    """Actor del dominio para el Empleado de la sesión, o None si no tiene perfil."""
    emp = getattr(request.user, "empleado", None)
    if emp is None:
        return None
    nombre = (request.user.first_name or "").strip() or request.user.username
    return Actor(id=emp.id, nombre=nombre, rol=emp.rol)


def movimiento_json(m):
    return {
        "id": m.id,
        "tipo": m.tipo.value,
        "tipo_texto": "Vale" if m.tipo is TipoMovimiento.VALE else "Gasto",
        "concepto": m.concepto,
        "monto": float(m.monto),
        "hora": timezone.localtime(m.fecha).strftime("%H:%M"),
        "registrado_por": m.registrado_por_nombre,
        "descontado_a": m.descontado_a_nombre,
    }
