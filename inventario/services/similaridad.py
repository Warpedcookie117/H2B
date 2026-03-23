import numpy as np
from inventario.models import Producto

def similitud_coseno(v1, v2):
    v1 = np.array(v1)
    v2 = np.array(v2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

UMBRAL = 0.80  # recomendado para ViT-L/14

def buscar_producto_similar(embedding_nuevo):
    candidatos = []
    for prod in Producto.objects.exclude(embedding=None):
        sim = similitud_coseno(embedding_nuevo, prod.embedding)
        if sim > UMBRAL:
            candidatos.append((prod, sim))
    return sorted(candidatos, key=lambda x: x[1], reverse=True)