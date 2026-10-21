import io
from types import SimpleNamespace

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from inventario.models import Inventario, Producto, SolicitudAjuste, Ubicacion
from inventario.services.imagen_service import ImagenService
from inventario.signals import borrar_foto_anterior
from inventario.templatetags import cloudinary_helpers as ch
from tienda_temp.models import Empleado, Usuario


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


class FotoReemplazadaTest(TestCase):
    """
    La foto anterior debe borrarse del storage al reemplazarla.

    Se prueba contra los signals directamente, con un storage falso, para no
    depender de Cloudinary ni del disco.
    """

    def setUp(self):
        self.borradas = []

        class StorageFalso:
            def delete(_, name):
                self.borradas.append(name)

        self.storage = StorageFalso()

    def _anterior(self, nombre):
        """Imita el FieldFile de la foto que ya estaba guardada."""
        anterior = SimpleNamespace(name=nombre, storage=self.storage)
        anterior.__bool__ = lambda: True
        return anterior

    def test_borra_la_foto_vieja_al_reemplazarla(self):
        producto = SimpleNamespace(_foto_anterior=self._anterior("productos/vieja.jpg"))

        borrar_foto_anterior(sender=None, instance=producto)

        self.assertEqual(self.borradas, ["productos/vieja.jpg"])

    def test_no_borra_nada_si_la_foto_no_cambio(self):
        producto = SimpleNamespace(_foto_anterior=None)

        borrar_foto_anterior(sender=None, instance=producto)

        self.assertEqual(self.borradas, [])

    def test_un_fallo_al_borrar_no_tumba_el_guardado(self):
        class StorageQueTruena:
            def delete(self, name):
                raise IOError("Cloudinary no responde")

        anterior = SimpleNamespace(name="productos/x.jpg", storage=StorageQueTruena())
        producto = SimpleNamespace(_foto_anterior=anterior)

        # No debe propagar la excepción: perder la foto vieja nunca vale
        # impedir que se guarde el producto.
        borrar_foto_anterior(sender=None, instance=producto)

    def test_no_reintenta_el_borrado_en_un_segundo_guardado(self):
        producto = SimpleNamespace(_foto_anterior=self._anterior("productos/vieja.jpg"))

        borrar_foto_anterior(sender=None, instance=producto)
        borrar_foto_anterior(sender=None, instance=producto)

        self.assertEqual(self.borradas, ["productos/vieja.jpg"])


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


# El hasher real tarda ~1.4 s por usuario; en tests no importa la seguridad.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SolicitudHuerfanaTest(TestCase):
    """
    Una solicitud de ajuste pendiente cuyo inventario se eliminó de la
    ubicación después de crearla. Pasó en producción (oct 2026): el panel de
    pendientes de la dueña tronaba con DoesNotExist y no podía entrar.
    """

    @classmethod
    def setUpTestData(cls):
        user = Usuario.objects.create_user(
            username="fabiola", email="fabiola@test.local", password="x"
        )
        cls.duena = Empleado.objects.create(
            user=user, rol="dueño", direccion="x", numero_contacto="1",
            contacto_emergencia="x", descripcion_contacto_emergencia="x",
        )
        cls.piso = Ubicacion.objects.create(nombre="Piso", direccion="x", tipo="piso")
        cls.producto = Producto.objects.create(
            nombre="Bolsa", precio_mayoreo=10, precio_menudeo=10, dueño=cls.duena
        )
        cls.otro = Producto.objects.create(
            nombre="Aretes", precio_mayoreo=10, precio_menudeo=10, dueño=cls.duena
        )
        Inventario.objects.create(producto=cls.otro, ubicacion=cls.piso, cantidad_actual=8)

    def setUp(self):
        self.client.force_login(self.duena.user)
        # Huérfana: no hay Inventario de self.producto en el piso
        self.huerfana = self._solicitud(self.producto)
        self.normal = self._solicitud(self.otro)

    def _solicitud(self, producto):
        return SolicitudAjuste.objects.create(
            producto=producto, ubicacion=self.piso, usuario=self.duena.user, cantidad=3
        )

    def test_el_panel_abre_aunque_haya_una_huerfana(self):
        resp = self.client.get(reverse("inventario:solicitudes_pendientes"))

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "fue eliminado")

    def test_la_huerfana_no_ofrece_aprobar_y_las_demas_si(self):
        resp = self.client.get(reverse("inventario:solicitudes_pendientes"))

        self.assertNotContains(
            resp, reverse("inventario:aprobar_solicitud_panel", args=[self.huerfana.id])
        )
        self.assertContains(
            resp, reverse("inventario:rechazar_solicitud_panel", args=[self.huerfana.id])
        )
        self.assertContains(
            resp, reverse("inventario:aprobar_solicitud_panel", args=[self.normal.id])
        )

    def test_aprobar_huerfana_desde_el_panel_no_truena_ni_la_cierra(self):
        resp = self.client.get(
            reverse("inventario:aprobar_solicitud_panel", args=[self.huerfana.id])
        )

        self.assertRedirects(resp, reverse("inventario:solicitudes_pendientes"))
        self.huerfana.refresh_from_db()
        self.assertEqual(self.huerfana.estado, "pendiente")

    def test_aprobar_huerfana_desde_el_correo_no_truena_ni_la_cierra(self):
        resp = self.client.get(
            reverse("inventario:aprobar_solicitud", args=[self.huerfana.id])
        )

        self.assertRedirects(resp, reverse("inventario:solicitudes_pendientes"))
        self.huerfana.refresh_from_db()
        self.assertEqual(self.huerfana.estado, "pendiente")

    def test_la_huerfana_se_puede_rechazar(self):
        self.client.get(reverse("inventario:rechazar_solicitud_panel", args=[self.huerfana.id]))

        self.huerfana.refresh_from_db()
        self.assertEqual(self.huerfana.estado, "rechazado")

    def test_no_deja_eliminar_inventario_con_solicitudes_pendientes(self):
        url = reverse("inventario:eliminar_inventario_ubicacion", args=[self.otro.id, self.piso.id])

        resp = self.client.delete(url)

        self.assertFalse(resp.json()["success"])
        self.assertTrue(Inventario.objects.filter(producto=self.otro, ubicacion=self.piso).exists())

    def test_elimina_inventario_si_no_hay_pendientes(self):
        self.client.get(reverse("inventario:rechazar_solicitud_panel", args=[self.normal.id]))
        url = reverse("inventario:eliminar_inventario_ubicacion", args=[self.otro.id, self.piso.id])

        resp = self.client.delete(url)

        self.assertTrue(resp.json()["success"])
        self.assertFalse(Inventario.objects.filter(producto=self.otro, ubicacion=self.piso).exists())
