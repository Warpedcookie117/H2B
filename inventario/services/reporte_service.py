from inventario.models import Inventario, MovimientoInventario
from inventario.services.filtros_service import filtrar_productos
from django.db.models import Sum, F



def inventario_general(categoria_id=None, subcategoria_id=None,
                       temporada_id=None, dueño_id=None, ubicacion_id=None):

    # 1. Filtrar productos según los parámetros
    productos = filtrar_productos(
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        temporada_id=temporada_id,
        dueño_id=dueño_id
    )

    # 2. Filtrar inventario según los productos
    inventario = (
        Inventario.objects
        .filter(producto__in=productos)
        .select_related(
            "producto",                     # ✔ necesario
            "producto__categoria_padre",    # ✔ ahora sí funciona
            "producto__categoria",
            "producto__dueño",
            "ubicacion"
        )
        .prefetch_related("producto__temporada")
    )


    # 3. Filtro opcional por ubicación
    if ubicacion_id:
        inventario = inventario.filter(ubicacion_id=ubicacion_id)

    # 4. Construir queryset plano para el reporte
    qs = (
        inventario
        .values(
            "producto_id",
            "ubicacion_id",
            producto_nombre=F("producto__nombre"),
            dueño_nombre=F("producto__dueño__user__username"),
            categoria_nombre=F("producto__categoria_padre__nombre"),  # ✔ corregido
            subcategoria_nombre=F("producto__categoria__nombre"),
            ubicacion_nombre=F("ubicacion__nombre"),
        )
        .annotate(total=Sum("cantidad_actual"))
        .order_by("producto__nombre")
    )

    # 5. Resolver temporadas sin N+1
    producto_map = {
        p.id: ", ".join([t.nombre for t in p.temporada.all()]) or "N/A"
        for p in productos
    }

    for item in qs:
        item["temporada_nombres"] = producto_map.get(item["producto_id"], "N/A")

    return qs

def movimientos_por_tipo(tipo=None, categoria_id=None, subcategoria_id=None,
                         temporada_id=None, dueño_id=None):

    # 1. Filtrar productos según los parámetros
    productos = filtrar_productos(
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        temporada_id=temporada_id,
        dueño_id=dueño_id
    )

    # 2. Filtrar movimientos según los productos
    queryset = (
        MovimientoInventario.objects
        .filter(producto__in=productos)
        .select_related(
            "producto__categoria_padre",   # ✔ corregido
            "producto__categoria",         # subcategoría
            "producto__dueño__user",
            "origen",
            "destino"
        )
        .prefetch_related("producto__temporada")
    )

    # 3. Filtro opcional por tipo de movimiento
    if tipo:
        queryset = queryset.filter(tipo=tipo)

    # 4. Construir queryset plano
    qs = (
        queryset
        .values(
            "producto_id",
            "tipo",
            "motivo",
            "cantidad",
            "fecha",
            producto_nombre=F("producto__nombre"),
            dueño_nombre=F("producto__dueño__user__username"),
            categoria_nombre=F("producto__categoria_padre__nombre"),  # ✔ corregido
            subcategoria_nombre=F("producto__categoria__nombre"),
            origen_nombre=F("origen__nombre"),
            destino_nombre=F("destino__nombre"),
        )
        .order_by("-fecha")
    )

    # 5. Resolver temporadas sin N+1
    producto_map = {
        p.id: ", ".join([t.nombre for t in p.temporada.all()]) or "N/A"
        for p in productos
    }

    for item in qs:
        item["temporada_nombres"] = producto_map.get(item["producto_id"], "N/A")

    return qs

def resumen_movimientos(categoria_id=None, subcategoria_id=None,
                        temporada_id=None, dueño_id=None):

    productos = filtrar_productos(
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        temporada_id=temporada_id,
        dueño_id=dueño_id
    )

    movimientos = (
        MovimientoInventario.objects
        .filter(producto__in=productos)
        .select_related(
            'producto__categoria_padre',   # ✔ corregido
            'producto__categoria',         # subcategoría
            'producto__dueño'
        )
        .prefetch_related('producto__temporada')
    )

    qs = (
        movimientos
        .values(
            'tipo',
            'producto__id',
            'producto__nombre',
            'producto__categoria_padre__nombre',   # ✔ corregido
            'producto__categoria__nombre',
            'producto__dueño__user__username',
        )
        .annotate(total=Sum('cantidad'))
        .order_by('tipo')
    )

    # Resolver temporadas sin N+1
    producto_map = {
        p.id: ", ".join([t.nombre for t in p.temporada.all()]) or "N/A"
        for p in productos
    }

    for item in qs:
        item["temporada_nombres"] = producto_map.get(item["producto__id"], "N/A")

    return qs

def total_global(categoria_id=None, subcategoria_id=None,
                 temporada_id=None, dueño_id=None):

    productos = filtrar_productos(
        categoria_id=categoria_id,
        subcategoria_id=subcategoria_id,
        temporada_id=temporada_id,
        dueño_id=dueño_id
    )

    inventario = Inventario.objects.filter(producto__in=productos)

    return inventario.aggregate(total=Sum('cantidad_actual'))['total'] or 0


def get_datos_reporte(
    tipo,
    categoria_id=None,
    subcategoria_id=None,
    temporada_id=None,
    ubicacion_id=None,
    dueño_id=None,
    movimiento_tipo=None
):
    """
    Dispatcher central de reportes.
    Según el tipo, llama al servicio correspondiente.
    """

    if tipo == "general":
        return inventario_general(
            categoria_id=categoria_id,
            subcategoria_id=subcategoria_id,
            temporada_id=temporada_id,
            dueño_id=dueño_id,
            ubicacion_id=ubicacion_id
        )

    if tipo == "movimientos":
        return movimientos_por_tipo(
            tipo=movimiento_tipo,
            categoria_id=categoria_id,
            subcategoria_id=subcategoria_id,
            temporada_id=temporada_id,
            dueño_id=dueño_id
        )

    if tipo == "resumen_movimientos":
        return resumen_movimientos(
            categoria_id=categoria_id,
            subcategoria_id=subcategoria_id,
            temporada_id=temporada_id,
            dueño_id=dueño_id
        )

    # Tipo desconocido
    return []