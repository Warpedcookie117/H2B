from PIL import Image
from barcode import EAN13, Code128
from barcode.writer import ImageWriter
import io
import base64
from pylibdmtx.pylibdmtx import encode
import hashlib




def generar_datamatrix_base64(codigo):
    encoded = encode(codigo.encode("utf-8"))
    img = Image.frombytes('RGB', (encoded.width, encoded.height), encoded.pixels)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


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


