from barcode import Code128
from inventario.models import Producto


class CodigoService:

    @staticmethod
    def validar_codigo_real(codigo):
        codigo = str(codigo).strip()

        if not codigo.isalnum():
            raise ValueError("El código contiene caracteres inválidos.")

        if len(codigo) < 3 or len(codigo) > 20:
            raise ValueError("La longitud del código no es válida para un código de barras.")

        # EAN-13 con checksum válido → tipo formal "ean13"
        # Si NO pasa checksum: NO rechazar; caen abajo como Code 128. Hay
        # fabricantes (sobre todo importados baratos) que imprimen códigos
        # numéricos de 13 dígitos sin seguir el estándar GS1, y son códigos
        # legítimos del producto. Mejor aceptarlos como genéricos.
        if codigo.isdigit() and len(codigo) == 13:
            if CodigoService._validar_ean13(codigo):
                return "ean13"

        # UPC-A con checksum válido → tipo formal "upca"
        # Misma lógica: si no cuadra el checksum, no es UPC-A real pero sí
        # puede ser un código numérico legítimo del proveedor.
        if codigo.isdigit() and len(codigo) == 12:
            if CodigoService._validar_ean13("0" + codigo):
                return "upca"

        # Fallback: cualquier alfanumérico válido se acepta como Code 128
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
        Itera hasta encontrar un código que no exista en la BD.
        """

        prefijo_dueño = dueño.user.username.upper().replace(" ", "")
        prefijo_sub = subcategoria.nombre.upper().replace(" ", "")

        count = Producto.objects.filter(
            registrado_por=dueño,
            categoria=subcategoria
        ).count() + 1

        for _ in range(50000):
            consecutivo = str(count).zfill(4)

            if tamaño == "chica":
                codigo = f"{prefijo_dueño[:2]}{prefijo_sub[:1]}{consecutivo[-3:]}"
            elif tamaño == "mediana":
                codigo = f"{prefijo_dueño[:2]}{prefijo_sub[:2]}{consecutivo[-4:]}"
            elif tamaño == "grande":
                codigo = f"{prefijo_dueño[:4]}{prefijo_sub[:4]}{consecutivo[-4:]}"
            else:
                raise ValueError("Tamaño de etiqueta inválido.")

            if not Producto.objects.filter(codigo_barras=codigo).exists():
                return codigo, "code128"

            count += 1

        raise ValueError("No se pudo generar un código interno único. Contacta al administrador.")
    
    @staticmethod
    def tamano_por_tipo(tipo_codigo):
        if tipo_codigo == "ean13":
            return "grande"
        if tipo_codigo == "upca":
            return "mediana"
        return "chica"  # code128 u otros