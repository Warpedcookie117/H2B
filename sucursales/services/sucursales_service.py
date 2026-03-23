from django.core.exceptions import ValidationError
from sucursales.models import Sucursal
from inventario.services.ubicaciones_service import UbicacionService


class SucursalService:

    @staticmethod
    def crear(nombre: str, direccion: str = "") -> Sucursal:
        """
        Crea una sucursal y automáticamente sus ubicaciones internas:
        - Piso <Sucursal>
        - Bodega Interna <Sucursal>

        Este es el ÚNICO punto de creación de sucursales en el sistema.
        """

        # Crear sucursal
        sucursal = Sucursal(
            nombre=nombre,
            direccion=direccion
        )

        sucursal.full_clean()
        sucursal.save()

        # Crear ubicaciones internas obligatorias
        UbicacionService.crear_internas_para_sucursal(sucursal)

        return sucursal