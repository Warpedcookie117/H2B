from django import views
from django.urls import path

# Productos
from .views.productos import (
    detalle_producto,
    eliminar_producto_completo,
    nuevo_producto,
    lista_productos,
    buscar_producto_por_codigo,
    codigo_base64,
    productos_por_ubicacion,
    seleccionar_etiqueta_temp,
    temporada_view,
    mis_productos,
)

# Categorías
from .views.categorias import (
    categoria_view,
    api_categorias,
    configurar_atributos,
    eliminar_atributo,
    nuevo_atributo,

    # NUEVAS VIEWS AJAX
    modal_categoria_view,
    modal_subcategoria_view,
    guardar_categoria_view,
    guardar_subcategoria_view,
    eliminar_categoria_view,
    eliminar_subcategoria_view,
)

# Ubicaciones
from .views.ubicaciones import (
    editar_ubicacion,
    eliminar_ubicacion,
    ubicacion_nueva,
    ubicaciones,
)

# Inventarios
from .views.inventarios import (
    agregar_inventario,
    aprobar_solicitud,
    aprobar_solicitud_panel,
    eliminar_inventario_ubicacion,
    mis_solicitudes,
    rechazar_solicitud,
    rechazar_solicitud_panel,
    solicitudes_pendientes,
    verificar_estado_producto,
    transferir_inventario,
    ajustar_inventario,
    dashboard_inventario,
    buscar_producto_en_ubicacion,
    transferencia_multiple,
    ubicaciones_del_producto,
)

# Reportes
from .views.reportes import (
    reportes,
    reporte_pdf,
    exportar_criticos,
)

app_name = 'inventario'

urlpatterns = [

    # ============================
    # PRODUCTOS
    # ============================
    path('mis-productos/', mis_productos, name='mis_productos'),
    path('nuevo_producto/', nuevo_producto, name='nuevo_producto'),
    path('productos/', lista_productos, name='lista_productos'),
    path('buscar_producto/', buscar_producto_por_codigo, name='buscar_producto'),
    path('temporadas/', temporada_view, name='temporadas'),
    path('detalle_producto/<int:producto_id>/', detalle_producto, name='detalle_producto'),
    path("ubicacion/<int:ubicacion_id>/", productos_por_ubicacion, name="productos_por_ubicacion"),
    path('producto/<int:producto_id>/codigo_base64/', codigo_base64, name='codigo_base64'),
    path('seleccionar_etiqueta_temp/', seleccionar_etiqueta_temp, name='seleccionar_etiqueta_temp'),
    path('api/producto/<int:producto_id>/', eliminar_producto_completo, name='eliminar_producto_completo'),

    # ============================
    # UBICACIONES
    # ============================
    path("ubicaciones/", ubicaciones, name="ubicaciones"),
    path("ubicaciones/nueva/", ubicacion_nueva, name="ubicacion_nueva"),
    path("ubicaciones/editar/<int:ubicacion_id>/", editar_ubicacion, name="editar_ubicacion"),
    path("ubicaciones/eliminar/<int:ubicacion_id>/", eliminar_ubicacion, name="eliminar_ubicacion"),

    # ============================
    # CATEGORÍAS (VISTA PRINCIPAL)
    # ============================
    path('categorias/', categoria_view, name='categorias'),
    path('api/categorias/', api_categorias, name='api_categorias'),

    # Atributos (módulo aparte)
    path('atributos/', configurar_atributos, name='configurar_atributos'),
    path("atributo/nuevo/<int:subcat_id>/", nuevo_atributo, name="nuevo_atributo"),
    path("atributo/editar/<int:subcat_id>/<int:atributo_id>/", nuevo_atributo, name="editar_atributo"),
    path("atributo/eliminar/<int:subcat_id>/<int:atributo_id>/", eliminar_atributo, name="eliminar_atributo"),

    # ============================
    # CATEGORÍAS (AJAX + MODALES)
    # ============================

    # Modal categoría padre
    path("categorias/modal-categoria/", modal_categoria_view, name="modal_categoria_nueva"),
    path("categorias/modal-categoria/<int:categoria_id>/", modal_categoria_view, name="modal_categoria_editar"),
    # Guardar categoría padre
    path("categorias/guardar/", guardar_categoria_view, name="categoria_guardar_nueva"),
    path("categorias/guardar/<int:categoria_id>/", guardar_categoria_view, name="categoria_guardar"),
    # Eliminar categoría padre
    path("categorias/eliminar/padre/<int:categoria_id>/", eliminar_categoria_view, name="eliminar_categoria"),


    # Modal subcategoría
    path("categorias/modal-subcategoria/<int:padre_id>/", modal_subcategoria_view, name="modal_subcategoria_nueva"),
    path("categorias/modal-subcategoria/<int:padre_id>/<int:sub_id>/", modal_subcategoria_view, name="modal_subcategoria_editar"),
    # Guardar subcategoría
    path("categorias/sub/guardar/<int:padre_id>/", guardar_subcategoria_view, name="subcategoria_guardar_nueva"),
    path("categorias/sub/guardar/<int:padre_id>/<int:sub_id>/", guardar_subcategoria_view, name="subcategoria_guardar"),
    # Eliminar subcategoría
    path("categorias/eliminar/sub/<int:sub_id>/", eliminar_subcategoria_view, name="eliminar_subcategoria"),





    # ============================
    # INVENTARIO
    # ============================
    path('verificar_estado_producto/', verificar_estado_producto, name='verificar_estado_producto'),
    path('agregar_inventario/<int:producto_id>/<int:ubicacion_id>/', agregar_inventario, name='agregar_inventario'),
    path('dashboard-inventario/', dashboard_inventario, name='dashboard_inventario'),
    path("ajustar/<int:producto_id>/<int:ubicacion_id>/", ajustar_inventario, name="ajustar_inventario"),
    path("transferir/", transferir_inventario, name="transferir_inventario"),
    path("transferencia-multiple/<int:ubicacion_origen_id>/", transferencia_multiple, name="transferencia_multiple"),
    path("buscar_producto_en_ubicacion/", buscar_producto_en_ubicacion, name="buscar_producto_en_ubicacion"),
    path('api/inventario-ubicacion/<int:producto_id>/<int:ubicacion_id>/', eliminar_inventario_ubicacion, name='eliminar_inventario_ubicacion'),
    path('api/ubicaciones-del-producto/<int:producto_id>/', ubicaciones_del_producto, name='ubicaciones_del_producto'),

    # ============================
    # SOLICITUDES
    # ============================
    path("mis-solicitudes/", mis_solicitudes, name="mis_solicitudes"),
    path("solicitudes-pendientes/", solicitudes_pendientes, name="solicitudes_pendientes"),

    # Aprobación / rechazo por correo
    path("solicitudes/<int:solicitud_id>/aprobar/", aprobar_solicitud, name="aprobar_solicitud"),
    path("solicitudes/<int:solicitud_id>/rechazar/", rechazar_solicitud, name="rechazar_solicitud"),

    # Aprobación / rechazo por panel
    path("solicitudes/<int:solicitud_id>/aprobar-panel/", aprobar_solicitud_panel, name="aprobar_solicitud_panel"),
    path("solicitudes/<int:solicitud_id>/rechazar-panel/", rechazar_solicitud_panel, name="rechazar_solicitud_panel"),

    # ============================
    # REPORTES
    # ============================
    path('reportes/', reportes, name='reportes'),
    path('reportes/pdf/', reporte_pdf, name='reporte_pdf'),
    path('exportar-criticos/', exportar_criticos, name='exportar_criticos'),
]