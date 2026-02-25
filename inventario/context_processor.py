from inventario.models import Ubicacion
from inventario.utils import color_from_name

def ubicaciones_sidebar(request):
    ubicaciones = Ubicacion.objects.all().order_by("nombre")
    for u in ubicaciones:
        u.color = color_from_name(u.nombre)
    return {
        "ubicaciones_sidebar": ubicaciones,
    }