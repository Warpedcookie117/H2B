import imagehash
from PIL import Image, ImageFile

ImageFile.LOAD_TRUNCATED_IMAGES = True

def generar_phash(file):
    if hasattr(file, 'seek'):
        file.seek(0)
    img = Image.open(file).convert("RGB")
    resultado = str(imagehash.phash(img))
    if hasattr(file, 'seek'):
        file.seek(0)
    return resultado
