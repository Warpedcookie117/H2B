from rapidfuzz import process, fuzz
from django.core.exceptions import ValidationError
from inventario.models import Atributo, ValorAtributo


class AtributoService:

    EQUIV_NA = {"n/a", "na", "no aplica", "-", ""}

    @staticmethod
    def normalizar_texto(valor_raw):
        v = valor_raw.strip().lower()

        v = (
            v.replace("á", "a")
             .replace("é", "e")
             .replace("í", "i")
             .replace("ó", "o")
             .replace("ú", "u")
        )

        if v in AtributoService.EQUIV_NA:
            return "N/A"

        return v

    @staticmethod
    def fuzzy_texto(valor_normalizado, atributo):
        existentes = list(
            ValorAtributo.objects.filter(atributo=atributo)
            .values_list("valor", flat=True)
        )

        if not existentes:
            return valor_normalizado

        mejor, score, _ = process.extractOne(
            valor_normalizado,
            existentes,
            scorer=fuzz.WRatio
        )

        if score >= 85:
            return mejor

        return valor_normalizado

    @staticmethod
    def normalizar_numero(valor_raw, atributo):
        v = valor_raw.strip().lower()

        if v in AtributoService.EQUIV_NA:
            return "N/A"

        try:
            num = float(v)
        except Exception:
            raise ValidationError(
                f"El atributo '{atributo.nombre}' debe ser numérico o 'N/A'."
            )

        # Si tiene decimales significativos → guardar exacto, sin corrección.
        # Ej: 8.11, 8.12, 8.13 son tonos distintos, no los tocamos.
        tiene_decimales = (num != int(num))
        if tiene_decimales:
            return str(int(num)) if num.is_integer() else str(num)

        # Solo para enteros → intentar corrección por tolerancia (Ej: 10ml vs 11ml typo)
        # TOL pequeño para no corregir valores legítimamente distintos
        TOL = 0.5

        existentes = ValorAtributo.objects.filter(
            atributo=atributo
        ).values_list("valor", flat=True)

        for existente in existentes:
            try:
                num_existente = float(existente)
            except Exception:
                continue

            # Solo comparar contra enteros existentes
            if num_existente != int(num_existente):
                continue

            if abs(num - num_existente) <= TOL:
                return str(int(num_existente))

        return str(int(num))

    @staticmethod
    def guardar_valores(producto, data):
        atributos = Atributo.objects.filter(categoria=producto.categoria)

        for atributo in atributos:
            key = f"atributo_{atributo.id}"
            valor_raw = (data.get(key) or "").strip()

            # TEXTO — fuzzy aplica a TODOS los atributos de tipo texto
            if atributo.tipo.strip().lower() == "texto":
                valor = AtributoService.normalizar_texto(valor_raw)

                # No aplicar fuzzy a N/A, no tiene sentido compararlo
                if valor != "N/A":
                    valor = AtributoService.fuzzy_texto(valor, atributo)

            # NUMÉRICO
            else:
                valor = AtributoService.normalizar_numero(valor_raw, atributo)

            ValorAtributo.objects.update_or_create(
                producto=producto,
                atributo=atributo,
                defaults={"valor": valor},
            )