from inventario.models import Atributo, ValorAtributo

class AtributoService:

    @staticmethod
    def guardar_valores(producto, data):
        """
        El Form ya validó todo.
        Aquí SOLO guardamos.
        """
        atributos = Atributo.objects.filter(categoria=producto.categoria)

        for atributo in atributos:
            key = f"atributo_{atributo.id}"
            valor = (data.get(key) or "").strip()

            ValorAtributo.objects.update_or_create(
                producto=producto,
                atributo=atributo,
                defaults={"valor": valor},
            )