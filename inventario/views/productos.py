import json
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from inventario.forms import  ProductoForm, TemporadaForm
from inventario.models import Atributo, Categoria, Inventario, MovimientoInventario, Producto, Producto, Temporada, ValorAtributo, Ubicacion
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
from django.views.decorators.http import require_POST







@login_required
def productos_por_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)

    productos = (
        Inventario.objects
        .filter(ubicacion=ubicacion, producto__activo=True)
        .select_related("producto", "producto__categoria", "producto__categoria_padre")
        .order_by("producto__nombre")
    )

    inventario_todas = (
        Inventario.objects
        .filter(producto__activo=True)
        .select_related("producto", "ubicacion")
        .order_by("producto__nombre")
    )

    inventario_todas_json = list(
        inventario_todas.values(
            "producto_id",
            "ubicacion_id",
            "cantidad_actual"
        )
    )

    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    paginator = Paginator(productos, 20)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    return render(request, "inventario/inventario_ubicacion.html", {
        "ubicacion": ubicacion,
        "productos": page_obj,
        "page_obj":  page_obj,
        "inventario_todas_json": inventario_todas_json,
        "ubicaciones": ubicaciones,
        "color_header": color_from_name(ubicacion.nombre),
    })



@login_required
def detalle_producto(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    inventarios = (
        Inventario.objects
        .filter(producto=producto, cantidad_actual__gt=0)
        .select_related("ubicacion")
    )

    valores_qs = (
        ValorAtributo.objects
        .filter(producto=producto)
        .select_related("atributo")
    )

    valores = {v.atributo.id: v for v in valores_qs}
    sub_atributos = producto.categoria.atributos.all()

    empleado = getattr(request.user, "empleado", None)
    puede_editar = empleado and empleado.rol == "dueño"

    if request.method == "POST" and puede_editar:

        # ⭐ Guardado solo del costo
        if request.POST.get("solo_costo"):
            costo = request.POST.get("costo", "").strip()
            producto.costo = costo if costo else None
            producto.save(update_fields=["costo"])
            messages.success(request, "Costo guardado.")
            return redirect("inventario:detalle_producto", producto_id=producto.id)

        # Guardado general
        producto.nombre = request.POST.get("nombre", producto.nombre)
        producto.descripcion = request.POST.get("descripcion", producto.descripcion)

        precio_menudeo_raw = request.POST.get("precio_menudeo", "").strip()
        if precio_menudeo_raw:
            producto.precio_menudeo = precio_menudeo_raw

        precio_mayoreo_raw = request.POST.get("precio_mayoreo", "").strip()
        if precio_mayoreo_raw:
            producto.precio_mayoreo = precio_mayoreo_raw

        precio_docena_raw = request.POST.get("precio_docena", "").strip()
        producto.precio_docena = precio_docena_raw if precio_docena_raw else None

        producto.save()

        for attr in sub_atributos:
            field_name = f"attr_{attr.nombre}"
            if field_name in request.POST:
                nuevo_valor = request.POST.get(field_name).strip()
                if attr.id in valores:
                    val_obj = valores[attr.id]
                    val_obj.valor = nuevo_valor
                    val_obj.save()
                else:
                    ValorAtributo.objects.create(
                        producto=producto,
                        atributo=attr,
                        valor=nuevo_valor
                    )

        messages.success(request, "Cambios guardados correctamente.")
        return redirect("inventario:detalle_producto", producto_id=producto.id)

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
    productos = (
        Producto.objects
        .filter(activo=True)
        .select_related(
            'registrado_por__user',
            'dueño__user',
            'categoria',
            'categoria__padre',
            'categoria_padre',
        )
        .prefetch_related(
            'inventarios__ubicacion',
            'temporada'
        )
    )

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

    empleados = Empleado.objects.select_related('user').all()
    dueños = empleados.filter(rol='dueño')
    registradores = empleados.exclude(rol='dueño')
    categorias_padre = Categoria.objects.filter(padre__isnull=True)
    subcategorias = Categoria.objects.filter(padre__isnull=False)
    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    return render(request, 'inventario/productos.html', {
        'productos':        productos,
        'empleados':        empleados,
        'dueños':           dueños,
        'registradores':    registradores,
        'categorias_padre': categorias_padre,
        'subcategorias':    subcategorias,
        'ubicaciones':      ubicaciones,
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
                # Solo enteros en sugerencias — decimales se guardan exactos
                solo_num = re.findall(r"[0-9]+(?:\.[0-9]+)?", s)
                if solo_num:
                    try:
                        num = float(solo_num[0])
                        # Si tiene decimales → mostrar exacto, no redondear
                        s = str(num) if num != int(num) else str(int(num))
                    except Exception:
                        s = AtributoService.normalizar_texto(s)
                else:
                    s = AtributoService.normalizar_texto(s)
            else:
                # Texto — incluyendo códigos como 8.11, 8.12
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

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    sucursal_actual = request.session.get("sucursal_actual")

    form = ProductoForm(
        request.POST,
        request.FILES,
        initial={"sucursal_actual": sucursal_actual}
    )
    form.request = request

    if not form.is_valid():
        if is_ajax:
            errores = [e for errs in form.errors.values() for e in errs]
            return JsonResponse({"success": False, "errors": errores})
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
            if is_ajax:
                return JsonResponse({"success": False, "errors": e.messages})
            messages.error(request, str(e))
            return render(request, "inventario/nuevo_producto.html", contexto(form))

        url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
        redirect_url = f"{url}?highlight={producto.id}&new=1"
        if is_ajax:
            return JsonResponse({"success": True, "redirect": redirect_url})
        return redirect(redirect_url)

    # ============================
    # CASO 2: Código interno
    # ============================

    tam = form.cleaned_data.get("tamano_etiqueta")
    if not tam:
        if is_ajax:
            return JsonResponse({"success": False, "errors": ["Debes seleccionar un tamaño de etiqueta."]})
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
        if is_ajax:
            return JsonResponse({"success": False, "errors": e.messages})
        messages.error(request, str(e))
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
    redirect_url = f"{url}?highlight={producto.id}&new=1"
    if is_ajax:
        return JsonResponse({"success": True, "redirect": redirect_url})
    return redirect(redirect_url)





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
    
    
    
    
# ============================================================
# LISTA DE PRODUCTOS INACTIVOS
# ============================================================
 
@login_required
def productos_inactivos(request):
    empleado = request.user.empleado

    if empleado.rol not in ["dueño", "cajero", "almacenista"]:
        messages.error(request, "No tienes permiso para ver esta sección.")
        return redirect("tienda_temp:dashboard_socio")

    productos = (
        Producto.objects
        .filter(activo=False)
        .select_related(
            "categoria",
            "categoria_padre",
            "dueño",
            "desactivado_por"
        )
        .order_by("nombre")
    )

    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    paginator = Paginator(productos, 20)
    page_obj  = paginator.get_page(request.GET.get("page", 1))

    return render(request, "inventario/productos_inactivos.html", {
        "productos":  page_obj,
        "page_obj":   page_obj,
        "ubicaciones": ubicaciones,
    })
 
# ============================================================
# REACTIVAR PRODUCTO
# ============================================================
 
@login_required
@require_POST
def reactivar_producto(request, producto_id):
    """
    Reactiva un producto inactivo y le asigna inventario
    en la ubicación y cantidad indicadas.
    """
    empleado = request.user.empleado
 
    if empleado.rol not in ["dueño"]:
        return JsonResponse({"success": False, "errors": "Sin permiso."}, status=403)
 
    producto = get_object_or_404(Producto, id=producto_id, activo=False)
 
    try:
        data = json.loads(request.body)
        ubicacion_id = data.get("ubicacion_id")
        cantidad = int(data.get("cantidad", 0))
    except Exception:
        return JsonResponse({"success": False, "errors": "JSON inválido."}, status=400)
 
    if not ubicacion_id:
        return JsonResponse({"success": False, "errors": "Debes seleccionar una ubicación."}, status=400)
 
    if cantidad <= 0:
        return JsonResponse({"success": False, "errors": "La cantidad debe ser mayor a 0."}, status=400)
 
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
 
    # Reactivar el producto
    producto.reactivar()
 
    # Asignar o actualizar inventario en la ubicación seleccionada
    inv, created = Inventario.objects.get_or_create(
        producto=producto,
        ubicacion=ubicacion,
        defaults={"cantidad_actual": cantidad}
    )
 
    if not created:
        inv.cantidad_actual += cantidad
        inv.save()
 
    # Registrar movimiento
    MovimientoInventario.objects.create(
        producto=producto,
        tipo="entrada",
        motivo="reabastecimiento",
        cantidad=cantidad,
        destino=ubicacion,
        realizado_por=empleado,
    )
 
    return JsonResponse({
        "success": True,
        "mensaje": f"Producto '{producto.nombre}' reactivado con {cantidad} unidades en {ubicacion.nombre}."
    })
 
 
# ============================================================
# ELIMINAR PRODUCTO DEFINITIVO (HARD DELETE)
# ============================================================
 
@login_required
@require_http_methods(["DELETE"])
def eliminar_producto_definitivo(request, producto_id):
    """
    Elimina un producto COMPLETAMENTE de la base de datos.
    Solo disponible para productos inactivos.
    Solo dueño puede hacerlo.
    """
    empleado = request.user.empleado
 
    if empleado.rol not in ["dueño"]:
        return JsonResponse({"success": False, "errors": "Sin permiso."}, status=403)
 
    producto = get_object_or_404(Producto, id=producto_id, activo=False)
 
    nombre = producto.nombre
    producto.delete()
 
    return JsonResponse({
        "success": True,
        "mensaje": f"Producto '{nombre}' eliminado definitivamente."
    })
    

@login_required
@require_POST
def desactivar_producto(request, producto_id):
    """
    Desactiva un producto (soft delete).
    Recibe el motivo desde el modal via JSON.
    Solo dueño, cajero y almacenista pueden desactivar.
    """
    empleado = request.user.empleado

    # Validar rol
    roles_permitidos = ["dueño", "cajero", "almacenista"]
    if empleado.rol not in roles_permitidos:
        return JsonResponse({"success": False, "errors": "No tienes permiso para desactivar productos."}, status=403)

    producto = Producto.objects.filter(id=producto_id).first()
    if not producto:
        return JsonResponse({"success": False, "errors": "El producto no existe."}, status=404)

    if not producto.activo:
        return JsonResponse({"success": False, "errors": "El producto ya está desactivado."}, status=400)

    try:
        data = json.loads(request.body)
        motivo = data.get("motivo", "").strip()
    except Exception:
        return JsonResponse({"success": False, "errors": "JSON inválido."}, status=400)

    if not motivo:
        return JsonResponse({"success": False, "errors": "El motivo es obligatorio."}, status=400)

    # Desactivar usando el método del modelo
    producto.desactivar(empleado=empleado, motivo=motivo)

    return JsonResponse({
        "success": True,
        "mensaje": f"Producto '{producto.nombre}' desactivado correctamente."
    })
    



