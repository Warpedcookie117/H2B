from django.core.exceptions import ValidationError
from inventario.models import Ubicacion


class UbicacionService:

    @staticmethod
    def crear(nombre: str, tipo: str, sucursal=None, direccion="") -> Ubicacion:
        """Crea una ubicación global o interna, validando reglas del dominio."""

        # Evitar duplicados globales
        if sucursal is None:
            if Ubicacion.objects.filter(nombre__iexact=nombre, sucursal__isnull=True).exists():
                raise ValidationError(f"Ya existe una ubicación global con el nombre '{nombre}'.")

        # Evitar duplicados por sucursal
        if sucursal is not None:
            if Ubicacion.objects.filter(nombre__iexact=nombre, sucursal=sucursal).exists():
                raise ValidationError(
                    f"Ya existe una ubicación llamada '{nombre}' en la sucursal {sucursal.nombre}."
                )

        ubicacion = Ubicacion(
            nombre=nombre,
            tipo=tipo,
            sucursal=sucursal,
            direccion=direccion
        )

        ubicacion.full_clean()
        ubicacion.save()

        return ubicacion

    @staticmethod
    def crear_internas_para_sucursal(sucursal):
        """Crea las ubicaciones internas obligatorias para cada sucursal."""

        piso_nombre = f"Piso {sucursal.nombre}"
        bodega_nombre = f"Bodega Interna {sucursal.nombre}"

        UbicacionService.crear(
            nombre=piso_nombre,
            tipo="piso",
            sucursal=sucursal,
            direccion=sucursal.direccion
        )

        UbicacionService.crear(
            nombre=bodega_nombre,
            tipo="bodega",
            sucursal=sucursal,
            direccion=sucursal.direccion
        )