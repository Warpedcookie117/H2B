from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Inventario


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
