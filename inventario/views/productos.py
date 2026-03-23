from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from inventario.forms import  ProductoForm, TemporadaForm
from inventario.models import Atributo, Categoria, Inventario, Producto, Producto, Temporada, ValorAtributo, Ubicacion
from inventario.services.barcode_render_service import BarcodeRenderService
from tienda_temp.models import Empleado
from inventario.services.producto_service import ProductService
from inventario.services.codigo_service import CodigoService
from inventario.services.etiqueta_service import EtiquetaService
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from tienda_temp.models import Empleado
from inventario.models import Categoria
from inventario.utils import color_from_name
from django.urls import reverse
from rapidfuzz import process, fuzz
from inventario.services.atributo_service import AtributoService
from inventario.models import ValorAtributo, Atributo, Categoria
import re






@login_required
def productos_por_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    productos = (
        Inventario.objects
        .filter(ubicacion=ubicacion)
        .select_related("producto", "producto__categoria", "producto__categoria_padre")
        .order_by("producto__nombre")
    )

    inventario_todas = (
        Inventario.objects
        .select_related("producto", "ubicacion")
        .order_by("producto__nombre")
    )

    # ⭐ SERIALIZAR AQUÍ
    inventario_todas_json = list(
        inventario_todas.values(
            "producto_id",
            "ubicacion_id",
            "cantidad_actual"
        )
    )

    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    return render(request, "inventario/inventario_ubicacion.html", {
        "ubicacion": ubicacion,
        "productos": productos,
        "inventario_todas_json": inventario_todas_json,   # ⭐ ESTO SE ENVÍA
        "ubicaciones": ubicaciones,
        "color_header": color_from_name(ubicacion.nombre),
    })



@login_required
def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    # Inventarios por ubicación
    inventarios = (
        Inventario.objects
        .filter(producto=producto)
        .select_related("ubicacion")
    )

    # Valores actuales del producto
    valores_qs = (
        ValorAtributo.objects
        .filter(producto=producto)
        .select_related("atributo")
    )

    valores = {v.atributo.id: v for v in valores_qs}

    # Atributos de la subcategoría
    sub_atributos = producto.categoria.atributos.all()

    # Permisos
    empleado = getattr(request.user, "empleado", None)
    puede_editar = empleado and empleado.rol == "dueño"

    # ============================
    # GUARDAR CAMBIOS (solo dueño)
    # ============================
    if request.method == "POST" and puede_editar:

        # 1. Guardar datos del producto
        producto.nombre = request.POST.get("nombre", producto.nombre)
        producto.descripcion = request.POST.get("descripcion", producto.descripcion)
        producto.precio_menudeo = request.POST.get("precio_menudeo", producto.precio_menudeo)
        producto.precio_mayoreo = request.POST.get("precio_mayoreo", producto.precio_mayoreo)
        producto.precio_docena = request.POST.get("precio_docena", producto.precio_docena)
        producto.save()

        # 2. Guardar valores de atributos
        for attr in sub_atributos:
            field_name = f"attr_{attr.nombre}"

            if field_name in request.POST:
                nuevo_valor = request.POST.get(field_name).strip()

                if attr.id in valores:
                    # Ya existe → actualizar
                    val_obj = valores[attr.id]
                    val_obj.valor = nuevo_valor
                    val_obj.save()
                else:
                    # No existe → crear
                    ValorAtributo.objects.create(
                        producto=producto,
                        atributo=attr,
                        valor=nuevo_valor
                    )

        messages.success(request, "Cambios guardados correctamente.")
        return redirect("inventario:detalle_producto", producto_id=producto.id)

    # ============================
    # PREPARAR DATOS PARA EL TEMPLATE
    # ============================
    atributos = []
    for attr in sub_atributos:
        atributos.append({
            "id": attr.id,
            "nombre": attr.nombre,
            "valor": valores.get(attr.id).valor if attr.id in valores else None
        })

    return render(request, "inventario/detalle_producto.html", {
        "producto": producto,
        "inventarios": inventarios,
        "atributos": atributos,
        "puede_editar": puede_editar,
    })



@login_required
def lista_productos(request):
    # Base queryset con relaciones optimizadas
    productos = (
        Producto.objects
        .select_related(
            'registrado_por__user',
            'dueño__user',
            'categoria',
            'categoria__padre'
        )
        .prefetch_related(
            'inventarios__ubicacion',
            'temporada'
        )
        .all()
    )

    # Filtros GET
    dueño_id = request.GET.get('dueño')
    registrado_por_id = request.GET.get('usuario')
    categoria_padre_id = request.GET.get('categoria_padre')
    subcategoria_id = request.GET.get('subcategoria')
    precio_tipo = request.GET.get('precio_tipo')
    precio_min = request.GET.get('precio_min')
    precio_max = request.GET.get('precio_max')

    if dueño_id:
        productos = productos.filter(dueño__id=dueño_id)

    if registrado_por_id:
        productos = productos.filter(registrado_por__id=registrado_por_id)

    if subcategoria_id:
        productos = productos.filter(categoria__id=subcategoria_id)

    if categoria_padre_id:
        productos = productos.filter(categoria__padre__id=categoria_padre_id)

    if precio_tipo in ['menudeo', 'mayoreo', 'docena']:
        if precio_min:
            productos = productos.filter(**{f'precio_{precio_tipo}__gte': precio_min})
        if precio_max:
            productos = productos.filter(**{f'precio_{precio_tipo}__lte': precio_max})

    # Datos para filtros
    empleados = Empleado.objects.select_related('user').all()
    dueños = empleados.filter(rol='dueño')
    registradores = empleados.exclude(rol='dueño')
    categorias_padre = Categoria.objects.filter(padre__isnull=True)
    subcategorias = Categoria.objects.filter(padre__isnull=False)

    # 🔥 UBICACIONES DINÁMICAS (la parte que arregla TODO)
    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    return render(request, 'inventario/productos.html', {
        'productos': productos,
        'empleados': empleados,
        'dueños': dueños,
        'registradores': registradores,
        'categorias_padre': categorias_padre,
        'subcategorias': subcategorias,

        # 🔥 ahora el template recibe TODAS las ubicaciones
        'ubicaciones': ubicaciones,
    })
    

   
@login_required
def mis_productos(request):
    empleado = request.user.empleado

    if empleado.rol != "dueño":
        return HttpResponseForbidden("No tienes permiso para ver esta vista")

    # Productos solo del dueño
    productos = (
        Producto.objects
        .filter(dueño=empleado)
        .select_related(
            'registrado_por__user',
            'dueño__user',
            'categoria',
            'categoria__padre'
        )
        .prefetch_related('inventarios__ubicacion', 'temporada')
    )

    # Ubicaciones dinámicas
    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    return render(request, 'inventario/mis_productos.html', {
        'productos': productos,
        'ubicaciones': ubicaciones,
    })
    
    
    
@login_required
def nuevo_producto(request):

    # ============================
    # Helpers internos
    # ============================

    def agrupar_fuzzy_global(valores):
        grupos = []
        for v in valores:
            agregado = False
            for g in grupos:
                mejor, score, _ = process.extractOne(v, g, scorer=fuzz.WRatio)
                if score >= 85:
                    g.append(v)
                    agregado = True
                    break
            if not agregado:
                grupos.append([v])
        return [g[0] for g in grupos]

    def valores_unicos_por_atributo(atributo):
        valores = (
            ValorAtributo.objects
            .filter(atributo=atributo)
            .values_list("valor", flat=True)
        )

        normalizados = []
        tipo_attr = (atributo.tipo or "").strip().lower()

        for v in valores:
            if v is None:
                continue

            s = str(v).strip()

            if tipo_attr == "numero":
                solo_num = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)
                if solo_num:
                    try:
                        num = float(solo_num[0])
                        s = str(int(num)) if num.is_integer() else str(num)
                    except:
                        s = AtributoService.normalizar_texto(s)
                else:
                    s = AtributoService.normalizar_texto(s)
            else:
                s = AtributoService.normalizar_texto(s)

            normalizados.append(s)

        agrupados = agrupar_fuzzy_global(normalizados)
        return sorted(set(agrupados))

    def contexto(form):
        atributos = Atributo.objects.all()
        for atributo in atributos:
            atributo.valores_unicos = valores_unicos_por_atributo(atributo)

        return {
            "form": form,
            "categorias_padre": Categoria.objects.filter(padre__isnull=True),
            "subcategorias": Categoria.objects.all(),
            "atributos": atributos,
            "ETIQUETAS": EtiquetaService.ETIQUETAS,
        }

    # ============================
    # GET → mostrar formulario
    # ============================

    if request.method == "GET":
        sucursal_actual = request.session.get("sucursal_actual")
        form = ProductoForm(initial={"sucursal_actual": sucursal_actual})
        form.request = request
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    # ============================
    # POST → procesar formulario
    # ============================

    sucursal_actual = request.session.get("sucursal_actual")

    form = ProductoForm(
        request.POST,
        request.FILES,
        initial={"sucursal_actual": sucursal_actual}
    )
    form.request = request

    if not form.is_valid():
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    # ============================
    # CASO 1: Código externo
    # ============================

    codigo_usuario = form.cleaned_data.get("codigo_barras")

    if codigo_usuario:
        tipo = form.cleaned_data.get("tipo_codigo")
        tam = CodigoService.tamano_por_tipo(tipo)

        try:
            producto, ubicacion = ProductService.crear_producto_desde_formulario(
                form,
                request,
                codigo_generado=codigo_usuario,
                tipo_codigo=tipo,
                tamano_etiqueta=tam
            )
        except ValidationError as e:
            messages.error(request, str(e))
            return render(request, "inventario/nuevo_producto.html", contexto(form))

        messages.success(request, "Producto registrado correctamente.")
        url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
        return redirect(f"{url}?highlight={producto.id}&new=1")

    # ============================
    # CASO 2: Código interno
    # ============================

    tam = form.cleaned_data.get("tamano_etiqueta")
    if not tam:
        messages.error(request, "Debes seleccionar un tamaño de etiqueta.")
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    sub = form.cleaned_data["subcategoria"]
    dueño = request.user.empleado

    codigo, tipo = CodigoService.generar_codigo_interno(
        tamaño=tam,
        dueño=dueño,
        subcategoria=sub
    )

    try:
        producto, ubicacion = ProductService.crear_producto_desde_formulario(
            form,
            request,
            codigo_generado=codigo,
            tipo_codigo=tipo,
            tamano_etiqueta=tam
        )
    except ValidationError as e:
        messages.error(request, str(e))
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    messages.success(request, "Producto registrado correctamente.")

    url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
    return redirect(f"{url}?highlight={producto.id}&new=1")





#Ajax que trae los datos del producto dado un codigo de barras, para llenar el formulario de nuevo producto
@login_required
def buscar_producto_por_codigo(request):
    codigo = request.GET.get('codigo')

    producto = (
        Producto.objects
        .select_related('categoria', 'dueño')
        .filter(codigo_barras=codigo)
        .first()
    )

    if not producto:
        return JsonResponse({'existe': False})

    # Categoría y subcategoría
    subcategoria = producto.categoria
    categoria_padre = subcategoria.padre if subcategoria else None

    # Atributos definidos para la subcategoría
    atributos_definidos = Atributo.objects.filter(categoria=subcategoria)

    # Cargar todos los valores del producto en una sola query
    valores = ValorAtributo.objects.filter(producto=producto)
    valores_dict = {v.atributo_id: v.valor for v in valores}

    atributos_list = [
        {
            'id': atributo.id,
            'nombre': atributo.nombre,
            'valor': valores_dict.get(atributo.id, '')
        }
        for atributo in atributos_definidos
    ]

    return JsonResponse({
        'existe': True,
        'producto_id': producto.id,
        'nombre': producto.nombre,
        'descripcion': producto.descripcion,
        'precio_menudeo': producto.precio_menudeo,
        'precio_mayoreo': producto.precio_mayoreo,
        'precio_docena': producto.precio_docena,
        'tipo_codigo': producto.tipo_codigo,
        'temporadas': list(producto.temporada.values_list("id", flat=True)),
        'foto_url': producto.foto_url.url if producto.foto_url else None,
        'duenio_id': producto.dueño_id,
        'categoria_padre_id': categoria_padre.id if categoria_padre else None,
        'categoria_padre_nombre': categoria_padre.nombre if categoria_padre else None,
        'subcategoria_id': subcategoria.id if subcategoria else None,
        'subcategoria_nombre': subcategoria.nombre if subcategoria else None,
        'atributos': atributos_list,
    })
    
    


    
import traceback   
#VISTA API PARA VER LOS CODIGOS EN EL FRONT DE MANERA FLUIDA
@login_required
def codigo_base64(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    try:
        imagen = BarcodeRenderService.generar(
            codigo=producto.codigo_barras,          # ← ESTE ES EL CAMBIO
            tipo=producto.tipo_codigo,
            tamaño=producto.tamano_etiqueta,
        )

        return JsonResponse({'imagen': imagen})

    except Exception as e:
        print("\n\n🔥 ERROR GENERANDO CÓDIGO DE BARRAS 🔥")
        print(f"Producto ID: {producto.id}")
        print(f"Codigo: {producto.codigo_barras}")
        print(f"Tipo: {producto.tipo_codigo}")
        print(f"Tamaño: {producto.tamaño_etiqueta}")
        traceback.print_exc()
        print("🔥 FIN DEL ERROR 🔥\n\n")

        return JsonResponse({'error': str(e)}, status=500)




# Vista encargada del formulario de temporadas y de mostrarlas a usuarios empleados normales.
@login_required
def temporada_view(request):
    user = request.user

    es_dueno = hasattr(user, "empleado") and user.empleado.rol == "dueño"
    es_empleado = hasattr(user, "empleado")

    if not (es_dueno or es_empleado):
        raise PermissionDenied("No tienes permiso para ver esta página.")

    # Ya no existe fecha_inicio → ordenamos por nombre
    temporadas = Temporada.objects.order_by("nombre")

    # Solo el dueño puede ver el formulario
    form = TemporadaForm() if es_dueno else None

    if request.method == "POST":
        if not es_dueno:
            raise PermissionDenied("No tienes permiso para modificar temporadas.")

        temporada_id = request.POST.get("temporada_id")

        if temporada_id:
            temporada = get_object_or_404(Temporada, id=temporada_id)
            form = TemporadaForm(request.POST, instance=temporada)
        else:
            form = TemporadaForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "Temporada guardada correctamente.")
            return redirect("inventario:temporadas")

    return render(request, "inventario/temporadas.html", {
        "temporadas": temporadas,
        "form": form,
        "solo_lectura": not es_dueno,
        "mostrar_formulario": es_dueno,
    })
    
    
@login_required
def eliminar_producto_completo(request, producto_id):
    if request.method != "DELETE":
        return JsonResponse(
            {"success": False, "errors": ["Método no permitido"]},
            status=405
        )

    producto = Producto.objects.filter(id=producto_id).first()

    if not producto:
        return JsonResponse({
            "success": False,
            "errors": ["El producto no existe."]
        })

    producto.delete()

    return JsonResponse({"success": True})