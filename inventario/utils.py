from PIL import Image
from barcode import EAN13, Code128
from barcode.writer import ImageWriter
import io
import base64
import segno
import hashlib








def color_from_name(name):
    hex_color = hashlib.md5(name.encode()).hexdigest()[:6]
    return f"#{hex_color}"


