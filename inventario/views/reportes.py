from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from inventario.models import Categoria, Inventario, Temporada, Ubicacion
from tienda_temp.models import Empleado
from inventario.services.filtros_service import parse_filtros, nombres_filtros
from inventario.services.pdf_renderer import generar_pdf, exportar_criticos_pdf
from inventario.services.reporte_service import get_datos_reporte





@login_required
def reportes(request):
    filtros = parse_filtros(request)

    datos = get_datos_reporte(
        filtros["tipo"],
        categoria_id=filtros["categoria"],
        subcategoria_id=filtros["subcategoria"],
        temporada_id=filtros["temporada"],
        ubicacion_id=filtros["ubicacion"],
        dueño_id=filtros["dueño"],
        movimiento_tipo=filtros["movimiento"],
    )

    contexto = {
        # Datos del reporte
        "tipo_reporte": filtros["tipo"],
        "datos": datos,

        # Filtros procesados
        "filtros": filtros,
        "filtros_legibles": nombres_filtros(filtros),

        # Filtros individuales (para mantener el estado del formulario)
        "filtro_categoria": filtros["categoria"],
        "filtro_subcategoria": filtros["subcategoria"],
        "filtro_temporada": filtros["temporada"],
        "filtro_ubicacion": filtros["ubicacion"],
        "filtro_dueno": filtros["dueño"],
        "filtro_movimiento": filtros["movimiento"],

        # Catálogos
        "categorias_padre": Categoria.objects.filter(padre__isnull=True),
        "temporadas": Temporada.objects.all(),
        "ubicaciones": Ubicacion.objects.all(),
        "dueños": Empleado.objects.all(),
    }

    return render(request, "inventario/reportes.html", contexto)






#Creo es el boton para generar el PDF y descargarlo.
@login_required
def reporte_pdf(request):
    # 1) Parsear filtros desde GET
    filtros = parse_filtros(request)

    # 2) Tipo de reporte
    tipo_reporte = filtros.get("tipo", "")

    # 3) Usuario que genera el PDF
    usuario = request.user.get_full_name() or request.user.username

    # 4) Generar PDF usando el renderer correcto
    return generar_pdf(
        tipo_reporte,
        filtros,
        usuario
    )








#INFORMACION GENERAL DE INVENTARIOS en la vista dashboardInventario.
def exportar_criticos(request):
    usuario = request.user.get_full_name() or request.user.username

    try:
        ubicacion_id = int(request.GET.get("ubicacion_id", 0)) or None
    except ValueError:
        ubicacion_id = None

    # Delegar TODO al servicio de reportes
    return exportar_criticos_pdf(usuario, ubicacion_id)