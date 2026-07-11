from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
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
    path('', TemplateView.as_view(template_name='tienda/landing.html'), name='landing'),
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
    path('sucursales/',include('sucursales.urls')),

    # Reset de contraseña con correo HTML en español y con marca.
    # Se define ANTES del include de auth para que tome esta versión (con
    # html_email_template_name); las demás rutas del flujo las da el include.
    path(
        'accounts/password_reset/',
        auth_views.PasswordResetView.as_view(
            template_name='registration/password_reset_form.html',
            subject_template_name='registration/password_reset_subject.txt',
            email_template_name='registration/password_reset_email.txt',
            html_email_template_name='registration/password_reset_email.html',
        ),
        name='password_reset',
    ),
    path('accounts/', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Personalización del panel de administración
admin.site.site_header = "Administración de tienda_temp"
admin.site.site_title = "Tienda"