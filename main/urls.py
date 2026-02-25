from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings
from django.conf.urls.static import static

# Importar vistas reales desde login.py
from tienda_temp.views.login import (
    contacto,
    aboutus,
    configuracion_perfil,
)

urlpatterns = [
    # Página principal (landing)
    path('', TemplateView.as_view(template_name='tienda_temp/landing.html'), name='landing'),

    # Admin
    path('admin/', admin.site.urls),

    # Rutas de la app tienda_temp
    path('tienda_temp/', include('tienda_temp.urls')),

    # Vistas públicas
    path('contacto/', contacto, name='contacto'),
    path('about-us/', aboutus, name='about-us'),
    path('configuracion/', configuracion_perfil, name='profile_settings'),

    # Otras apps
    path('inventario/', include('inventario.urls')),
    path('ventas/', include('ventas.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Personalización del panel de administración
admin.site.site_header = "Administración de tienda_temp"
admin.site.site_title = "Tienda"