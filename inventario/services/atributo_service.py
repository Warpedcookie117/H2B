from rapidfuzz import process, fuzz
from django.core.exceptions import ValidationError
from inventario.models import Atributo, ValorAtributo


class AtributoService:

    EQUIV_NA = {"n/a", "na", "no aplica", "-", ""}

    @staticmethod
    def normalizar_texto(valor_raw):
        print(f"[DEBUG TEXTO] RAW='{repr(valor_raw)}'")

        v = valor_raw.strip().lower()

        v = (
            v.replace("á", "a")
             .replace("é", "e")
             .replace("í", "i")
             .replace("ó", "o")
             .replace("ú", "u")
        )

        if v in AtributoService.EQUIV_NA:
            print(f"[DEBUG TEXTO] → 'N/A'")
            return "N/A"

        print(f"[DEBUG TEXTO] NORMALIZADO='{v}'")
        return v

    @staticmethod
    def fuzzy_texto(valor_normalizado, atributo):
        print(f"[DEBUG FUZZY] atributo={atributo.nombre} valor='{valor_normalizado}'")

        existentes = list(
            ValorAtributo.objects.filter(atributo=atributo)
            .values_list("valor", flat=True)
        )

        print(f"[DEBUG FUZZY] existentes={existentes}")

        if not existentes:
            print("[DEBUG FUZZY] No hay existentes → se queda igual")
            return valor_normalizado

        mejor, score, _ = process.extractOne(
            valor_normalizado,
            existentes,
            scorer=fuzz.WRatio
        )

        print(f"[DEBUG FUZZY] mejor='{mejor}' score={score}")

        if score >= 85:
            print(f"[DEBUG FUZZY] → Normalizado a existente '{mejor}'")
            return mejor

        print("[DEBUG FUZZY] → No aplica fuzzy")
        return valor_normalizado

    @staticmethod
    def normalizar_numero(valor_raw, atributo):
        print(f"[DEBUG NUM] atributo={atributo.nombre} RAW='{repr(valor_raw)}'")

        v = valor_raw.strip().lower()

        if v in AtributoService.EQUIV_NA:
            print("[DEBUG NUM] → 'N/A' por equivalencia")
            return "N/A"

        try:
            num = float(v)
            print(f"[DEBUG NUM] float={num}")
        except Exception as e:
            print(f"[DEBUG NUM ERROR] No se pudo convertir '{v}' a número")
            raise ValidationError(
                f"El atributo '{atributo.nombre}' debe ser numérico o 'N/A'."
            )

        existentes = ValorAtributo.objects.filter(atributo=atributo).values_list("valor", flat=True)
        print(f"[DEBUG NUM] existentes={list(existentes)}")

        TOL = 0.3

        for existente in existentes:
            try:
                num_existente = float(existente)
            except:
                continue

            if abs(num - num_existente) <= TOL:
                print(f"[DEBUG NUM] Coincide con existente '{num_existente}'")
                return str(num_existente)

        print(f"[DEBUG NUM] Nuevo valor '{num}'")
        return str(num)

    @staticmethod
    def guardar_valores(producto, data):
        atributos = Atributo.objects.filter(categoria=producto.categoria)

        print("\n================= DEBUG GUARDAR VALORES =================")
        print(f"Producto: {producto.id} | Categoria: {producto.categoria.nombre}")
        print("POST DATA:", {k: repr(v) for k, v in data.items()})
        print("=========================================================\n")

        for atributo in atributos:
            key = f"atributo_{atributo.id}"
            valor_raw = (data.get(key) or "").strip()

            print(f"\n[DEBUG LOOP] atributo_id={atributo.id} nombre={atributo.nombre} tipo={atributo.tipo}")
            print(f"[DEBUG LOOP] valor_raw='{repr(valor_raw)}'")

            if atributo.tipo.strip().lower() == "texto":
                valor = AtributoService.normalizar_texto(valor_raw)

                if atributo.nombre.lower() in ["marca", "color", "material", "modelo"]:
                    valor = AtributoService.fuzzy_texto(valor, atributo)

            else:
                valor = AtributoService.normalizar_numero(valor_raw, atributo)

            print(f"[DEBUG SAVE] Guardando valor='{valor}' para atributo='{atributo.nombre}'")

            ValorAtributo.objects.update_or_create(
                producto=producto,
                atributo=atributo,
                defaults={"valor": valor},
            )

        print("\n================= FIN DEBUG GUARDAR VALORES =================\n")