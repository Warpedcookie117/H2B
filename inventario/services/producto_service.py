from django.db import transaction
from django.core.exceptions import ValidationError

from inventario.services.atributo_service import AtributoService
from inventario.services.codigo_service import CodigoService
from inventario.services.etiqueta_service import EtiquetaService
from inventario.services.inventario_service import InventarioService


class ProductService:

    @staticmethod
    def crear_producto_desde_formulario(form, request):
        """
        Decide si el flujo es:
        - NORMAL (producto con código)
        - ETIQUETA (producto sin código → seleccionar etiqueta)
        """
        codigo = form.cleaned_data.get("codigo_barras")

        if codigo:
            return ProductService._crear_producto_normal(form, request)

        return EtiquetaService.preparar_producto_sin_codigo(form, request)

    @staticmethod
    @transaction.atomic
    def _crear_producto_normal(form, request):
        """
        Crea un producto REAL (con código ya asignado),
        guarda atributos dinámicos y registra inventario inicial.
        """
        cleaned = form.cleaned_data

        producto = form.save(commit=False)
        producto.registrado_por = getattr(request.user, "empleado", None)

        sub = cleaned.get("subcategoria")
        if sub:
            producto.categoria = sub
            producto.categoria_padre = sub.padre

        # Validar y asignar código real
        codigo = cleaned.get("codigo_barras")
        tipo = CodigoService.validar_codigo_real(codigo)

        producto.codigo_barras = codigo
        producto.tipo_codigo = tipo

        if not producto.tipo_codigo:
            raise ValueError("tipo_codigo no fue asignado antes de crear el producto.")

        producto.save()
        form.save_m2m()

        # Guardar atributos dinámicos (ya validados por el Form)
        AtributoService.guardar_valores(producto, request.POST)

        # Inventario inicial
        cantidad = cleaned.get("cantidad_inicial")
        ubicacion = cleaned.get("ubicacion")
        empleado = getattr(request.user, "empleado", None)

        if cantidad and ubicacion:
            InventarioService.entrada(
                producto=producto,
                cantidad=cantidad,
                destino=ubicacion,
                empleado=empleado,
                motivo="nuevo"
            )

        return producto, ubicacion

    @staticmethod
    @transaction.atomic
    def crear_producto_sin_codigo(form, request):
        """
        Crea un producto cuyo código fue generado internamente
        y cuyo tipo_codigo viene de la selección de etiqueta.
        NO se valida como código de barras real.
        """
        cleaned = form.cleaned_data

        producto = form.save(commit=False)
        producto.registrado_por = getattr(request.user, "empleado", None)

        sub = cleaned.get("subcategoria")
        if sub:
            producto.categoria = sub
            producto.categoria_padre = sub.padre

        if not producto.codigo_barras:
            raise ValueError("Error crítico: código interno no asignado.")

        if not producto.tipo_codigo:
            raise ValueError("Error crítico: tipo_codigo no asignado.")

        producto.save()
        form.save_m2m()

        # Guardar atributos dinámicos (ya validados por el Form)
        AtributoService.guardar_valores(producto, form.data)

        cantidad = cleaned.get("cantidad_inicial")
        ubicacion = cleaned.get("ubicacion")
        empleado = getattr(request.user, "empleado", None)

        if cantidad and ubicacion:
            InventarioService.entrada(
                producto=producto,
                cantidad=cantidad,
                destino=ubicacion,
                empleado=empleado,
                motivo="nuevo"
            )

        return producto, ubicacion