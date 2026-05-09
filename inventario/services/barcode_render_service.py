import base64
from io import BytesIO
from barcode import Code128, EAN13, UPCA
from barcode.writer import ImageWriter


class BarcodeRenderService:

    # Presets por tamaño de etiqueta (pensados para:
    # chica 50×20 mm, mediana 100×30 mm, grande 135×32 mm)
    SIZE_PRESETS = {
        "chica": {
            "module_width": 0.38,
            "module_height": 10,
            "font_size": 8,
            "quiet_zone": 4.0,   # GS1 recomienda ≥10× module_width por lado
            "dpi": 203,
        },
        "mediana": {
            "module_width": 0.50,
            "module_height": 14,
            "font_size": 10,
            "quiet_zone": 5.0,
            "dpi": 203,
        },
        "grande": {
            "module_width": 0.55,
            "module_height": 16,
            "font_size": 12,
            "quiet_zone": 5.5,
            "dpi": 300,
        },
    }

    # Mapeo de tipo de código a clase de la librería
    BARCODE_CLASSES = {
        "code128": Code128,
        "ean13": EAN13,
        "upca": UPCA,
    }

    @staticmethod
    def generar(codigo, tipo, tamaño):
        """
        Genera un código de barras en base64 según:
        - código (texto)
        - tipo (code128, ean13, upca)
        - tamaño (chica, mediana, grande)
        """

        if tipo not in BarcodeRenderService.BARCODE_CLASSES:
            raise ValueError(f"Tipo de código no soportado: {tipo}")

        if tamaño not in BarcodeRenderService.SIZE_PRESETS:
            raise ValueError(f"Tamaño de etiqueta no válido: {tamaño}")

        barcode_class = BarcodeRenderService.BARCODE_CLASSES[tipo]
        options = BarcodeRenderService.SIZE_PRESETS[tamaño]

        buffer = BytesIO()

        # Generar imagen
        barcode_class(codigo, writer=ImageWriter()).write(buffer, options)

        # Convertir a base64
        return base64.b64encode(buffer.getvalue()).decode("utf-8")