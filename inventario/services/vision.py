import imagehash
from PIL import Image

def generar_phash(file):
    img = Image.open(file).convert("RGB")
    return str(imagehash.phash(img))
