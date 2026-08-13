"""
Construcción de URLs de Cloudinary con transformaciones (resize, calidad auto,
formato auto WebP/AVIF). Cloudinary genera la versión transformada al vuelo y
la guarda como "recurso derivado" en su CDN.

CATÁLOGO CERRADO DE TAMAÑOS
---------------------------
Cada ancho distinto que la app pida se convierte en un derivado que Cloudinary
guarda PARA SIEMPRE. Con un ancho suelto por vista, los derivados crecen sin
control (llegaron a ser 12,292 sobre 4,586 fotos reales).

Por eso aquí NO hay parámetro de ancho: solo tres tags con nombre. Si una vista
nueva necesita una foto, tiene que elegir uno de estos tres tamaños, no inventar
el suyo. Así el total de derivados por producto queda acotado y es predecible.

Los tamaños salen de medir las cajas CSS reales y multiplicarlas por 2 (para que
se vean nítidas en pantallas retina):

    MINI     160 px  → cajas de 48–72 px  (card del POS, thumbs de selectores)
    CARD     320 px  → cajas de 96–256 px (grids, kanban, ubicaciones, detalle)

Si alguna vista necesita algo más grande, es mejor subir el tamaño de una de
estas constantes que agregar otra.

CUIDADO CON EL COSTO DE CADA ANCHO NUEVO
----------------------------------------
Cada derivado que Cloudinary crea cuenta como una TRANSFORMACIÓN, y con f_auto
son DOS por ancho (guarda una f_jxl y una f_webp,fl_awebp). Con ~4,000
productos, un ancho nuevo son ~8,000 transformaciones = 8 credits del plan.

Corolario aprendido a la mala: NO purgar derivados para liberar storage. Cada
uno regenerado vuelve a cobrar transformación, y sale más caro el remedio
(~8 credits) que la enfermedad (~4 credits de storage).

NUNCA SIRVAS `producto.foto_url.url` DIRECTO
--------------------------------------------
Comprobado en producción: una URL SIN transformación hace que Cloudinary
guarde una derivada del tamaño completo del original — duplica el storage de
esa foto (2.5 MB extra cada una). Es lo que llenó 4 GB de la cuenta antes de
que existiera este catálogo.

Cualquier transformación evita ese comportamiento. Usa siempre uno de los
helpers de este módulo, aunque solo necesites "la foto tal cual".

Uso:
    {% load cloudinary_helpers %}
    <img src="{% foto_mini producto.foto_url %}">
    <img src="{% foto_card producto.foto_url %}">
    <img src="{% foto_detalle producto.foto_url %}">
"""

from django import template

register = template.Library()

# Anchos del catálogo. Cambiarlos aquí los cambia en toda la app; agregar uno
# nuevo significa un derivado más por producto en Cloudinary, así que piénsalo.
ANCHO_MINI = 160
ANCHO_CARD = 320

# Deliberadamente IGUAL a ANCHO_CARD, no es un descuido.
#
# Estuvo en 640 y resultó carísimo: ese derivado solo se genera cuando alguien
# abre la ficha de un producto, así que con ~4,000 productos había ~8,000
# transformaciones (2 formatos por f_auto) esperando a dispararse una por una
# conforme la gente navegara. Al reusar 320 —que ya está generado para
# prácticamente todo el catálogo— esas transformaciones nunca se cobran.
#
# La foto del detalle se muestra en una caja de 256 px de alto (max-h-64), así
# que 320 alcanza. Se pierde algo de nitidez en pantallas retina; es el precio
# de no reventar la cuota.
#
# Para subirlo de nuevo basta cambiar este número, pero cuesta una
# transformación por producto que abra esa vista. Hacerlo solo con holgura
# de credits.
ANCHO_DETALLE = ANCHO_CARD

# Ancho para las fotos incrustadas en PDFs. Se dibujan en 18 mm de lado, así
# que 320 px sobra incluso imprimiendo a 300 dpi.
ANCHO_PDF = 320

# Ancho para heredar la foto al crear una variante: el navegador descarga esta
# versión y la vuelve a SUBIR. Coincide con el tope de ImagenService para que
# la variante nueva nazca con el mismo original que tendría si la subieras.
ANCHO_MASTER = 1600


def _aplicar_transformaciones(url, transformaciones):
    """Inserta una cadena de transformaciones después de '/upload/' en la URL.
    Si la URL no es de Cloudinary (storage local en dev), la devuelve sin tocar."""
    if not url or "/image/upload/" not in url:
        return url
    return url.replace("/image/upload/", f"/image/upload/{transformaciones}/")


def _url(field):
    """URL cruda del ImageField, o "" si no hay foto."""
    if not field:
        return ""
    try:
        return field.url
    except Exception:
        return ""


def _transformada(field, width):
    """
    URL para mostrar en un <img>.

    - c_limit: respeta proporción y nunca agranda.
    - q_auto:  calidad óptima automática.
    - f_auto:  formato moderno (WebP/AVIF) si el browser lo soporta.

    Nota: f_auto hace que Cloudinary guarde un derivado por formato entregado.
    Se mantiene a propósito — un derivado extra se guarda UNA vez (decenas de
    KB), mientras que el ahorro de WebP/AVIF se cobra en CADA vista, y las
    vistas son ~150,000 al mes.
    """
    url = _url(field)
    if not url:
        return ""
    return _aplicar_transformaciones(url, f"w_{width},c_limit,q_auto,f_auto")


@register.simple_tag
def foto_mini(field):
    """Thumb chico: card del POS, selector de variantes, búsqueda de órdenes."""
    return _transformada(field, ANCHO_MINI)


@register.simple_tag
def foto_card(field):
    """Card de catálogo: grids, kanban, inventario_ubicacion, inactivos."""
    return _transformada(field, ANCHO_CARD)


@register.simple_tag
def foto_detalle(field):
    """
    Vista de detalle del producto.

    Hoy produce la MISMA URL que foto_card (ver ANCHO_DETALLE). Se mantiene
    como tag aparte para que el día que haya holgura de credits se pueda subir
    solo este tamaño sin tocar las demás vistas.
    """
    return _transformada(field, ANCHO_DETALLE)


def foto_pdf(field):
    """
    URL para incrustar en los PDFs que se generan en el servidor.

    No es un template tag: la consume ReportLab desde las vistas.

    Fuerza f_jpg en lugar de f_auto porque ReportLab no siempre sabe decodificar
    el WebP/AVIF que f_auto entregaría.

    Devuelve "" si no hay foto.
    """
    url = _url(field)
    if not url:
        return ""
    return _aplicar_transformaciones(url, f"w_{ANCHO_PDF},c_limit,q_auto,f_jpg")


def foto_master(field):
    """
    Versión grande para el flujo de "heredar foto" al crear una variante: el
    navegador descarga esta URL y vuelve a SUBIR el blob como foto del
    producto nuevo.

    Fuerza f_jpg para que Pillow siempre sepa abrirlo al re-subir.

    OJO — NUNCA sirvas aquí `field.url` sin transformar. Se probó en
    producción: pedir una URL sin transformación hace que Cloudinary guarde
    una derivada del TAMAÑO COMPLETO del original (2.5 MB por producto), o
    sea que duplica el storage de esa foto. Cualquier transformación evita
    ese comportamiento; ésta pesa ~390 KB en vez de 2.5 MB.

    Devuelve "" si no hay foto.
    """
    url = _url(field)
    if not url:
        return ""
    return _aplicar_transformaciones(url, f"w_{ANCHO_MASTER},c_limit,q_auto,f_jpg")
