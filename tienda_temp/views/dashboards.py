from django.db.models import Sum, F
from django.shortcuts import render
from inventario.models import Categoria, Inventario, MovimientoInventario, Producto


def dashboard_socio(request):

    # === MÉTRICAS ===

    # Productos activos = productos que tienen inventario en alguna ubicación
    productos_activos = Inventario.objects.values('producto').distinct().count()

    # Bajo stock → como NO tienes stock_minimo, lo dejamos en 0
    bajo_stock = 0

    # Valor total del inventario
    valor_inventario = Inventario.objects.aggregate(
        total=Sum(F('cantidad_actual') * F('producto__precio_menudeo'))
    )['total'] or 0

    # === ALERTAS IMPORTANTES ===
    alertas = []

    if Producto.objects.filter(foto_url__isnull=True).exists():
        alertas.append("Hay productos sin fotografía.")

    if Producto.objects.filter(precio_menudeo__lte=0).exists():
        alertas.append("Hay productos sin precio asignado.")

    # === MOVIMIENTOS RECIENTES ===
    movimientos = MovimientoInventario.objects.select_related('producto').order_by('-fecha')[:5]

    # === GRÁFICAS ===
    categorias = Categoria.objects.filter(padre__isnull=True)

    graf_categorias_labels = []
    graf_categorias_data = []

    graf_valor_labels = []
    graf_valor_data = []

    for cat in categorias:
        # Cantidad total por categoría
        total_cat = Inventario.objects.filter(
            producto__categoria_padre=cat
        ).aggregate(total=Sum('cantidad_actual'))['total'] or 0

        graf_categorias_labels.append(cat.nombre)
        graf_categorias_data.append(total_cat)

        # Valor total por categoría
        valor_cat = Inventario.objects.filter(
            producto__categoria_padre=cat
        ).aggregate(
            total=Sum(F('cantidad_actual') * F('producto__precio_menudeo'))
        )['total'] or 0

        graf_valor_labels.append(cat.nombre)
        graf_valor_data.append(valor_cat)

    context = {
        "productos_activos": productos_activos,
        "bajo_stock": bajo_stock,
        "valor_inventario": valor_inventario,

        "alertas": alertas,
        "movimientos": movimientos,

        "graf_categorias_labels": graf_categorias_labels,
        "graf_categorias_data": graf_categorias_data,

        "graf_valor_labels": graf_valor_labels,
        "graf_valor_data": graf_valor_data,
    }

    return render(request, 'tienda/dashboard_socio.html', context)


def dashboard_dueno(request):
    return render(request, 'tienda/dashboard_dueno.html')


def base_conocimientos(request):
    return render(request, 'tienda/base_conocimientos.html')