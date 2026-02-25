from django.contrib import admin
from .models import Usuario, Empleado, Cliente

class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff')

class EmpleadoAdmin(admin.ModelAdmin):
    list_display = ('user', 'rol', 'edad')

class ClienteAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'direccion', 'numero_contacto')

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Usuario'


admin.site.register(Usuario, UsuarioAdmin)
admin.site.register(Empleado, EmpleadoAdmin)
admin.site.register(Cliente, ClienteAdmin)
