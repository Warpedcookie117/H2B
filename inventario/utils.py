from PIL import Image
from barcode import EAN13, Code128
from barcode.writer import ImageWriter
import io
import base64
import segno
import hashlib








def color_from_name(name):
    hex_color = hashlib.md5(name.encode()).hexdigest()[:6]
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)

    def _lum(rv, gv, bv):
        def _lin(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        return 0.2126 * _lin(rv) + 0.7152 * _lin(gv) + 0.0722 * _lin(bv)

    # WCAG AA contra blanco: contraste >= 4.5 → luminancia <= 0.18
    while _lum(r, g, b) > 0.18 and max(r, g, b) > 0:
        r = int(r * 0.78)
        g = int(g * 0.78)
        b = int(b * 0.78)

    return f"#{r:02x}{g:02x}{b:02x}"


