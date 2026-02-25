from barcode import Code128, EAN13, UPCA
from inventario.models import Producto
from inventario.utils import generar_base64, generar_datamatrix_base64


class CodigoService:
    
    # ---------------------------------------------------------
    # VALIDAR CÓDIGOS REALES (EAN13, UPC-A, Code128)
    # ---------------------------------------------------------
    @staticmethod
    def validar_codigo_real(codigo):
        """
        Valida códigos reales sin permitir frases o textos largos.
        """

        # LIMPIAR BASURA INVISIBLE
        codigo = str(codigo).strip()

        # 1. Solo números o letras (sin espacios ni símbolos raros)
        if not codigo.isalnum():
            raise ValueError("El código contiene caracteres inválidos.")

        # 2. Longitud razonable para códigos de barras reales
        if len(codigo) < 6 or len(codigo) > 20:
            raise ValueError("La longitud del código no es válida para un código de barras.")

        # 3. EAN13
        if codigo.isdigit() and len(codigo) == 13:
            if CodigoService._validar_ean13(codigo):
                return "ean13"
            else:
                raise ValueError("El código EAN13 es inválido (dígito verificador incorrecto).")

        # 4. UPC-A
        if codigo.isdigit() and len(codigo) == 12:
            return "upca"

        # 5. Code128 (si la librería lo acepta)
        try:
            Code128(codigo)
            return "code128"
        except:
            pass

        # 6. Si no coincide con nada → NO aceptarlo
        raise ValueError("El código proporcionado no es un código de barras válido.")
        

    @staticmethod
    def _validar_ean13(codigo):
        """Valida el dígito verificador de un EAN13."""
        base = codigo[:-1]
        dv_real = int(codigo[-1])

        suma = 0
        for i, digit in enumerate(base):
            n = int(digit)
            suma += n if i % 2 == 0 else n * 3

        dv_calc = (10 - (suma % 10)) % 10
        return dv_calc == dv_real


    # ---------------------------------------------------------
    # GENERAR CÓDIGO INTERNO HUMANO
    # ---------------------------------------------------------
    @staticmethod
    def generar_codigo_interno(tamaño, dueño, subcategoria):
        """
        Genera un código interno humano + único.
        Ejemplo: ANAISGELISH001
        """

        # Prefijos basados en el dueño y la subcategoría
        prefijo_dueño = dueño.user.username.upper().replace(" ", "")
        prefijo_sub = subcategoria.nombre.upper().replace(" ", "")

        # Contador por dueño + subcategoría
        count = Producto.objects.filter(
            dueño=dueño,
            categoria=subcategoria
        ).count() + 1

        consecutivo = str(count).zfill(3)

        codigo_humano = f"{prefijo_dueño}{prefijo_sub}{consecutivo}"

        # Tipo de código según tamaño de etiqueta
        if tamaño == "chica":
            tipo = "datamatrix"
        elif tamaño == "mediana":
            tipo = "code128"
        elif tamaño == "grande":
            tipo = "ean13"
        else:
            raise ValueError("Tamaño de etiqueta inválido.")

        return codigo_humano, tipo


    # ---------------------------------------------------------
    # GENERAR IMAGEN BASE64 PARA EL FRONTEND
    # ---------------------------------------------------------
    @staticmethod
    def generar_imagen_base64(producto):
        """Genera la imagen base64 del código del producto."""
        if not producto.codigo_barras or not producto.tipo_codigo:
            return None

        if producto.tipo_codigo == "datamatrix":
            return generar_datamatrix_base64(producto.codigo_barras)

        if producto.tipo_codigo == "ean13":
            return generar_base64(producto.codigo_barras, EAN13)

        if producto.tipo_codigo == "upca":
            return generar_base64(producto.codigo_barras, UPCA)

        if producto.tipo_codigo == "code128":
            return generar_base64(producto.codigo_barras, Code128)

        return None
    