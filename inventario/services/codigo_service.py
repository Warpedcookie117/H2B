from barcode import Code128
from inventario.models import Producto


class CodigoService:

    @staticmethod
    def validar_codigo_real(codigo):
        codigo = str(codigo).strip()

        if not codigo.isalnum():
            raise ValueError("El código contiene caracteres inválidos.")

        if len(codigo) < 6 or len(codigo) > 20:
            raise ValueError("La longitud del código no es válida para un código de barras.")

        if codigo.isdigit() and len(codigo) == 13:
            return "ean13"

        if codigo.isdigit() and len(codigo) == 12:
            return "upca"

        try:
            Code128(codigo)
            return "code128"
        except:
            pass

        raise ValueError("El código proporcionado no es válido.")

    @staticmethod
    def _validar_ean13(codigo):
        base = codigo[:-1]
        dv_real = int(codigo[-1])

        suma = 0
        for i, digit in enumerate(base):
            n = int(digit)
            suma += n if i % 2 == 0 else n * 3

        dv_calc = (10 - (suma % 10)) % 10
        return dv_calc == dv_real

    # ---------------------------------------------------------
    # GENERAR CÓDIGO INTERNO EXACTO POR TAMAÑO
    # ---------------------------------------------------------
    @staticmethod
    def generar_codigo_interno(tamaño, dueño, subcategoria):
        """
        Genera un código interno EXACTO según tamaño:
        - chica: 6 caracteres
        - mediana: 8 caracteres
        - grande: 12 caracteres
        """

        prefijo_dueño = dueño.user.username.upper().replace(" ", "")
        prefijo_sub = subcategoria.nombre.upper().replace(" ", "")

        count = Producto.objects.filter(
            registrado_por=dueño,
            categoria=subcategoria
        ).count() + 1

        consecutivo = str(count).zfill(4)  # 4 dígitos para flexibilidad

        # --- CHICA (6) ---
        if tamaño == "chica":
            # 2 dueño + 1 sub + 3 del consecutivo
            d = prefijo_dueño[:2]
            s = prefijo_sub[:1]
            c = consecutivo[-3:]
            codigo = f"{d}{s}{c}"
            return codigo, "code128"

        # --- MEDIANA (8) ---
        if tamaño == "mediana":
            # 2 dueño + 2 sub + 4 consecutivo = 8 exactos
            d = prefijo_dueño[:2]
            s = prefijo_sub[:2]
            c = consecutivo[-4:]
            codigo = f"{d}{s}{c}"
            return codigo, "code128"

        # --- GRANDE (12) ---
        if tamaño == "grande":
            # 4 dueño + 4 sub + 4 consecutivo = 12 exactos
            d = prefijo_dueño[:4]
            s = prefijo_sub[:4]
            c = consecutivo[-4:]
            codigo = f"{d}{s}{c}"
            return codigo, "code128"

        raise ValueError("Tamaño de etiqueta inválido.")
    
    @staticmethod
    def tamano_por_tipo(tipo_codigo):
        if tipo_codigo == "ean13":
            return "grande"
        if tipo_codigo == "upca":
            return "mediana"
        return "chica"  # code128 u otros