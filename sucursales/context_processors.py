from sucursales.models import Sucursal
from inventario.models import Ubicacion
from inventario.utils import color_from_name

def sucursales_sidebar(request):
    if request.user.is_authenticated and hasattr(request.user, "empleado"):
        sucursales = Sucursal.objects.all().order_by("nombre")

        for s in sucursales:
            s.color = color_from_name(s.nombre)

            # Piso
            s.piso = Ubicacion.objects.filter(
                sucursal=s, tipo="piso"
            ).first()

            # Bodega interna
            s.bodega_interna = Ubicacion.objects.filter(
                sucursal=s, tipo="bodega"
            ).first()

        return {"sucursales_sidebar": sucursales}

    return {}