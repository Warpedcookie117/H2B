from django.urls import path

# POS
from ventas.views.pos_views import pos_view, procesar_venta, stock_productos

# Promociones
from ventas.views.promociones_views import (
    promociones_view,
    modal_promocion_view,
    guardar_promocion_view,
    toggle_promocion_view,
    eliminar_promocion_view,
    productos_regalo_view,
    atributos_categoria_view,
)

# Ofertas
from ventas.views.ofertas_views import (
    modal_oferta_view,
    guardar_oferta_view,
    toggle_oferta_view,
    eliminar_oferta_view,
    buscar_producto_view,
)
# Tickets de venta
from ventas.views.ticket_venta_views import (
    
    tickets_ventas,
    ticket_venta, 
    ticket_venta_pdf, 
    ticket_venta_termico

)

#ventas_views
from ventas.views.ventas_views import (
    
    ventas_por_cajero,
    api_ventas_hoy
) 

# Tickets de corte
from ventas.views.ticket_corte_views import (
    ticket_corte,
    ticket_corte_pdf,
    ticket_corte_termico,
    tickets_cortes_caja,
    corte_del_dia,
)


app_name = "ventas"

urlpatterns = [

    # ============================
    # POS
    # ============================
    path("pos/", pos_view, name="pos"),
    path("procesar-venta/", procesar_venta, name="procesar_venta"),
    path("stock-productos/", stock_productos, name="stock_productos"),

    # ============================
    # TICKETS DE VENTA
    # ============================
    path("<int:sucursal_id>/tickets/ventas/", tickets_ventas, name="tickets_ventas"),
    path("ticket-venta/<int:venta_id>/", ticket_venta, name="ticket_venta"),
    path("ticket-venta/<int:venta_id>/pdf/", ticket_venta_pdf, name="ticket_venta_pdf"),
    path("ticket-venta/<int:venta_id>/termico/", ticket_venta_termico, name="ticket_venta_termico"),
    
    # ============================
    # Cortes de caja
    # ============================
    path("corte-del-dia/", corte_del_dia, name="corte_caja"),
    path("<int:sucursal_id>/tickets/cortes/", tickets_cortes_caja, name="tickets_cortes_caja"),
    path("ticket-corte/<int:corte_id>/", ticket_corte, name="ticket_corte"),
    path("ticket-corte/<int:corte_id>/pdf/", ticket_corte_pdf, name="ticket_corte_pdf"),
    path("ticket-corte/<int:corte_id>/termico/", ticket_corte_termico, name="ticket_corte_termico"),

    # ============================
    # Ventas
    # ============================
    path("ventas-por-cajero/", ventas_por_cajero, name="ventas_por_cajero"),
    path("api/ventas/hoy/", api_ventas_hoy, name="api_ventas_hoy"),

    # ============================
    # Promociones
    # ============================
    path("promociones/", promociones_view, name="promociones"),
    path("promociones/modal/", modal_promocion_view, name="promocion_modal_nueva"),
    path("promociones/modal/<int:promocion_id>/", modal_promocion_view, name="promocion_modal_editar"),
    path("promociones/guardar/", guardar_promocion_view, name="promocion_guardar_nueva"),
    path("promociones/guardar/<int:promocion_id>/", guardar_promocion_view, name="promocion_guardar"),
    path("promociones/toggle/<int:promocion_id>/", toggle_promocion_view, name="promocion_toggle"),
    path("promociones/eliminar/<int:promocion_id>/", eliminar_promocion_view, name="promocion_eliminar"),
    path("promociones/productos-regalo/<int:promo_id>/", productos_regalo_view, name="promocion_productos_regalo"),
    path("promociones/atributos-categoria/<int:categoria_id>/", atributos_categoria_view, name="atributos_categoria"),

    # ============================
    # Ofertas
    # ============================
    path("ofertas/modal/",                          modal_oferta_view,    name="oferta_modal_nueva"),
    path("ofertas/modal/<int:oferta_id>/",          modal_oferta_view,    name="oferta_modal_editar"),
    path("ofertas/guardar/",                        guardar_oferta_view,  name="oferta_guardar_nueva"),
    path("ofertas/guardar/<int:oferta_id>/",        guardar_oferta_view,  name="oferta_guardar"),
    path("ofertas/toggle/<int:oferta_id>/",         toggle_oferta_view,   name="oferta_toggle"),
    path("ofertas/eliminar/<int:oferta_id>/",       eliminar_oferta_view, name="oferta_eliminar"),
    path("api/buscar-producto/",                    buscar_producto_view, name="buscar_producto"),

]
