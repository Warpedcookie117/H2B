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
    CARD     320 px  → cajas de 96–144 px (grids, kanban, inventario_ubicacion)
    DETALLE  640 px  → caja de 256 px     (detalle_producto)

Si alguna vista necesita algo más grande, es mejor subir el tamaño de una de
estas tres constantes que agregar una cuarta.

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
ANCHO_DETALLE = 640

# Ancho para las fotos incrustadas en PDFs. Se dibujan en 18 mm de lado, así
# que 320 px sobra incluso imprimiendo a 300 dpi.
ANCHO_PDF = 320


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
    """Vista de detalle del producto."""
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


def foto_original(field):
    """
    URL del original, sin transformar.

    Solo para el flujo de "heredar foto" al crear una variante: el navegador
    descarga esta URL y vuelve a SUBIR el blob como foto del producto nuevo.

    Se usa el original a propósito, en vez de una versión transformada:
    - No crea ningún derivado nuevo en Cloudinary.
    - No degrada la foto heredada (si heredáramos una versión de 640 px, la
      variante nueva nacería con un original peor que el de su padre).
    - Es JPEG, así que no hay riesgo de que Pillow no sepa abrirlo al re-subir.

    El costo es una descarga más pesada, pero heredar foto es una operación
    puntual (no ocurre en cada vista), y con ImagenService los originales
    nuevos ya pesan ~300 KB en vez de 2.5 MB.

    Devuelve "" si no hay foto.
    """
    return _url(field)
