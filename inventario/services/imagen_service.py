"""
Servicio para generar thumbnails de fotos de producto.

La foto original (foto_url) NUNCA se modifica. Esto solo construye un
archivo derivado más pequeño que se guarda en foto_thumbnail.

Las cards del catálogo usan el thumbnail (rápido); el detalle del
producto sigue usando la foto_url original a calidad completa.
"""

import io
from PIL import Image, ImageOps
from django.core.files.base import ContentFile

# Tamaño máximo del lado mayor del thumbnail
MAX_DIM = 600        # px
JPEG_QUALITY = 85    # buena calidad visual, ~80-150 KB típico


def generar_thumbnail(file_field):
    """
    Recibe el FieldFile de foto_url (la original) y devuelve un
    ContentFile con la versión redimensionada lista para asignarse
    a foto_thumbnail.

    NUNCA cierra ni consume el file_field — Django todavía necesita
    leerlo después para guardar el archivo original en disco.

    Devuelve (content_file, nombre_archivo) o (None, None) si falla.
    """
    if not file_field:
        return None, None

    try:
        # Leer el contenido completo a bytes UNA sola vez y trabajar
        # sobre una copia en memoria. Así no movemos el cursor del
        # file_field ni lo cerramos — Django lo lee después intacto.
        try:
            file_field.seek(0)
        except Exception:
            pass
        contenido = file_field.read()
        try:
            file_field.seek(0)
        except Exception:
            pass

        img = Image.open(io.BytesIO(contenido))

        # Respetar la orientación EXIF (iPhone gira fotos vía metadata)
        img = ImageOps.exif_transpose(img)

        # Redimensionar manteniendo proporción
        img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)

        # JPEG no soporta alpha → fondo blanco si la original es PNG transparente
        if img.mode in ("RGBA", "LA"):
            fondo = Image.new("RGB", img.size, (255, 255, 255))
            fondo.paste(img, mask=img.split()[-1])
            img = fondo
        elif img.mode != "RGB":
            img = img.convert("RGB")

        out = io.BytesIO()
        img.save(out, format="JPEG", quality=JPEG_QUALITY,
                 optimize=True, progressive=True)
        out.seek(0)

        # Nombre: igual que la original pero con sufijo y .jpg
        nombre_base = file_field.name.rsplit("/", 1)[-1]
        nombre_sin_ext = nombre_base.rsplit(".", 1)[0]
        nombre_final = f"{nombre_sin_ext}_thumb.jpg"

        return ContentFile(out.read(), name=nombre_final), nombre_final
    except Exception:
        return None, None
