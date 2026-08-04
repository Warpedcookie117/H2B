"""
Compresión de fotos de producto ANTES de subirlas a Cloudinary.

Motivo: las fotos llegan crudas del celular (2–4 MB cada una). Con ~4,500
productos eso son ~12 GB de storage, que por sí solos revientan el plan
gratuito de Cloudinary (25 credits, donde 1 GB de storage = 1 credit).

El ancho más grande que la app llega a pedir es 1200 px (ver el default de
`foto_srcset` en templatetags/cloudinary_helpers.py), así que guardar el
original a 1600 px deja margen de sobra y no degrada ninguna vista actual.

No se genera thumbnail aquí a propósito: las versiones chicas las produce
Cloudinary al vuelo con w_/q_auto/f_auto. (El campo `foto_thumbnail` existió
en la migración 0016 y se eliminó en la 0018 justamente por redundante.)
"""

import io
import logging
import os

from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image, ImageOps

_logger = logging.getLogger(__name__)


class ImagenService:

    # Lado mayor máximo del original almacenado. 1600 > 1200 (el ancho más
    # grande que pide la app), así que sobra calidad para cualquier vista.
    MAX_LADO = 1600

    # Calidad JPEG. 85 es el punto donde la pérdida deja de ser perceptible
    # en fotos de producto y el archivo ya bajó ~90%.
    CALIDAD = 85

    # Por debajo de esto no vale la pena re-codificar: el ahorro es marginal
    # y un segundo encode solo suma pérdida.
    UMBRAL_BYTES = 300 * 1024

    @staticmethod
    def comprimir(archivo):
        """
        Recibe un UploadedFile y devuelve una versión comprimida en JPEG.

        Es fail-safe por diseño: ante CUALQUIER problema (formato raro, imagen
        corrupta, Pillow sin el codec) devuelve el archivo original intacto.
        Nunca debe impedir que se guarde un producto.

        Se salta la recompresión si la imagen ya es chica y cabe en MAX_LADO.
        """
        if not archivo:
            return archivo

        try:
            tamaño_original = getattr(archivo, "size", 0) or 0

            archivo.seek(0)
            imagen = Image.open(archivo)

            # Las fotos de celular traen la rotación en el EXIF en vez de en
            # los píxeles. Si re-codificamos sin aplicarla, el EXIF se pierde
            # y la foto queda acostada. Esto lo resuelve antes de tocar nada.
            imagen = ImageOps.exif_transpose(imagen)

            cabe = max(imagen.size) <= ImagenService.MAX_LADO
            if cabe and tamaño_original and tamaño_original <= ImagenService.UMBRAL_BYTES:
                archivo.seek(0)
                return archivo

            if not cabe:
                # thumbnail() respeta proporción y nunca agranda.
                imagen.thumbnail(
                    (ImagenService.MAX_LADO, ImagenService.MAX_LADO),
                    Image.LANCZOS,
                )

            # JPEG no soporta alfa ni paleta. Las transparencias se aplanan
            # sobre blanco, que es el fondo de las cards del catálogo.
            if imagen.mode in ("RGBA", "LA", "P"):
                imagen = imagen.convert("RGBA")
                fondo = Image.new("RGB", imagen.size, (255, 255, 255))
                fondo.paste(imagen, mask=imagen.split()[-1])
                imagen = fondo
            elif imagen.mode != "RGB":
                imagen = imagen.convert("RGB")

            buffer = io.BytesIO()
            imagen.save(
                buffer,
                format="JPEG",
                quality=ImagenService.CALIDAD,
                optimize=True,
                progressive=True,
            )
            tamaño_nuevo = buffer.tell()

            # Si comprimir no ayudó (pasa con imágenes ya optimizadas o muy
            # chicas), nos quedamos con el original.
            if tamaño_original and tamaño_nuevo >= tamaño_original:
                archivo.seek(0)
                return archivo

            buffer.seek(0)
            nombre = ImagenService._nombre_jpg(archivo.name)

            _logger.info(
                "Foto comprimida %s: %.1f KB → %.1f KB (%.0f%% menos)",
                nombre,
                tamaño_original / 1024 if tamaño_original else 0,
                tamaño_nuevo / 1024,
                (1 - tamaño_nuevo / tamaño_original) * 100 if tamaño_original else 0,
            )

            return InMemoryUploadedFile(
                buffer,
                field_name=getattr(archivo, "field_name", "foto_url"),
                name=nombre,
                content_type="image/jpeg",
                size=tamaño_nuevo,
                charset=None,
            )

        except Exception as e:
            _logger.warning(
                "No se pudo comprimir la foto %s (%s). Se sube el original.",
                getattr(archivo, "name", "?"), e,
            )
            try:
                archivo.seek(0)
            except Exception:
                pass
            return archivo

    @staticmethod
    def _nombre_jpg(nombre):
        """Cambia la extensión a .jpg conservando el nombre base."""
        if not nombre:
            return "foto.jpg"
        base = os.path.splitext(os.path.basename(nombre))[0]
        return f"{base}.jpg"
