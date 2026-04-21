from django.urls import path
from sucursales import views
from sucursales.views.sucursales_views import crear_sucursal
from sucursales.views.dashboard_sucursales_views import dashboard_sucursal, eliminar_sucursal
from sucursales.views.cajas_views import crear_caja_ajax, entrar_caja_ajax, salir_caja, modal_crear_caja, modal_entrar_caja, eliminar_caja

app_name = "sucursales"

urlpatterns = [
    # Sucursales
    path("crear/", crear_sucursal, name="crear_sucursal"),
    path("<int:sucursal_id>/dashboard/", dashboard_sucursal, name="dashboard_sucursal"),
    path("<int:sucursal_id>/eliminar/", eliminar_sucursal, name="eliminar_sucursal"),

    # Cajas
    path("<int:sucursal_id>/caja/modal/", modal_crear_caja, name="modal_crear_caja"),
    path("<int:sucursal_id>/caja/crear/", crear_caja_ajax, name="crear_caja"),
    path("caja/entrar/ajax/", entrar_caja_ajax, name="entrar_caja_ajax"),  # ✔ CORRECTO
    path("caja/salir/", salir_caja, name="salir_caja"),
    path("modal-entrar-caja/", modal_entrar_caja, name="modal_entrar_caja"),
    path("caja/<int:caja_id>/eliminar/", eliminar_caja, name="eliminar_caja"),
]