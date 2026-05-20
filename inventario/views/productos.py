import json
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
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
from ventas.models import IdempotencyKey
import re
from django.views.decorators.http import require_POST







@login_required
def productos_por_ubicacion(request, ubicacion_id):
    ubicacion = get_object_or_404(Ubicacion, id=ubicacion_id)
    q = request.GET.get("q", "").strip()

    productos = (
        Inventario.objects
        .filter(ubicacion=ubicacion, producto__activo=True)
        .select_related("producto", "producto__categoria", "producto__categoria_padre")
        .order_by("producto__nombre")
    )

    if q:
        filtro = (
            Q(producto__nombre__icontains=q) |
            Q(producto__codigo_barras__icontains=q) |
            Q(producto__valores_atributo__valor__icontains=q)
        )
        try:
            filtro |= Q(producto__id=int(q))
        except ValueError:
            pass
        productos = productos.filter(filtro).distinct()

    # Filtro "¿Qué falta?" — excluye productos que ya tienen stock en la ubicación paired
    falta_en_id = None
    falta_en_raw = request.GET.get("falta_en", "").strip()
    if falta_en_raw:
        try:
            falta_en_id = int(falta_en_raw)
            en_paired = Inventario.objects.filter(
                ubicacion_id=falta_en_id,
                cantidad_actual__gt=0,
            ).values_list("producto_id", flat=True)
            productos = productos.exclude(producto__id__in=en_paired)
        except (ValueError, TypeError):
            falta_en_id = None

    # Solo productos que existen en esta ubicación — evita cargar inventario global
    ids_en_ubicacion = list(
        Inventario.objects
        .filter(ubicacion=ubicacion, producto__activo=True)
        .values_list("producto_id", flat=True)
    )

    inventario_todas_json = list(
        Inventario.objects
        .filter(producto_id__in=ids_en_ubicacion)
        .values("producto_id", "ubicacion_id", "cantidad_actual")
    )

    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    # Paired location: bodega ↔ piso within the same sucursal (auto-compare, no select)
    paired_ubicacion = None
    piso_ubicaciones = []

    if ubicacion.sucursal:
        if ubicacion.tipo == "bodega":
            paired_ubicacion = (
                Ubicacion.objects
                .filter(tipo="piso", sucursal=ubicacion.sucursal, activa=True)
                .values("id", "nombre")
                .first()
            )
        elif ubicacion.tipo == "piso":
            paired_ubicacion = (
                Ubicacion.objects
                .filter(tipo="bodega", sucursal=ubicacion.sucursal, activa=True)
                .values("id", "nombre")
                .first()
            )

    if not paired_ubicacion:
        piso_ubicaciones = list(
            Ubicacion.objects
            .filter(activa=True)
            .exclude(id=ubicacion_id)
            .values("id", "nombre")
            .order_by("nombre")
        )

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if is_ajax:
        lista_productos = productos[:200]
        page_obj = None
    else:
        page_number_raw = request.GET.get("page")
        highlight_raw   = request.GET.get("highlight", "").strip()
        is_new          = request.GET.get("new") == "1"
        pinned_inv      = None

        # Pin newly registered/variant product to the top of page 1 — only on the
        # initial redirect (?new=1). The JS clears this param immediately via
        # replaceState so going-back never shows the pin again.
        if highlight_raw and is_new and not page_number_raw:
            try:
                highlight_id = int(highlight_raw)
                found = productos.filter(producto_id=highlight_id).first()
                if found:
                    pinned_inv = found
                    productos  = productos.exclude(producto_id=highlight_id)
            except (ValueError, TypeError):
                pass

        paginator = Paginator(productos, 20)
        page_obj  = paginator.get_page(page_number_raw or 1)
        lista_productos = ([pinned_inv] + list(page_obj)) if pinned_inv else list(page_obj)

    return render(request, "inventario/inventario_ubicacion.html", {
        "ubicacion": ubicacion,
        "productos": lista_productos,
        "page_obj":  page_obj,
        "inventario_todas_json": inventario_todas_json,
        "ubicaciones": ubicaciones,
        "paired_ubicacion": paired_ubicacion,
        "piso_ubicaciones": piso_ubicaciones,
        "color_header": color_from_name(ubicacion.nombre),
        "q": q,
        "falta_en_id": falta_en_id,
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
    rol = getattr(empleado, "rol", None)
    es_dueno  = rol == "dueño"
    es_cajero = rol == "cajero"
    puede_editar = es_dueno or es_cajero

    # Permisos por campo (cajero edita lo básico operativo; dueño todo)
    permisos = {
        "nombre":          puede_editar,
        "descripcion":     puede_editar,
        "atributos":       puede_editar,
        "foto":            puede_editar,
        "precios":         es_dueno,
        "categoria":       es_dueno,
        "dueño":           es_dueno,
        "costo":           es_dueno,
        "codigo_barras":   es_dueno,
    }

    if request.method == "POST" and puede_editar:

        # ⭐ Guardado solo del costo (solo dueño)
        if request.POST.get("solo_costo"):
            if not es_dueno:
                messages.error(request, "No tienes permiso para editar el costo.")
                return redirect("inventario:detalle_producto", producto_id=producto.id)
            costo = request.POST.get("costo", "").strip()
            producto.costo = costo if costo else None
            producto.save(update_fields=["costo"])
            messages.success(request, "Costo guardado.")
            return redirect("inventario:detalle_producto", producto_id=producto.id)

        # Guardado general — campos según rol
        if permisos["nombre"]:
            producto.nombre = request.POST.get("nombre", producto.nombre)
        if permisos["descripcion"]:
            producto.descripcion = request.POST.get("descripcion", producto.descripcion)

        # Foto: cualquiera con permiso de edición puede actualizarla
        if permisos["foto"] and "foto_url" in request.FILES:
            producto.foto_url = request.FILES["foto_url"]

        if permisos["precios"]:
            precio_menudeo_raw = request.POST.get("precio_menudeo", "").strip()
            if precio_menudeo_raw:
                producto.precio_menudeo = precio_menudeo_raw

            precio_mayoreo_raw = request.POST.get("precio_mayoreo", "").strip()
            if precio_mayoreo_raw:
                producto.precio_mayoreo = precio_mayoreo_raw

            precio_docena_raw = request.POST.get("precio_docena", "").strip()
            producto.precio_docena = precio_docena_raw if precio_docena_raw else None

        # ⭐ Cambio de subcategoría (solo dueño — afecta atributos)
        sub_cambio = False
        if permisos["categoria"]:
            sub_id_raw = request.POST.get("subcategoria", "").strip()
            if sub_id_raw and str(producto.categoria_id) != sub_id_raw:
                try:
                    nueva_sub = Categoria.objects.select_related("padre").get(id=sub_id_raw)
                    if nueva_sub.padre_id is not None:
                        producto.categoria = nueva_sub
                        producto.categoria_padre = nueva_sub.padre
                        sub_cambio = True
                except (Categoria.DoesNotExist, ValueError):
                    pass

        # ⭐ Cambio de dueño (solo dueño)
        if permisos["dueño"]:
            dueno_id_raw = request.POST.get("dueño", "").strip()
            if dueno_id_raw and str(producto.dueño_id) != dueno_id_raw:
                try:
                    producto.dueño = Empleado.objects.get(id=dueno_id_raw, rol="dueño")
                except (Empleado.DoesNotExist, ValueError):
                    pass

        producto.save()

        # Si la sub cambió, los atributos a procesar son los de la NUEVA sub.
        # Y borramos ValorAtributo huérfanos (de atributos que ya no aplican).
        if sub_cambio:
            atributos_actuales_ids = set(producto.categoria.atributos.values_list("id", flat=True))
            ValorAtributo.objects.filter(producto=producto).exclude(
                atributo_id__in=atributos_actuales_ids
            ).delete()
            sub_atributos = producto.categoria.atributos.all()
            valores = {
                v.atributo.id: v
                for v in ValorAtributo.objects.filter(producto=producto)
            }

        if permisos["atributos"]:
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

        nueva_firma = ProductService._generar_firma(producto)
        conflicto = Producto.objects.filter(firma_unica=nueva_firma).exclude(pk=producto.pk).first()
        if conflicto:
            messages.error(request, f"Los atributos coinciden con un producto existente: {conflicto.nombre} (ID {conflicto.id}).")
            return redirect("inventario:detalle_producto", producto_id=producto.id)

        producto.firma_unica = nueva_firma
        producto.save(update_fields=["firma_unica"])
        messages.success(request, "Cambios guardados correctamente.")

        max_inv = (
            Inventario.objects
            .filter(producto=producto)
            .order_by("-cantidad_actual")
            .select_related("ubicacion")
            .first()
        )
        if max_inv:
            ubicacion_id = max_inv.ubicacion.id
            ids = list(
                Inventario.objects
                .filter(ubicacion_id=ubicacion_id, producto__activo=True)
                .order_by("producto__nombre")
                .values_list("producto_id", flat=True)
            )
            pos = ids.index(producto.id) if producto.id in ids else 0
            page = (pos // 20) + 1
            url = reverse("inventario:productos_por_ubicacion", kwargs={"ubicacion_id": ubicacion_id})
            return redirect(f"{url}?page={page}&highlight={producto.id}&toast=Cambios+guardados+%E2%9C%93")
        return redirect("inventario:detalle_producto", producto_id=producto.id)

    atributos = []
    for attr in sub_atributos:
        atributos.append({
            "id": attr.id,
            "nombre": attr.nombre,
            "valor": valores.get(attr.id).valor if attr.id in valores else None
        })

    # ⭐ Datos para los selects editables (solo si puede_editar, pero rendereamos siempre sin costo extra)
    categorias_padre = list(Categoria.objects.filter(padre__isnull=True).order_by("nombre"))
    subcategorias    = list(
        Categoria.objects.filter(padre__isnull=False)
        .select_related("padre")
        .order_by("nombre")
    )
    dueños = list(
        Empleado.objects
        .filter(rol="dueño")
        .select_related("user")
        .order_by("user__first_name")
    )
    atributos_todos = list(
        Atributo.objects.select_related("categoria").order_by("categoria_id", "nombre")
    )

    return render(request, "inventario/detalle_producto.html", {
        "producto": producto,
        "inventarios": inventarios,
        "atributos": atributos,
        "puede_editar": puede_editar,
        "es_dueno": es_dueno,
        "es_cajero": es_cajero,
        "permisos": permisos,
        "categorias_padre": categorias_padre,
        "subcategorias": subcategorias,
        "dueños": dueños,
        "atributos_todos": atributos_todos,
    })


@login_required
def lista_productos(request):
    from django.db.models import Case, When, IntegerField, Value

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
    q = (request.GET.get('q') or "").strip()

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

    # ============================
    # BÚSQUEDA DE TEXTO LIBRE — con ranking por relevancia
    # Match en nombre o código pesa más que match en atributo/categoría.
    # ============================
    if q:
        from django.db.models import Max

        codigos_exactos = [q]
        if q.isdigit():
            if len(q) == 12:
                codigos_exactos.append("0" + q)
            elif len(q) == 13 and q.startswith("0"):
                codigos_exactos.append(q[1:])

        productos = productos.filter(
            Q(nombre__icontains=q)
            | Q(codigo_barras__in=codigos_exactos)
            | Q(codigo_barras__icontains=q)
            | Q(categoria__nombre__icontains=q)
            | Q(categoria__padre__nombre__icontains=q)
            | Q(temporada__nombre__icontains=q)
            | Q(valores_atributo__valor__icontains=q)
        ).annotate(
            # Max(Case()) agrega sobre joins M2M: si un producto matchea por
            # múltiples rutas (nombre Y atributo), se queda con la relevancia
            # más alta. Esto también colapsa duplicados sin necesidad de distinct().
            relevancia=Max(Case(
                When(codigo_barras__in=codigos_exactos,         then=Value(100)),
                When(nombre__icontains=q,                       then=Value(90)),
                When(codigo_barras__icontains=q,                then=Value(80)),
                When(categoria__nombre__icontains=q,            then=Value(50)),
                When(categoria__padre__nombre__icontains=q,     then=Value(40)),
                When(temporada__nombre__icontains=q,            then=Value(30)),
                When(valores_atributo__valor__icontains=q,      then=Value(20)),
                default=Value(0),
                output_field=IntegerField(),
            ))
        ).order_by('-relevancia', 'nombre')

    paginator = Paginator(productos, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    params = request.GET.copy()
    params.pop('page', None)
    query_string = params.urlencode()

    empleados = Empleado.objects.select_related('user').all()
    dueños = empleados.filter(rol='dueño')
    registradores = empleados.exclude(rol='dueño')
    categorias_padre = Categoria.objects.filter(padre__isnull=True)
    subcategorias = Categoria.objects.filter(padre__isnull=False)
    ubicaciones = Ubicacion.objects.all().order_by("nombre")

    return render(request, 'inventario/productos.html', {
        'productos':        page_obj,
        'page_obj':         page_obj,
        'query_string':     query_string,
        'empleados':        empleados,
        'dueños':           dueños,
        'registradores':    registradores,
        'categorias_padre': categorias_padre,
        'subcategorias':    subcategorias,
        'ubicaciones':      ubicaciones,
    })


@login_required
def api_stock_global(request):
    ids_param = request.GET.get('ids', '')
    ids = [int(i) for i in ids_param.split(',') if i.strip().isdigit()]
    if not ids:
        return JsonResponse({})
    inventarios = (
        Inventario.objects
        .filter(producto_id__in=ids)
        .values('producto_id', 'ubicacion_id', 'cantidad_actual')
    )
    resultado = {}
    for inv in inventarios:
        pid = str(inv['producto_id'])
        uid = str(inv['ubicacion_id'])
        if pid not in resultado:
            resultado[pid] = {}
        resultado[pid][uid] = inv['cantidad_actual']
    return JsonResponse(resultado)
    

   
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

    # ============================
    # IDEMPOTENCY: claim del token antes de procesar
    # ============================
    idem_obj = None
    if is_ajax:
        idem_key = request.POST.get("idempotency_key")
        empleado_idem = getattr(request.user, "empleado", None)
        idem_obj, cached = IdempotencyKey.claim(idem_key, "nuevo_producto", empleado_idem)
        if cached is not None:
            status = cached.pop("__status", 200)
            return JsonResponse(cached, status=status)

    def respond_ajax(data, status=200):
        """Devuelve JSON y commitea/libera la llave idempotente según éxito."""
        if idem_obj:
            if data.get("success"):
                idem_obj.commit(data, status_code=status)
            else:
                idem_obj.release()
        return JsonResponse(data, status=status)

    form = ProductoForm(
        request.POST,
        request.FILES,
        initial={"sucursal_actual": sucursal_actual}
    )
    form.request = request

    if not form.is_valid():
        if is_ajax:
            errores = [e for errs in form.errors.values() for e in errs]
            return respond_ajax({"success": False, "errors": errores})
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
                return respond_ajax({"success": False, "errors": e.messages})
            messages.error(request, str(e))
            return render(request, "inventario/nuevo_producto.html", contexto(form))
        except Exception as e:
            import traceback; traceback.print_exc()
            if is_ajax:
                return respond_ajax({"success": False, "errors": [f"Error interno: {type(e).__name__}: {e}"]})
            messages.error(request, "El servidor encontró un error interno. Intenta de nuevo.")
            return render(request, "inventario/nuevo_producto.html", contexto(form))

        from urllib.parse import quote
        cantidad_ini = form.cleaned_data.get("cantidad_inicial") or 0
        url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
        toast = quote(f"➕ Producto creado con {cantidad_ini} piezas iniciales")
        redirect_url = f"{url}?highlight={producto.id}&new=1&toast={toast}"
        if is_ajax:
            return respond_ajax({"success": True, "redirect": redirect_url})
        return redirect(redirect_url)

    # ============================
    # CASO 2: Código interno
    # ============================

    tam = form.cleaned_data.get("tamano_etiqueta")
    if not tam:
        if is_ajax:
            return respond_ajax({"success": False, "errors": ["Debes seleccionar un tamaño de etiqueta."]})
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
            return respond_ajax({"success": False, "errors": e.messages})
        messages.error(request, str(e))
        return render(request, "inventario/nuevo_producto.html", contexto(form))
    except Exception:
        if is_ajax:
            return respond_ajax({"success": False, "errors": ["El servidor encontró un error interno. Intenta de nuevo."]})
        messages.error(request, "El servidor encontró un error interno. Intenta de nuevo.")
        return render(request, "inventario/nuevo_producto.html", contexto(form))

    from urllib.parse import quote
    cantidad_ini = form.cleaned_data.get("cantidad_inicial") or 0
    url = reverse("inventario:productos_por_ubicacion", args=[ubicacion.id])
    toast = quote(f"➕ Producto creado con {cantidad_ini} piezas iniciales")
    redirect_url = f"{url}?highlight={producto.id}&new=1&toast={toast}"
    if is_ajax:
        return respond_ajax({"success": True, "redirect": redirect_url})
    return redirect(redirect_url)





#Ajax que trae los datos del producto dado un codigo de barras, para llenar el formulario de nuevo producto
@login_required
def buscar_producto_por_codigo(request):
    codigo = (request.GET.get('codigo') or "").strip()

    # Búsqueda dual: si el código es UPC-A de 12 dígitos, también buscar
    # su forma EAN-13 (con 0 al frente), y viceversa. Esto encuentra
    # productos viejos guardados en cualquiera de los dos formatos.
    codigos_buscar = [codigo]
    if codigo and codigo.isdigit():
        if len(codigo) == 12:
            codigos_buscar.append("0" + codigo)
        elif len(codigo) == 13 and codigo.startswith("0"):
            codigos_buscar.append(codigo[1:])

    productos = list(
        Producto.objects
        .select_related('categoria', 'categoria__padre', 'dueño')
        .prefetch_related('temporada')
        .filter(codigo_barras__in=codigos_buscar, activo=True)
        .order_by('nombre', 'id')
    )

    if not productos:
        return JsonResponse({'existe': False, 'variantes': []})

    # Cargar todos los valores de atributo para todas las variantes en una sola query
    valores = ValorAtributo.objects.filter(producto__in=productos).select_related('atributo')
    valores_por_producto = {}
    for v in valores:
        valores_por_producto.setdefault(v.producto_id, []).append(v)

    variantes = []
    for producto in productos:
        subcategoria = producto.categoria
        categoria_padre = subcategoria.padre if subcategoria else None

        # Atributos definidos para la subcategoría (todos los slots)
        atributos_definidos = Atributo.objects.filter(categoria=subcategoria)

        valores_dict = {
            v.atributo_id: v.valor
            for v in valores_por_producto.get(producto.id, [])
        }

        atributos_list = [
            {
                'id': atributo.id,
                'nombre': atributo.nombre,
                'valor': valores_dict.get(atributo.id, '')
            }
            for atributo in atributos_definidos
        ]

        variantes.append({
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

    return JsonResponse({
        'existe': True,
        'variantes': variantes,
    })
    
    


    
import logging
_logger = logging.getLogger(__name__)


# ============================================================
# AJAX: Cambiar el código de barras de un producto (solo dueño)
# ============================================================
@login_required
def cambiar_codigo_barras_ajax(request, producto_id):
    """
    Endpoint inline para editar el código de barras desde detalle_producto.

    Body JSON: {codigo: "...", confirmar_variante: bool}

    Reglas (idénticas al diseño hablado):
    - Si el código nuevo no pasa validar_codigo_real → 400 tipo=validacion.
    - Si el código nuevo no existe en otros productos → guarda OK.
    - Si pertenece a productos de OTRA categoría → bloquea siempre
      (probable error humano).
    - Si pertenece a productos de la MISMA categoría → exige confirmar_variante=true.

    Solo el dueño puede ejecutar este endpoint.
    """
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método no permitido."}, status=405)

    empleado = getattr(request.user, "empleado", None)
    if not empleado or empleado.rol != "dueño":
        return JsonResponse(
            {"ok": False, "error": "Solo el dueño puede cambiar el código de barras."},
            status=403,
        )

    producto = get_object_or_404(Producto, id=producto_id)

    try:
        body = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "JSON inválido."}, status=400)

    nuevo_codigo = (body.get("codigo") or "").strip()
    confirmar_variante = bool(body.get("confirmar_variante"))

    if not nuevo_codigo:
        return JsonResponse(
            {"ok": False, "tipo": "validacion", "error": "El código no puede estar vacío."},
            status=400,
        )

    if nuevo_codigo == (producto.codigo_barras or ""):
        return JsonResponse(
            {"ok": False, "tipo": "validacion", "error": "El código es igual al actual."},
            status=400,
        )

    try:
        tipo_calc = CodigoService.validar_codigo_real(nuevo_codigo)
    except ValueError as e:
        return JsonResponse(
            {"ok": False, "tipo": "validacion", "error": str(e)},
            status=400,
        )

    otros = list(
        Producto.objects
        .filter(codigo_barras=nuevo_codigo, activo=True)
        .exclude(pk=producto.pk)
        .select_related("categoria")
    )

    if otros:
        otros_distinto = [o for o in otros if o.categoria_id != producto.categoria_id]

        if otros_distinto:
            p = otros_distinto[0]
            cat_nombre = p.categoria.nombre if p.categoria else "Sin categoría"
            return JsonResponse(
                {
                    "ok": False,
                    "tipo": "otra_categoria",
                    "error": (
                        f"El código '{nuevo_codigo}' pertenece a "
                        f"'{p.nombre}' (ID #{p.id}) de la categoría '{cat_nombre}'. "
                        f"Intenta registrar otro código. "
                        f"Recuerda que vas a tener que reetiquetar los productos."
                    ),
                    "variantes": [
                        {
                            "producto_id": o.id,
                            "nombre": o.nombre,
                            "subcategoria_nombre": o.categoria.nombre if o.categoria else None,
                        }
                        for o in otros
                    ],
                },
                status=409,
            )

        if not confirmar_variante:
            return JsonResponse(
                {
                    "ok": False,
                    "tipo": "necesita_confirmacion",
                    "error": (
                        f"El código '{nuevo_codigo}' ya pertenece a otros productos "
                        f"de la misma categoría."
                    ),
                    "variantes": [
                        {
                            "producto_id": o.id,
                            "nombre": o.nombre,
                            "subcategoria_nombre": o.categoria.nombre if o.categoria else None,
                        }
                        for o in otros
                    ],
                },
                status=409,
            )

    producto.codigo_barras = nuevo_codigo
    producto.tipo_codigo = tipo_calc
    producto.save(update_fields=["codigo_barras", "tipo_codigo"])

    return JsonResponse({
        "ok": True,
        "codigo": producto.codigo_barras,
        "tipo_codigo": producto.tipo_codigo,
    })


#VISTA API PARA VER LOS CODIGOS EN EL FRONT DE MANERA FLUIDA
@login_required
def codigo_base64(request, producto_id):
    producto = get_object_or_404(Producto, id=producto_id)

    try:
        imagen = BarcodeRenderService.generar(
            codigo=producto.codigo_barras,
            tipo=producto.tipo_codigo,
            tamaño=producto.tamano_etiqueta,
        )

        return JsonResponse({'imagen': imagen})

    except Exception as e:
        _logger.error("Error generando código de barras para producto %s: %s", producto_id, e, exc_info=True)
        return JsonResponse({'error': 'No se pudo generar el código de barras.'}, status=500)


@login_required
def descargar_etiqueta_pdf(request, producto_id):
    """Genera un PDF con las dimensiones exactas de la etiqueta del producto."""
    import base64 as _b64
    import io as _io
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import mm
    from reportlab.lib.utils import ImageReader

    # Dimensiones físicas por tamaño (ancho x alto en mm)
    TAMAÑOS = {
        "chica":   (30, 15),
        "mediana": (100, 30),
        "grande":  (135, 32),
    }

    producto = get_object_or_404(Producto, id=producto_id)

    if not producto.codigo_barras:
        return HttpResponse("Este producto no tiene código de barras.", status=404)

    tamaño = producto.tamano_etiqueta or "mediana"
    tipo   = producto.tipo_codigo    or "code128"
    ancho_mm, alto_mm = TAMAÑOS.get(tamaño, (100, 30))

    try:
        img_b64 = BarcodeRenderService.generar(
            codigo=producto.codigo_barras,
            tipo=tipo,
            tamaño=tamaño,
        )
    except Exception as e:
        _logger.error("Error generando barcode PDF para producto %s: %s", producto_id, e, exc_info=True)
        return HttpResponse("Error generando el código de barras.", status=500)

    img_bytes = _b64.b64decode(img_b64)
    page_w = ancho_mm * mm
    page_h = alto_mm * mm

    buf = _io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.drawImage(ImageReader(_io.BytesIO(img_bytes)), 0, 0, width=page_w, height=page_h, preserveAspectRatio=True, anchor="c")
    c.save()
    buf.seek(0)

    response = HttpResponse(buf.read(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="etiqueta_{producto.codigo_barras}.pdf"'
    )
    return response


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
    



