from PIL import Image
from barcode import EAN13, Code128
from barcode.writer import ImageWriter
import io
import base64
import segno
import hashlib




def generar_datamatrix_base64(data: str):
    qr = segno.helpers.make_datamatrix(data)
    buffer = io.BytesIO()
    qr.save(buffer, kind='png', scale=5)
    return base64.b64encode(buffer.getvalue()).decode()




def generar_base64(codigo, clase_barcode):
    """
    Genera una imagen PNG del código de barras y la devuelve en base64.
    """
    buffer = io.BytesIO()
    barcode = clase_barcode(codigo, writer=ImageWriter())
    barcode.write(buffer)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def color_from_name(name):
    hex_color = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"#{hex_color}"


