"""
API JSON del modal "¿Compraste algo?" del POS. Cualquiera que esté en una
caja (cajera o dueña) registra vales y gastos; la caja es la de la sesión.
"""
import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from caja_chica.domain.errores import ErrorCajaChica, NombreParecido, SinPermiso
from caja_chica.domain.permisos import exigir_puede_registrar
from caja_chica.infrastructure import contenedor
from caja_chica.views.comun import actor_de, movimiento_json


def _error(mensaje, status=400):
    return JsonResponse({"status": "error", "mensaje": mensaje}, status=status)


def _cuerpo(request):
    try:
        data = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _en_caja(request):
    """(actor, caja_id) de la sesión, o una respuesta 403 si no puede registrar."""
    actor = actor_de(request)
    caja_id = request.session.get("caja_actual")
    if actor is None:
        return None, None, _error("No tienes perfil de empleado.", 403)
    try:
        exigir_puede_registrar(actor, caja_id)
    except SinPermiso as e:
        return None, None, _error(str(e), 403)
    return actor, caja_id, None


@login_required
@require_GET
def estado(request):
    """Lo que necesita el modal al abrirse: personas registradas, de quién es la cajita y lo de hoy en esta caja."""
    actor, caja_id, error = _en_caja(request)
    if error:
        return error
    duena = contenedor.cajita_de(caja_id)
    return JsonResponse({
        "status": "ok",
        "duena": duena.nombre if duena else None,
        "personas": [{"id": p.id, "nombre": p.nombre} for p in contenedor.listar_personas()()],
        "sin_corte": [movimiento_json(m) for m in contenedor.lo_sin_corte_de_caja()(caja_id)],
    })


def _registrado(movimiento):
    return JsonResponse({
        "status": "ok",
        "movimiento": movimiento_json(movimiento),
        "mensaje": f"Listo. Saca ${movimiento.monto:,.2f} de la cajita de {movimiento.descontado_a_nombre}.",
    }, status=201)


@login_required
@require_POST
def registrar_vale(request):
    """Body: {"monto", "persona_id"} o {"monto", "nombre", "es_otra_persona"?}."""
    actor, caja_id, error = _en_caja(request)
    if error:
        return error
    data = _cuerpo(request)
    if data is None:
        return _error("No se entendió lo que se mandó.")
    persona_id = data.get("persona_id")
    if not isinstance(persona_id, int) or isinstance(persona_id, bool):
        persona_id = None
    try:
        m = contenedor.registrar_vale()(
            actor, caja_id, data.get("monto"), nombre=data.get("nombre", ""),
            persona_id=persona_id, es_otra_persona=data.get("es_otra_persona") is True,
        )
    except NombreParecido as e:
        return JsonResponse({"status": "parecido", "mensaje": str(e), "sugerencias": e.sugerencias},
                            status=409)
    except ErrorCajaChica as e:
        return _error(str(e))
    return _registrado(m)


@login_required
@require_POST
def registrar_gasto(request):
    """Body: {"descripcion", "monto"}."""
    actor, caja_id, error = _en_caja(request)
    if error:
        return error
    data = _cuerpo(request)
    if data is None:
        return _error("No se entendió lo que se mandó.")
    try:
        m = contenedor.registrar_gasto()(actor, caja_id, data.get("monto"), data.get("descripcion", ""))
    except ErrorCajaChica as e:
        return _error(str(e))
    return _registrado(m)
