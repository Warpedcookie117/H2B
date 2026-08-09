import json
import logging

from django.db.models.signals import pre_save, post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.core.serializers.json import DjangoJSONEncoder

from inventario.templatetags.cloudinary_helpers import foto_mini
from .models import Inventario, Producto

_logger = logging.getLogger(__name__)


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
        # Mismo tamaño que _producto_card.html: esta URL reemplaza la de esa
        # card en el POS, y pedir otro ancho generaría un derivado duplicado.
        foto = foto_mini(producto.foto_url)
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


# ============================================================================
# BORRADO DE LA FOTO REEMPLAZADA
#
# Django NO borra el archivo anterior cuando se reasigna un ImageField: sube
# el nuevo y deja el viejo en Cloudinary para siempre. Cada cambio de foto
# dejaba así un huérfano que nadie referencia pero sigue ocupando storage
# (llegaron a ser cientos).
#
# Se hace en dos tiempos a propósito:
#   pre_save  → guarda una referencia a la foto vieja (todavía se puede leer
#               de la BD, porque `instance` ya trae la nueva en memoria).
#   post_save → la borra, pero SOLO si el guardado sí se completó. Si se
#               borrara en pre_save y el INSERT/UPDATE fallara después, se
#               habría perdido una foto sin haber guardado la nueva.
# ============================================================================

@receiver(pre_save, sender=Producto)
def recordar_foto_anterior(sender, instance, update_fields=None, **kwargs):
    instance._foto_anterior = None

    # Guardados dirigidos que ni tocan la foto (p. ej. save(update_fields=["costo"]))
    # se saltan la consulta extra.
    if update_fields is not None and "foto_url" not in update_fields:
        return

    if not instance.pk:
        return  # producto nuevo: no hay foto previa que borrar

    try:
        anterior = Producto.objects.only("foto_url").get(pk=instance.pk).foto_url
    except Producto.DoesNotExist:
        return

    nueva = getattr(instance.foto_url, "name", None)
    if anterior and anterior.name and anterior.name != nueva:
        instance._foto_anterior = anterior


@receiver(post_save, sender=Producto)
def borrar_foto_anterior(sender, instance, **kwargs):
    anterior = getattr(instance, "_foto_anterior", None)
    if not anterior:
        return
    instance._foto_anterior = None

    try:
        anterior.storage.delete(anterior.name)
        _logger.info("Foto reemplazada borrada de storage: %s", anterior.name)
    except Exception as e:
        # Que no se pueda borrar la vieja jamás debe impedir guardar el producto.
        # A lo mucho queda un huérfano, que el comando limpiar_fotos_huerfanas
        # recoge después.
        _logger.warning(
            "No se pudo borrar la foto anterior %s: %s", anterior.name, e
        )
