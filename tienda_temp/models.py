from django.db import models
from django.contrib.auth.models import AbstractUser

# Usuario base extendido
class Usuario(AbstractUser):
    email = models.EmailField(unique=True)

    def __str__(self):
        return self.username

# Clase abstracta para compartir campos comunes
class PerfilBase(models.Model):
    direccion = models.CharField(max_length=255)
    numero_contacto = models.CharField(max_length=20)

    class Meta:
        abstract = True

# Perfil de empleado
class Empleado(PerfilBase):
    user = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='empleado')

    ROL_CHOICES = [
        ('cajero', 'Cajero'),
        ('ayudante', 'Ayudante General'),
        ('almacenista', 'Almacenista'),
        ('dueño', 'Dueño'),
    ]

    edad = models.IntegerField(null=True, blank=True)
    rol = models.CharField(max_length=50, choices=ROL_CHOICES)
    contacto_emergencia = models.CharField(max_length=100)
    descripcion_contacto_emergencia = models.TextField(max_length=100)

    def __str__(self):
        return f"{self.user.username} ({self.rol})"

# Perfil de cliente
class Cliente(PerfilBase):
    user = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name='cliente')

    def __str__(self):
        return f"{self.user.username} (Cliente)"
