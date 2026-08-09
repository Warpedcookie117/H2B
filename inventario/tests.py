import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from inventario.services.imagen_service import ImagenService
from inventario.templatetags import cloudinary_helpers as ch


def _subida(imagen, nombre="foto.jpg", formato="JPEG", **guardar):
    """Serializa una imagen de Pillow como si viniera de un <input type=file>."""
    buffer = io.BytesIO()
    imagen.save(buffer, format=formato, **guardar)
    buffer.seek(0)
    return SimpleUploadedFile(nombre, buffer.read(), content_type=f"image/{formato.lower()}")


def _abrir(archivo):
    archivo.seek(0)
    return Image.open(io.BytesIO(archivo.read()))


class ImagenServiceTest(SimpleTestCase):

    def test_reduce_foto_grande_de_celular(self):
        grande = _subida(Image.new("RGB", (4032, 3024), "navy"))
        peso_antes = grande.size

        salida = ImagenService.comprimir(grande)

        self.assertLessEqual(max(_abrir(salida).size), ImagenService.MAX_LADO)
        self.assertLess(salida.size, peso_antes)

    def test_respeta_la_proporcion(self):
        salida = ImagenService.comprimir(_subida(Image.new("RGB", (4000, 2000), "olive")))

        ancho, alto = _abrir(salida).size
        self.assertEqual(ancho / alto, 2.0)

    def test_no_recomprime_una_imagen_que_ya_es_chica(self):
        chica = _subida(Image.new("RGB", (580, 580), "teal"))
        original = chica.read()
        chica.seek(0)

        salida = ImagenService.comprimir(chica)

        salida.seek(0)
        self.assertEqual(salida.read(), original)

    def test_aplica_la_rotacion_del_exif_a_los_pixeles(self):
        # Las fotos de celular guardan los píxeles horizontales y la rotación
        # aparte, en el EXIF (orientación 6 = girar 90°). Al re-codificar, ese
        # EXIF se pierde: si no horneamos la rotación, la foto queda acostada.
        exif = Image.Exif()
        exif[274] = 6
        acostada = _subida(Image.new("RGB", (4000, 3000), "maroon"), exif=exif.tobytes())

        ancho, alto = _abrir(ImagenService.comprimir(acostada)).size

        self.assertGreater(alto, ancho, "la foto debió quedar vertical")

    def test_aplana_transparencia_sobre_blanco(self):
        # JPEG no soporta canal alfa; un PNG transparente reventaría el save().
        transparente = _subida(
            Image.new("RGBA", (2000, 2000), (255, 0, 0, 0)), "logo.png", "PNG"
        )

        salida = ImagenService.comprimir(transparente)

        imagen = _abrir(salida)
        self.assertEqual(imagen.mode, "RGB")
        self.assertEqual(imagen.getpixel((0, 0)), (255, 255, 255))

    def test_la_salida_siempre_se_llama_jpg(self):
        salida = ImagenService.comprimir(
            _subida(Image.new("RGB", (3000, 3000), "purple"), "IMG_0042.HEIC")
        )

        self.assertEqual(salida.name, "IMG_0042.jpg")

    def test_un_archivo_ilegible_se_devuelve_intacto(self):
        # Nunca debe impedir que se guarde el producto.
        basura = SimpleUploadedFile("roto.jpg", b"esto no es una imagen", content_type="image/jpeg")

        self.assertIs(ImagenService.comprimir(basura), basura)

    def test_sin_foto_no_truena(self):
        self.assertIsNone(ImagenService.comprimir(None))


class _Foto:
    """Imita un ImageField de Cloudinary."""
    url = ("https://res.cloudinary.com/demo/image/upload/v1/media/productos/x")

    def __bool__(self):
        return True


# Todos los helpers que producen una URL para consumo externo.
HELPERS = (ch.foto_mini, ch.foto_card, ch.foto_detalle, ch.foto_pdf, ch.foto_master)


class CatalogoDeTamañosTest(SimpleTestCase):

    def test_ninguna_url_sale_sin_transformacion(self):
        # Comprobado en producción: una URL sin transformación hace que
        # Cloudinary guarde una copia del tamaño COMPLETO del original,
        # duplicando el storage de esa foto. Ya nos costó ~4 GB una vez.
        for helper in HELPERS:
            url = helper(_Foto())
            resto = url.split("/image/upload/", 1)[1]
            primer_segmento = resto.split("/", 1)[0]
            self.assertIn(
                "w_", primer_segmento,
                f"{helper.__name__} devolvió una URL sin transformación: {url}",
            )

    def test_el_catalogo_esta_acotado(self):
        # Si este test falla es porque alguien agregó un ancho nuevo. No está
        # prohibido, pero significa un derivado más por producto en Cloudinary:
        # actualiza el número a conciencia, no por inercia.
        anchos = {ch.ANCHO_MINI, ch.ANCHO_CARD, ch.ANCHO_DETALLE,
                  ch.ANCHO_PDF, ch.ANCHO_MASTER}
        self.assertLessEqual(len(anchos), 4, f"anchos distintos en uso: {sorted(anchos)}")

    def test_sin_foto_devuelve_cadena_vacia(self):
        for helper in HELPERS:
            self.assertEqual(helper(None), "", helper.__name__)

    def test_no_toca_urls_que_no_son_de_cloudinary(self):
        # En desarrollo el storage es local y la URL no lleva /image/upload/.
        class Local:
            url = "/media/productos/x.jpg"
            def __bool__(self): return True

        for helper in HELPERS:
            self.assertEqual(helper(Local()), "/media/productos/x.jpg", helper.__name__)
