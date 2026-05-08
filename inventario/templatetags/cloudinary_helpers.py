"""
Templatetags para construir URLs de Cloudinary con transformaciones
(resize, calidad auto, formato auto WebP/AVIF) sin necesidad de subir
versiones extra del archivo. Cloudinary genera la versión transformada
al vuelo y la cachea en su CDN.

Uso:
    {% load cloudinary_helpers %}
    <img src="{% foto_card producto.foto_url %}">
    <img src="{% foto_card producto.foto_url 400 %}">
    <img srcset="{% foto_srcset producto.foto_url %}"
         sizes="(max-width: 600px) 50vw, 300px"
         src="{% foto_card producto.foto_url %}">
"""

from django import template

register = template.Library()


def _aplicar_transformaciones(url, transformaciones):
    """Inserta una cadena de transformaciones después de '/upload/' en la URL.
    Si la URL no es de Cloudinary (storage local en dev), la devuelve sin tocar."""
    if not url or "/image/upload/" not in url:
        return url
    return url.replace("/image/upload/", f"/image/upload/{transformaciones}/")


@register.simple_tag
def foto_card(field, width=600):
    """
    URL transformada para cards del catálogo.
    - width: ancho máximo en px (default 600).
    - c_limit: respeta proporción y nunca agranda.
    - q_auto: calidad óptima automática.
    - f_auto: formato moderno (WebP/AVIF) si el browser lo soporta.

    Devuelve "" si no hay foto.
    """
    if not field:
        return ""
    try:
        url = field.url
    except Exception:
        return ""
    transformaciones = f"w_{width},c_limit,q_auto,f_auto"
    return _aplicar_transformaciones(url, transformaciones)


@register.simple_tag
def foto_srcset(field, *widths):
    """
    Atributo srcset con múltiples anchuras para imágenes responsive.
    Si no se pasan anchuras, usa 400, 600 y 1200.

    Devuelve "" si no hay foto.
    """
    if not field:
        return ""
    try:
        url = field.url
    except Exception:
        return ""
    if not widths:
        widths = (400, 600, 1200)
    partes = []
    for w in widths:
        transformaciones = f"w_{w},c_limit,q_auto,f_auto"
        partes.append(f"{_aplicar_transformaciones(url, transformaciones)} {w}w")
    return ",".join(partes)
