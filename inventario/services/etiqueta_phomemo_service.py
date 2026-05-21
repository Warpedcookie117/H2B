from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from barcode.writer import ImageWriter


# ============================
# DIMENSIONES FÍSICAS (PHOMEMO M110)
# ============================
# Papel real: 30mm × 15mm. Resolución nativa de la M110: 203 DPI.
# Renderizamos al DOBLE EXACTO del DPI nativo de python-barcode (300 DPI →
# 11.811 px/mm). Resize ×2 NEAREST sale entero y no distorsiona las barras.
ANCHO_MM = 30
ALTO_MM = 15
PX_POR_MM = 11.811 * 2              # = 23.622 → factor 2 exacto
ANCHO_PX = round(ANCHO_MM * PX_POR_MM)   # 709
ALTO_PX = round(ALTO_MM * PX_POR_MM)     # 354

# Bandas verticales: cabecera (nombre+precios juntos) | barcode | código
# Sin márgenes verticales sobrantes: 100 + 190 + 64 = 354
H_CABECERA = 100
H_BARCODE = 190
H_CODIGO = 64


def _cargar_fuente(tamano_px, bold=True):
    """Carga la primera fuente bold disponible; cae a default de PIL."""
    candidatas_bold = [
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    candidatas_normal = [
        "arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for ruta in (candidatas_bold if bold else candidatas_normal):
        try:
            return ImageFont.truetype(ruta, tamano_px)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _fmt_precio(precio):
    """80.0 → '$80', 85.5 → '$85.5'."""
    if precio is None:
        return ""
    f = float(precio)
    if f == int(f):
        return f"${int(f)}"
    return f"${f:.1f}"


def _ajustar_nombre_precios(draw, nombre, precios_str, ancho_max, tamano_max=68, tamano_min=36, min_chars_nombre=5):
    """
    Devuelve (nombre_truncado, precios, fuente) para una sola línea con los
    precios GRANDES y al menos `min_chars_nombre` caracteres legibles del
    nombre. A tamaños >70px en bold las letras se aplastan visualmente
    (BL → 'BI', CL → 'CI'), por eso el techo está en 68.
    """
    sep = "  "
    nombre_strip = nombre.strip()
    minimo_chars = min(min_chars_nombre, len(nombre_strip))

    for size in range(tamano_max, tamano_min - 1, -2):
        fuente = _cargar_fuente(size, bold=True)
        ancho_precios = draw.textlength(precios_str, font=fuente)
        ancho_sep = draw.textlength(sep, font=fuente)

        if ancho_precios + 4 > ancho_max:
            continue

        ancho_para_nombre = ancho_max - ancho_precios - ancho_sep
        # Verificar que el mínimo de letras del nombre cabe en este tamaño
        ancho_min_nombre = draw.textlength(nombre_strip[:minimo_chars], font=fuente)
        if ancho_min_nombre > ancho_para_nombre:
            continue

        # Truncar nombre lo justo para que quepa
        n = nombre_strip
        while len(n) > minimo_chars and draw.textlength(n, font=fuente) > ancho_para_nombre:
            n = n[:-1]
        return n.strip(), precios_str, fuente

    # Fallback: tamaño mínimo, truncar nombre como sea
    fuente = _cargar_fuente(tamano_min, bold=True)
    return nombre_strip[:minimo_chars], precios_str, fuente


class EtiquetaPhomemoService:
    """
    Genera una etiqueta PNG lista para imprimir en Phomemo M110 vía Print Master.

    Layout 30x15mm (renderizado a 709x354 px):
      ┌──────────────────────────────────┐
      │  NOMBRE   $25  $20                │  ← una sola línea, precios GRANDES
      │  ║║║║║ ║║ ║║║ ║║║║║               │  ← barcode (mayor parte del alto)
      │  MOP024                           │
      └──────────────────────────────────┘
    """

    @staticmethod
    def generar(producto):
        codigo = producto.codigo_barras or ""

        # ============================
        # 1. Calcular module_width para que el barcode SIEMPRE escanee.
        # ============================
        modules = 11 * len(codigo) + 35
        quiet_mm = 2.0
        ancho_para_barras_mm = ANCHO_MM - 2 * quiet_mm
        ideal = ancho_para_barras_mm / modules
        # 0.25mm mínimo GS1, 0.55mm máximo (más grueso desperdicia espacio).
        module_width_mm = min(0.55, max(0.25, ideal))

        # ============================
        # 2. Generar barcode puro (sin texto debajo: lo dibujamos nosotros).
        # ============================
        barcode_buffer = BytesIO()
        Code128(codigo, writer=ImageWriter()).write(
            barcode_buffer,
            {
                "module_width": module_width_mm,
                "module_height": 18,
                "write_text": False,
                "quiet_zone": quiet_mm,
            },
        )
        barcode_buffer.seek(0)
        barcode_img = Image.open(barcode_buffer).convert("RGB")

        # ============================
        # 3. Lienzo blanco
        # ============================
        etiqueta = Image.new("RGB", (ANCHO_PX, ALTO_PX), "white")
        draw = ImageDraw.Draw(etiqueta)
        ancho_util = ANCHO_PX - 12   # 6px margen visual a cada lado

        # ============================
        # 4. Cabecera: nombre + precios en UNA línea, precios al máximo
        # ============================
        nombre = (producto.nombre or "").strip().upper()
        precios_str = f"{_fmt_precio(producto.precio_menudeo)}  {_fmt_precio(producto.precio_mayoreo)}"
        nombre_t, precios_t, font_cab = _ajustar_nombre_precios(
            draw, nombre, precios_str, ancho_util,
            tamano_max=68, tamano_min=38, min_chars_nombre=5,
        )

        # Texto compuesto: si el nombre quedó vacío, solo precios centrados
        if nombre_t:
            texto = f"{nombre_t}  {precios_t}"
        else:
            texto = precios_t

        bbox = draw.textbbox((0, 0), texto, font=font_cab)
        x = (ANCHO_PX - (bbox[2] - bbox[0])) // 2
        y = (H_CABECERA - (bbox[3] - bbox[1])) // 2 - 2
        draw.text((x, y), texto, fill="black", font=font_cab)

        # ============================
        # 5. Barcode escalado ×2 EXACTO con NEAREST (no distorsiona barras).
        # ============================
        bc_w, bc_h = barcode_img.size
        new_w = bc_w * 2
        new_h = bc_h * 2

        # Si excede altura disponible, escalar altura con factor entero.
        max_h = H_BARCODE - 8
        if new_h > max_h:
            factor_h = max(1, max_h // bc_h)
            new_h = bc_h * factor_h
        barcode_img = barcode_img.resize((new_w, new_h), Image.NEAREST)

        # Si el barcode es más ancho que el lienzo (código demasiado largo),
        # comprimir horizontalmente — scanner puede fallar.
        if new_w > ANCHO_PX:
            factor = ANCHO_PX / new_w
            new_w = ANCHO_PX
            new_h = max(1, int(new_h * factor))
            barcode_img = barcode_img.resize((new_w, new_h), Image.NEAREST)

        x = (ANCHO_PX - new_w) // 2
        y = H_CABECERA + (H_BARCODE - new_h) // 2
        etiqueta.paste(barcode_img, (x, y))

        # ============================
        # 6. Código en texto debajo del barcode
        # ============================
        codigo_texto = codigo
        font_codigo = _cargar_fuente(46, bold=True)
        # Auto-shrink si no cabe
        while draw.textlength(codigo_texto, font=font_codigo) > ancho_util and font_codigo.size > 24:
            font_codigo = _cargar_fuente(font_codigo.size - 2, bold=True)
        bbox = draw.textbbox((0, 0), codigo_texto, font=font_codigo)
        x = (ANCHO_PX - (bbox[2] - bbox[0])) // 2
        y = H_CABECERA + H_BARCODE + (H_CODIGO - (bbox[3] - bbox[1])) // 2 - 4
        draw.text((x, y), codigo_texto, fill="black", font=font_codigo)

        # ============================
        # 7. PNG final
        # ============================
        out = BytesIO()
        etiqueta.save(out, format="PNG", dpi=(203, 203))
        return out.getvalue()
