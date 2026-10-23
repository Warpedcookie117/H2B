"""
Correcciones de las dueñas desde su dashboard: cambiar el monto o eliminar
un vale o un gasto. Formularios normales (POST y de regreso al dashboard).
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from caja_chica.domain.errores import ErrorCajaChica
from caja_chica.infrastructure import contenedor
from caja_chica.views.comun import actor_de


def _de_regreso(request):
    destino = request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()},
                                           require_https=request.is_secure()):
        destino = reverse("tienda_temp:dashboard_dueno") + "#caja-chica"
    return redirect(destino)


def _corregir(request, accion, exito):
    """Corre el caso de uso `accion(actor)` y deja el mensaje; siempre regresa al dashboard."""
    actor = actor_de(request)
    if actor is None:
        messages.error(request, "No tienes permiso.")
        return _de_regreso(request)
    try:
        resultado = accion(actor)
    except ErrorCajaChica as e:
        messages.error(request, str(e))
    else:
        messages.success(request, exito(resultado))
    return _de_regreso(request)


@login_required
@require_POST
def cambiar_monto(request, movimiento_id):
    return _corregir(
        request,
        lambda actor: contenedor.cambiar_monto()(actor, movimiento_id, request.POST.get("monto")),
        lambda m: f"Listo: {m.concepto} quedó en ${m.monto:,.2f}.",
    )


@login_required
@require_POST
def eliminar(request, movimiento_id):
    return _corregir(
        request,
        lambda actor: contenedor.eliminar_movimiento()(actor, movimiento_id),
        lambda _: "Listo, se borró. Ese dinero vuelve a contar en la cajita.",
    )
