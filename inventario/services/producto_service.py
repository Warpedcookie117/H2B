from django.db import transaction
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from inventario.services.atributo_service import AtributoService
from inventario.services.inventario_service import InventarioService


class ProductService:

    @staticmethod
    @transaction.atomic
    def crear_producto_desde_formulario(
        form,
        request,
        codigo_generado=None,
        tipo_codigo=None,
        tamano_etiqueta=None
    ):
        """
        Flujo unificado compatible con la vista:
        - Si viene codigo_generado → usarlo
        - Si no viene → usar el del form
        - tipo_codigo puede venir desde la vista o desde el form
        - tamano_etiqueta puede venir desde la vista o desde el form
        """

        cleaned = form.cleaned_data

        # Crear producto base
        producto = form.save(commit=False)
        producto.registrado_por = getattr(request.user, "empleado", None)

        # Categoría / subcategoría
        sub = cleaned.get("subcategoria")
        if sub:
            producto.categoria = sub
            producto.categoria_padre = sub.padre

        # ============================================================
        # TAMAÑO DE ETIQUETA (prioridad: vista → form → default)
        # ============================================================
        producto.tamano_etiqueta = (
            tamano_etiqueta or
            cleaned.get("tamano_etiqueta") or
            "mediana"
        )

        # ============================================================
        # ASIGNAR CÓDIGO Y TIPO (real o generado)
        # ============================================================
        if codigo_generado:
            producto.codigo_barras = codigo_generado
            producto.tipo_codigo = tipo_codigo or "code128"
        else:
            producto.codigo_barras = cleaned.get("codigo_barras")
            producto.tipo_codigo = cleaned.get("tipo_codigo")

        if not producto.codigo_barras:
            raise ValueError("Error crítico: no se asignó código de barras.")

        if not producto.tipo_codigo:
            raise ValueError("Error crítico: no se asignó tipo_codigo.")

        # Guardar producto (sin firma)
        try:
            producto.save()
        except IntegrityError:
            from inventario.models import Producto as Prod
            existente = Prod.objects.filter(codigo_barras=producto.codigo_barras).first()
            if existente:
                raise ValidationError(
                    f"Este código de barras ya está registrado. "
                    f"Busca el ID {existente.id} en el inventario global."
                )
            raise ValidationError("Este producto ya existe. Verifica el inventario global.")

        # Guardar M2M
        form.save_m2m()

        # Guardar atributos dinámicos
        AtributoService.guardar_valores(producto, request.POST)

        # Generar firma única
        firma = ProductService._generar_firma(producto)
        producto.firma_unica = firma

        try:
            producto.save(update_fields=["firma_unica"])
        except IntegrityError:
            from inventario.models import Producto as Prod
            existente = Prod.objects.filter(firma_unica=firma).first()
            if existente:
                raise ValidationError(
                    f"Este producto ya existe (firma única). "
                    f"Busca el ID {existente.id} en el inventario global."
                )
            raise ValidationError("Este producto ya existe (firma única). Verifica el inventario global.")

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

    # ============================================================
    # FIRMA ÚNICA (limpia)
    # ============================================================
    @staticmethod
    def _generar_firma(producto):
        partes = []

        valores = producto.valores_atributo.all()

        for valor in valores:
            nombre = valor.atributo.nombre.lower().strip()
            val = str(valor.valor).lower().strip()
            partes.append(f"{nombre}={val}")

        partes.sort()
        return "|".join(partes)