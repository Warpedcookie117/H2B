"""Precios por cantidad: reglas del servicio, Lista de precios y permisos."""
import json
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from inventario.models import Presentacion, Producto, TipoPresentacion
from inventario.services import presentacion_service as ps
from tienda_temp.models import Empleado, Usuario

CAJA = TipoPresentacion.CAJA
MEDIA = TipoPresentacion.MEDIA_DOCENA
DECENA = TipoPresentacion.DECENA


def crear_empleado(username, rol="dueño"):
    user = Usuario.objects.create_user(username=username, email=f"{username}@t.local", password="x",
                                       first_name=username)
    return Empleado.objects.create(user=user, rol=rol, direccion="x", numero_contacto="1",
                                   contacto_emergencia="x", descripcion_contacto_emergencia="x")


class LeerFilasTest(TestCase):

    def test_media_docena_y_decena_ignoran_las_piezas_que_manden(self):
        filas = ps.leer_filas([
            {"tipo": "media_docena", "piezas": 99, "precio": "150"},
            {"tipo": "decena", "precio": "240"},
        ])
        self.assertEqual([(f.tipo, f.piezas) for f in filas], [(MEDIA, 6), (DECENA, 10)])

    def test_caja_pide_piezas(self):
        with self.assertRaises(ValidationError) as e:
            ps.leer_filas([{"tipo": "caja", "piezas": "", "precio": "550"}])
        self.assertIn("Caja: escribe cuántas piezas trae.", e.exception.messages)

        with self.assertRaises(ValidationError):
            ps.leer_filas([{"tipo": "caja", "piezas": 1, "precio": "550"}])

        [caja] = ps.leer_filas([{"tipo": "caja", "piezas": "24", "precio": "550"}])
        self.assertEqual((caja.piezas, caja.precio), (24, Decimal("550.0")))

    def test_fila_sin_precio_se_ignora(self):
        self.assertEqual(ps.leer_filas([{"tipo": "caja", "piezas": 24, "precio": ""}]), [])
        self.assertEqual(ps.leer_filas(None), [])

    def test_precio_cero_negativo_o_texto(self):
        for precio in ("0", "-5", "abc", "NaN"):
            with self.assertRaises(ValidationError, msg=precio):
                ps.leer_filas([{"tipo": "decena", "precio": precio}])

    def test_tipo_que_no_existe(self):
        with self.assertRaises(ValidationError):
            ps.leer_filas([{"tipo": "ciento", "precio": "10"}])

    def test_repetido(self):
        with self.assertRaises(ValidationError) as e:
            ps.leer_filas([{"tipo": "decena", "precio": "10"}, {"tipo": "decena", "precio": "12"}])
        self.assertIn("Decena está dos veces. Deja solo uno.", e.exception.messages)

    def test_dos_cajas_de_distinto_tamano_si_se_puede(self):
        filas = ps.leer_filas([{"tipo": "caja", "piezas": 24, "precio": "550"},
                               {"tipo": "caja", "piezas": 50, "precio": "1000"}])
        self.assertEqual(len(filas), 2)


class ModeloTest(TestCase):

    def setUp(self):
        self.producto = Producto.objects.create(nombre="Serie", precio_mayoreo=25, precio_menudeo=30)

    def test_nombre(self):
        self.assertEqual(Presentacion(tipo=CAJA, piezas=24).nombre, "Caja de 24")
        self.assertEqual(Presentacion(tipo=MEDIA, piezas=6).nombre, "Media docena")

    def test_la_base_no_acepta_piezas_que_no_son_del_tipo(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Presentacion.objects.create(producto=self.producto, tipo=MEDIA, piezas=12, precio=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Presentacion.objects.create(producto=self.producto, tipo=CAJA, piezas=1, precio=10)

    def test_la_base_no_acepta_repetidos(self):
        Presentacion.objects.create(producto=self.producto, tipo=CAJA, piezas=24, precio=10)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Presentacion.objects.create(producto=self.producto, tipo=CAJA, piezas=24, precio=12)


class GuardarTest(TestCase):

    def setUp(self):
        self.producto = Producto.objects.create(nombre="Serie", precio_mayoreo=25, precio_menudeo=30)

    def guardar(self, filas):
        return ps.guardar_de_producto(self.producto, ps.leer_filas(filas))

    def test_agrega_cambia_y_quita_conservando_ids(self):
        self.guardar([{"tipo": "caja", "piezas": 24, "precio": "550"},
                      {"tipo": "media_docena", "precio": "150"}])
        caja_id = self.producto.presentaciones.get(tipo=CAJA).id

        resumen = self.guardar([{"tipo": "caja", "piezas": 24, "precio": "500"},
                                {"tipo": "decena", "precio": "240"}])

        self.assertEqual(resumen, {"nuevos": 1, "cambiados": 1, "quitados": 1})
        caja = self.producto.presentaciones.get(tipo=CAJA)
        self.assertEqual((caja.id, caja.precio), (caja_id, Decimal("500.0")))
        self.assertFalse(self.producto.presentaciones.filter(tipo=MEDIA).exists())

    def test_sin_cambios(self):
        self.guardar([{"tipo": "decena", "precio": "240"}])
        self.assertEqual(self.guardar([{"tipo": "decena", "precio": "240.0"}]),
                         {"nuevos": 0, "cambiados": 0, "quitados": 0})

    def test_para_venta_solo_del_mismo_producto(self):
        self.guardar([{"tipo": "decena", "precio": "240"}])
        decena = self.producto.presentaciones.get()
        self.assertEqual(ps.para_venta(self.producto.id, decena.id), decena)

        otro = Producto.objects.create(nombre="Otra", precio_mayoreo=1, precio_menudeo=1)
        with self.assertRaises(ValueError):
            ps.para_venta(otro.id, decena.id)
        with self.assertRaises(ValueError):
            ps.para_venta(self.producto.id, 999999)


class GuardarListaTest(TestCase):

    def setUp(self):
        self.a = Producto.objects.create(nombre="Serie A", precio_mayoreo=25, precio_menudeo=30)
        self.b = Producto.objects.create(nombre="Serie B", precio_mayoreo=25, precio_menudeo=30)
        ps.guardar_de_producto(self.a, ps.leer_filas([{"tipo": "caja", "piezas": 24, "precio": "550"}]))

    def test_guarda_todo(self):
        total = ps.guardar_lista([
            {"producto_id": self.a.id, "originales": [{"tipo": "caja", "piezas": 24, "precio": "550"}],
             "presentaciones": [{"tipo": "caja", "piezas": 24, "precio": "520"}]},
            {"producto_id": self.b.id, "originales": [],
             "presentaciones": [{"tipo": "caja", "piezas": 24, "precio": "520"},
                                {"tipo": "media_docena", "precio": "150"}]},
        ])
        self.assertEqual(total, {"productos": 2, "nuevos": 2, "cambiados": 1, "quitados": 0})
        self.assertEqual(self.b.presentaciones.count(), 2)

    def test_un_error_y_no_se_guarda_nada(self):
        with self.assertRaises(ps.ListaConErrores) as e:
            ps.guardar_lista([
                {"producto_id": self.b.id, "originales": [],
                 "presentaciones": [{"tipo": "decena", "precio": "240"}]},
                {"producto_id": self.a.id, "originales": [{"tipo": "caja", "piezas": 24, "precio": "550"}],
                 "presentaciones": [{"tipo": "caja", "piezas": "", "precio": "520"}]},
            ])
        self.assertIn(self.a.id, e.exception.errores)
        self.assertFalse(self.b.presentaciones.exists())

    def test_si_alguien_mas_lo_cambio_no_lo_pisa(self):
        with self.assertRaises(ps.ListaConErrores) as e:
            ps.guardar_lista([
                {"producto_id": self.a.id, "originales": [],   # cuando lo escaneó no tenía
                 "presentaciones": [{"tipo": "decena", "precio": "240"}]},
            ])
        self.assertIn("Alguien más", e.exception.errores[self.a.id][0])
        self.assertEqual(self.a.presentaciones.get().precio, Decimal("550.0"))


# Sin manifest: en local nunca se corre collectstatic (lo hace el deploy).
SIN_MANIFEST = {
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
}


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
                   STORAGES=SIN_MANIFEST)
class VistasTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.duena = crear_empleado("duena")
        cls.cajera = crear_empleado("cajera", rol="cajero")
        cls.producto = Producto.objects.create(nombre="Serie LED 100 blanca", precio_mayoreo=25,
                                               precio_menudeo=30, codigo_barras="750100",
                                               registrado_por=cls.duena)

    def post_lista(self, renglones):
        return self.client.post(reverse("inventario:precios_cantidad_guardar"),
                                json.dumps({"renglones": renglones}), content_type="application/json")

    def test_cajera_no_entra(self):
        self.client.force_login(self.cajera.user)
        self.assertEqual(self.client.get(reverse("inventario:lista_precios")).status_code, 302)
        self.assertEqual(self.client.get(reverse("inventario:precios_cantidad_buscar"), {"q": "750100"})
                         .status_code, 403)
        respuesta = self.post_lista([{"producto_id": self.producto.id, "originales": [],
                                      "presentaciones": [{"tipo": "decena", "precio": "1"}]}])
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(self.producto.presentaciones.exists())

    def test_duena_escanea_guarda_y_ve_el_ultimo(self):
        self.client.force_login(self.duena.user)
        self.assertEqual(self.client.get(reverse("inventario:lista_precios")).status_code, 200)

        datos = self.client.get(reverse("inventario:precios_cantidad_buscar"), {"q": "750100"}).json()
        self.assertEqual(datos["productos"][0]["producto_id"], self.producto.id)

        respuesta = self.post_lista([{"producto_id": self.producto.id, "originales": [],
                                      "presentaciones": [{"tipo": "caja", "piezas": 24, "precio": "550"}]}])
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json()["resumen"]["nuevos"], 1)
        self.assertEqual(respuesta.json()["productos"][0]["presentaciones"][0]["nombre"], "Caja de 24")

        ultimo = self.client.get(reverse("inventario:precios_cantidad_ultimo")).json()["producto"]
        self.assertEqual(ultimo["producto_id"], self.producto.id)

    def alta(self, empleado, presentaciones):
        import io
        import tempfile
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        from inventario.models import Categoria, Ubicacion

        padre = Categoria.objects.create(nombre="NAVIDAD")
        sub = Categoria.objects.create(nombre="LUCES", padre=padre)
        ubicacion = Ubicacion.objects.create(nombre="Bodega", direccion="x")
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), "red").save(buffer, format="JPEG")
        foto = SimpleUploadedFile("f.jpg", buffer.getvalue(), content_type="image/jpeg")

        self.client.force_login(empleado.user)
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            return self.client.post(reverse("inventario:nuevo_producto"), {
                "nombre": "Serie LED 300", "precio_menudeo": "45", "precio_mayoreo": "40",
                "dueño": self.duena.id, "categoria_padre": padre.id, "subcategoria": sub.id,
                "cantidad_inicial": 48, "ubicacion": ubicacion.id, "codigo_barras": "750300",
                "foto_url": foto, "presentaciones_json": json.dumps(presentaciones),
            }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    def test_alta_de_duena_guarda_los_precios_por_cantidad(self):
        resp = self.alta(self.duena, [{"tipo": "caja", "piezas": 12, "precio": "480"},
                                      {"tipo": "media_docena", "precio": "240"},
                                      {"tipo": "decena", "precio": ""}])
        self.assertTrue(resp.json()["success"], resp.content)
        producto = Producto.objects.get(nombre="Serie LED 300")
        self.assertEqual(sorted((p.tipo, p.piezas) for p in producto.presentaciones.all()),
                         [(CAJA, 12), (MEDIA, 6)])

    def test_alta_con_caja_sin_piezas_no_crea_el_producto(self):
        resp = self.alta(self.duena, [{"tipo": "caja", "piezas": "", "precio": "480"}])
        self.assertFalse(resp.json()["success"])
        self.assertIn("Caja: escribe cuántas piezas trae.", resp.json()["errors"])
        self.assertFalse(Producto.objects.filter(nombre="Serie LED 300").exists())

    def test_alta_de_cajera_ignora_los_precios_por_cantidad(self):
        resp = self.alta(self.cajera, [{"tipo": "caja", "piezas": 12, "precio": "480"}])
        self.assertTrue(resp.json()["success"], resp.content)
        self.assertFalse(Producto.objects.get(nombre="Serie LED 300").presentaciones.exists())

    def test_paginas_cargan_y_solo_la_duena_edita(self):
        from inventario.models import Categoria
        padre = Categoria.objects.create(nombre="NAVIDAD")
        self.producto.categoria = Categoria.objects.create(nombre="LUCES", padre=padre)
        self.producto.categoria_padre = padre
        self.producto.save()
        Presentacion.objects.create(producto=self.producto, tipo=CAJA, piezas=24, precio=550)
        detalle = reverse("inventario:detalle_producto", args=[self.producto.id])

        self.client.force_login(self.duena.user)
        alta = self.client.get(reverse("inventario:nuevo_producto")).content.decode()
        self.assertIn("¿Otro producto tiene el precio que quieres poner?", alta)
        html = self.client.get(detalle).content.decode()
        self.assertIn('"tipo": "caja"', html)
        self.assertIn('id="pcd-guardar"', html)
        self.assertIn("Lista de precios", self.client.get(reverse("inventario:lista_precios")).content.decode())

        self.client.force_login(self.cajera.user)
        self.assertNotIn("¿Otro producto tiene el precio", self.client.get(reverse("inventario:nuevo_producto"))
                         .content.decode())
        html = self.client.get(detalle).content.decode()
        self.assertIn('"tipo": "caja"', html)        # la ve
        self.assertNotIn('id="pcd-guardar"', html)   # pero no la cambia

    def test_errores_por_producto(self):
        self.client.force_login(self.duena.user)
        respuesta = self.post_lista([{"producto_id": self.producto.id, "originales": [],
                                      "presentaciones": [{"tipo": "caja", "precio": "550"}]}])
        self.assertEqual(respuesta.status_code, 400)
        self.assertIn(str(self.producto.id), respuesta.json()["por_producto"])
