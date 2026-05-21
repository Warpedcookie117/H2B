from io import BytesIO

from PIL import Image, ImageDraw, ImageFont
from barcode import Code128
from barcode.writer import ImageWriter


# ============================
# DIMENSIONES FÍSICAS (PHOMEMO M110)
# ============================
# Papel real: 30mm × 15mm. Resolución nativa de la M110: 203 DPI.
# Para que las barras del Code 128 sobrevivan al downscale que hace Print Master,
# fijamos el lienzo al DOBLE EXACTO del DPI nativo de python-barcode (300 DPI
# → 11.811 px/mm). Así el resize ×2 que aplicamos al barcode es entero y NEAREST
# duplica píxeles sin distorsionar el grosor relativo de las barras.
ANCHO_MM = 30
ALTO_MM = 15
PX_POR_MM = 11.811 * 2              # = 23.622 → factor 2 exacto vs python-barcode
ANCHO_PX = round(ANCHO_MM * PX_POR_MM)   # 709
ALTO_PX = round(ALTO_MM * PX_POR_MM)     # 354

# Márgenes y bandas (en px del lienzo escalado)
MARGEN_LATERAL = 14   # margen visual del texto (NO aplica al barcode)

# Bandas verticales: titulo, precios, barcode, codigo numerico
# Total ≈ 354 px (= ALTO_PX). Damos más espacio a precios y barcode.
H_TITULO = 50
H_PRECIOS = 65
H_BARCODE = 180
H_CODIGO = 60

# Largo máximo de código que escanea con confianza en 30×15mm con Code 128.
# Por arriba de esto las barras quedan más finas que 0.25mm (mínimo GS1) y
# el lector falla. Calculado: (ancho útil 26mm) / (0.30mm mín × 11 mod/char + 35)
LARGO_SEGURO_CODE128 = 10


def _cargar_fuente(tamano_px, bold=True):
    """Carga la primera fuente disponible del sistema; cae a default de PIL."""
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


def _ajustar_a_ancho(draw, texto, fuente_base_size, ancho_max, bold=True, minimo=18):
    """
    Devuelve (texto, fuente) con tamaño reducido si es necesario para caber.
    Si aun así no cabe en el mínimo, recorta con '…'.
    """
    size = fuente_base_size
    while size >= minimo:
        fuente = _cargar_fuente(size, bold=bold)
        if draw.textlength(texto, font=fuente) <= ancho_max:
            return texto, fuente
        size -= 2

    fuente = _cargar_fuente(minimo, bold=bold)
    while texto and draw.textlength(texto + "…", font=fuente) > ancho_max:
        texto = texto[:-1]
    return ((texto + "…") if texto else ""), fuente


class EtiquetaPhomemoService:
    """
    Genera una etiqueta PNG lista para imprimir en Phomemo M110 vía Print Master.

    Layout 30x15mm (renderizado a 720x360 px):
      ┌──────────────────────────────┐
      │  NOMBRE DEL PRODUCTO          │
      │  $80 men   $85 may            │
      │  ║║║║║ ║║ ║║║ ║║║║║           │
      │  GODETES01                    │
      └──────────────────────────────┘

    Pensado para productos con code128 (generado por sistema o manual).
    Los EAN-13/UPC-A del fabricante usan el render plano de BarcodeRenderService.
    """

    @staticmethod
    def generar(producto):
        codigo = producto.codigo_barras or ""

        # ============================
        # 1. Calcular module_width físico que SÍ va a escanear en papel.
        # ============================
        # Code 128 usa ~11 modules por carácter + 35 (start/stop/checksum).
        # El barcode usa TODO el ancho de la etiqueta (sin margen visual al
        # lado). El quiet_zone propio del bitmap actúa como margen blanco
        # — eso es lo que el scanner necesita ver.
        modules = 11 * len(codigo) + 35
        quiet_mm = 2.0
        ancho_para_barras_mm = ANCHO_MM - 2 * quiet_mm  # 26mm

        ideal = ancho_para_barras_mm / modules
        # Cap inferior: 0.25mm es el mínimo absoluto GS1 (debajo de eso el
        # scanner no puede separar barras adyacentes). Cap superior: 0.55mm
        # (barras demasiado gruesas ocupan más que la etiqueta).
        module_width_mm = min(0.55, max(0.25, ideal))

        # ============================
        # 2. Generar barcode puro (sin texto debajo: lo dibujamos nosotros).
        # ============================
        barcode_buffer = BytesIO()
        Code128(codigo, writer=ImageWriter()).write(
            barcode_buffer,
            {
                "module_width": module_width_mm,
                "module_height": 15,
                "write_text": False,
                "quiet_zone": quiet_mm,
            },
        )
        barcode_buffer.seek(0)
        barcode_img = Image.open(barcode_buffer).convert("RGB")

        # ============================
        # 2. Lienzo blanco
        # ============================
        etiqueta = Image.new("RGB", (ANCHO_PX, ALTO_PX), "white")
        draw = ImageDraw.Draw(etiqueta)
        ancho_util = ANCHO_PX - 2 * MARGEN_LATERAL

        # ============================
        # 3. Nombre del producto (auto-shrink si es largo)
        # ============================
        nombre = (producto.nombre or "").strip().upper()
        nombre, font_titulo = _ajustar_a_ancho(
            draw, nombre, fuente_base_size=44, ancho_max=ancho_util, bold=True, minimo=22
        )
        bbox = draw.textbbox((0, 0), nombre, font=font_titulo)
        x = (ANCHO_PX - (bbox[2] - bbox[0])) // 2
        y = (H_TITULO - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), nombre, fill="black", font=font_titulo)

        # ============================
        # 4. Precios (más grandes — segunda prioridad después del barcode)
        # ============================
        precios = f"{_fmt_precio(producto.precio_menudeo)} men   {_fmt_precio(producto.precio_mayoreo)} may"
        precios, font_precios = _ajustar_a_ancho(
            draw, precios, fuente_base_size=46, ancho_max=ancho_util, bold=True, minimo=24
        )
        bbox = draw.textbbox((0, 0), precios, font=font_precios)
        x = (ANCHO_PX - (bbox[2] - bbox[0])) // 2
        y = H_TITULO + (H_PRECIOS - (bbox[3] - bbox[1])) // 2
        draw.text((x, y), precios, fill="black", font=font_precios)

        # ============================
        # 5. Barcode escalado por factor 2 EXACTO (NEAREST).
        #    python-barcode genera a 300 DPI (11.81 px/mm). Mi lienzo a 23.62
        #    px/mm → factor 2 perfecto. NEAREST con factor entero duplica
        #    píxeles sin distorsionar el ancho relativo de cada barra.
        #    Si el barcode resultante NO cabe horizontalmente, significa que
        #    el código es demasiado largo para esta etiqueta (módulo cayó al
        #    mínimo de 0.30mm). En ese caso reducimos altura solamente y
        #    aceptamos que toque ambos bordes; el lector aún puede leerlo si
        #    el papel queda perfectamente alineado.
        # ============================
        bc_w, bc_h = barcode_img.size
        new_w = bc_w * 2
        new_h = bc_h * 2

        # Si excede altura disponible, escalar altura SOLA con NEAREST entero
        max_h = H_BARCODE - 10
        if new_h > max_h:
            # Buscamos factor entero ≤2 que cumpla
            factor_h = max(1, max_h // bc_h)
            new_h = bc_h * factor_h
            # Mantenemos factor 2 horizontal para no distorsionar las barras
        barcode_img = barcode_img.resize((new_w, new_h), Image.NEAREST)

        # Si el barcode es más ancho que el lienzo (código demasiado largo),
        # forzamos un downscale horizontal — el scanner puede fallar y hay que
        # avisar al usuario que use código más corto o etiqueta más grande.
        if new_w > ancho_util:
            factor = ancho_util / new_w
            new_w = ancho_util
            new_h = max(1, int(new_h * factor))
            barcode_img = barcode_img.resize((new_w, new_h), Image.NEAREST)

        x = (ANCHO_PX - new_w) // 2
        y = H_TITULO + H_PRECIOS + (H_BARCODE - new_h) // 2
        etiqueta.paste(barcode_img, (x, y))

        # ============================
        # 6. Código en texto debajo del barcode
        # ============================
        codigo_texto = producto.codigo_barras or ""
        codigo_texto, font_codigo = _ajustar_a_ancho(
            draw, codigo_texto, fuente_base_size=38, ancho_max=ancho_util, bold=True, minimo=20
        )
        bbox = draw.textbbox((0, 0), codigo_texto, font=font_codigo)
        x = (ANCHO_PX - (bbox[2] - bbox[0])) // 2
        y = H_TITULO + H_PRECIOS + H_BARCODE + (H_CODIGO - (bbox[3] - bbox[1])) // 2 - 5
        draw.text((x, y), codigo_texto, fill="black", font=font_codigo)

        # ============================
        # 7. PNG final
        # ============================
        out = BytesIO()
        etiqueta.save(out, format="PNG", dpi=(203, 203))
        return out.getvalue()
