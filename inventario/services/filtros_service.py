from inventario.models import Categoria, Producto, Temporada, Ubicacion
from tienda_temp.models import Empleado

# -----------------------------
# Helper para filtros
# -----------------------------

def filtrar_productos(categoria_id=None, subcategoria_id=None,
                      temporada_id=None, dueño_id=None):

    qs = (
        Producto.objects
        .select_related("categoria", "categoria_padre", "dueño")
        .prefetch_related("temporada")
    )

    # Filtrar por categoría padre
    if categoria_id:
        qs = qs.filter(categoria_padre_id=categoria_id)

    # Filtrar por subcategoría
    if subcategoria_id:
        qs = qs.filter(categoria_id=subcategoria_id)

    # Filtrar por temporada (M2M)
    if temporada_id:
        qs = qs.filter(temporada__id=temporada_id)

    # Filtrar por dueño
    if dueño_id:
        qs = qs.filter(dueño_id=dueño_id)

    return qs.distinct()


def parse_filtros(request):
    """
    Extrae filtros desde request.GET.
    Convierte valores vacíos o con espacios en None.
    """

    def clean(value):
        if value is None:
            return None
        value = str(value).strip()
        return value or None   # "" → None, "   " → None, "3" → "3"

    # Tipo de reporte
    tipo = clean(request.GET.get("tipo"))
    if tipo not in {"general", "movimientos", "resumen_movimientos"}:
        tipo = "general"

    return {
        "ubicacion": clean(request.GET.get("ubicacion")),
        "categoria": clean(request.GET.get("categoria")),
        "subcategoria": clean(request.GET.get("subcategoria")),
        "temporada": clean(request.GET.get("temporada")),
        "dueño": clean(request.GET.get("dueño")),
        "movimiento": clean(request.GET.get("movimiento")),
        "tipo": tipo,
    }


def nombres_filtros(filtros):
    """
    Convierte los IDs de filtros en nombres legibles usando los modelos reales.
    Si no encuentra el registro, devuelve 'Desconocido'.
    """

    resultado = {
        "ubicacion": None,
        "categoria": None,
        "subcategoria": None,
        "temporada": None,
        "dueño": None,
    }

    if filtros.get("ubicacion"):
        resultado["ubicacion"] = Ubicacion.objects.filter(
            id=filtros["ubicacion"]
        ).values_list("nombre", flat=True).first() or "Desconocido"

    if filtros.get("categoria"):
        resultado["categoria"] = Categoria.objects.filter(
            id=filtros["categoria"]
        ).values_list("nombre", flat=True).first() or "Desconocido"

    if filtros.get("subcategoria"):
        resultado["subcategoria"] = Categoria.objects.filter(
            id=filtros["subcategoria"]
        ).values_list("nombre", flat=True).first() or "Desconocido"

    if filtros.get("temporada"):
        resultado["temporada"] = Temporada.objects.filter(
            id=filtros["temporada"]
        ).values_list("nombre", flat=True).first() or "Desconocido"

    if filtros.get("dueño"):
        resultado["dueño"] = Empleado.objects.filter(
            id=filtros["dueño"]
        ).values_list("user__first_name", flat=True).first() or "Desconocido"

    return resultado

