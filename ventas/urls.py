from django.urls import path, include

from . import views


app_name = "ventas"

urlpatterns = [
    
    path("pos/", views.pos_view, name="pos"),
    path("procesar-venta/", views.procesar_venta, name="procesar_venta"),




] 

