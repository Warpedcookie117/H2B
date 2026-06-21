import json

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.serializers.json import DjangoJSONEncoder

from inventario.templatetags.cloudinary_helpers import foto_card
from .models import Inventario, Producto


def _broadcast(ubicacion_id, producto_id, cantidad_actual):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"inventario_{ubicacion_id}",
            {
                "type": "stock_update",
                "producto_id": producto_id,
                "ubicacion_id": ubicacion_id,
                "cantidad_actual": cantidad_actual,
            }
        )
    except Exception:
        # Redis no disponible en este entorno — broadcast silenciado.
        pass


@receiver(post_save, sender=Inventario)
def inventario_actualizado(sender, instance, **kwargs):
    _broadcast(instance.ubicacion_id, instance.producto_id, instance.cantidad_actual)


@receiver(post_delete, sender=Inventario)
def inventario_eliminado(sender, instance, **kwargs):
    # Registro eliminado → cantidad 0 para todos los que escuchen esa ubicación
    _broadcast(instance.ubicacion_id, instance.producto_id, 0)


def _broadcast_producto(producto):
    """Difunde los cambios de detalle del producto a cada ubicación donde existe
    (el POS escucha el grupo de su Piso)."""
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    ubicacion_ids = (
        Inventario.objects
        .filter(producto_id=producto.id)
        .values_list("ubicacion_id", flat=True)
        .distinct()
    )

    try:
        foto = foto_card(producto.foto_url)
    except Exception:
        foto = ""

    atributos_json = json.dumps(
        {va.atributo.nombre: va.valor for va in producto.valores_atributo.select_related("atributo").all()},
        cls=DjangoJSONEncoder,
    )

    payload = {
        "type": "producto_update",
        "producto_id": producto.id,
        "nombre": producto.nombre,
        "precio_menudeo": str(producto.precio_menudeo),
        "precio_mayoreo": str(producto.precio_mayoreo),
        "precio_docena": str(producto.precio_docena) if producto.precio_docena is not None else "",
        "codigo_barras": producto.codigo_barras or "",
        "foto_url": foto,
        "atributos_json": atributos_json,
        "categoria_id": producto.categoria_id,
        "categoria_padre_id": producto.categoria_padre_id,
        "activo": producto.activo,
    }

    for uid in ubicacion_ids:
        try:
            async_to_sync(channel_layer.group_send)(f"inventario_{uid}", payload)
        except Exception:
            # Redis no disponible en este entorno — broadcast silenciado.
            pass


@receiver(post_save, sender=Producto)
def producto_actualizado(sender, instance, created, **kwargs):
    # Solo nos interesan ediciones de productos ya existentes en algún inventario.
    if created:
        return
    _broadcast_producto(instance)
