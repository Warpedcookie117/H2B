from django.urls import path

# POS
from ventas.views.pos_views import pos_view, procesar_venta, stock_productos
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


]
