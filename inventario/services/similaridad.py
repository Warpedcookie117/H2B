import imagehash

UMBRAL_HAMMING = 8  # bits diferentes permitidos (de 64 total)

def buscar_producto_similar_phash(phash_nuevo):
    from inventario.models import Producto
    hash_nuevo = imagehash.hex_to_hash(phash_nuevo)
    candidatos = []
    for prod in Producto.objects.exclude(phash=None):
        hash_prod = imagehash.hex_to_hash(prod.phash)
        distancia = hash_nuevo - hash_prod
        if distancia <= UMBRAL_HAMMING:
            candidatos.append((prod, distancia))
    return sorted(candidatos, key=lambda x: x[1])
