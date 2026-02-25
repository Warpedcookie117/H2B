
from django.shortcuts import redirect
from django.urls import path
from .views.dashboards import (
dashboard_socio, 
dashboard_dueno,
base_conocimientos,
)

from .views.login import (
  landing,
  login_user,
  logout_user,
  configuracion_perfil,
  contacto,
)

from .views.registro_de_empleados import (
    registro_cliente, 
    registro_empleado,
)




app_name = 'tienda_temp'

urlpatterns = [
    path('login/', login_user, name='login'),
    path('logout/', logout_user, name='logout'),
    path('registro-empleado/', registro_empleado, name='registro_empleado'),
    path('registro-cliente/', registro_cliente, name='registro_cliente'),
    path('registro-dueno/', lambda r: redirect('/tienda/registro-empleado/?rol=dueño'), name='registro_dueno'),

    #URLS para dashboards y usuarios clientes
    path('', landing, name='landing'),
    
    #dashboards
    path('dashboard-socio/', dashboard_socio, name='dashboard_socio'),
    path('dashboard-dueno/', dashboard_dueno, name='dashboard_dueno'),
    path('base-conocimientos/', base_conocimientos, name='base_conocimientos'),
    
    path('contacto/', contacto, name='contacto'),
    path('configuracion_perfil/', configuracion_perfil, name='configuracion_perfil'),

]
