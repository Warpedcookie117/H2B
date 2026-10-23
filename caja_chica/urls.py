from django.urls import path

from caja_chica.views import duenas, pos

app_name = "caja_chica"

urlpatterns = [
    # Modal "¿Compraste algo?" del POS (JSON)
    path("pos/estado/", pos.estado, name="estado"),
    path("pos/vales/", pos.registrar_vale, name="registrar_vale"),
    path("pos/gastos/", pos.registrar_gasto, name="registrar_gasto"),

    # Correcciones de las dueñas desde el dashboard (formularios)
    path("movimientos/<int:movimiento_id>/monto/", duenas.cambiar_monto, name="cambiar_monto"),
    path("movimientos/<int:movimiento_id>/eliminar/", duenas.eliminar, name="eliminar"),
]
