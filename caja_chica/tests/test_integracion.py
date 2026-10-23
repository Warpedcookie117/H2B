"""Vistas, corte y dashboard con la base de datos real de tests."""
import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from caja_chica.models import MovimientoCaja, PersonaVale
from ventas.models import CorteCaja
from ventas.services.ticket_service import generar_texto_ticket
from ventas.tests.base import D, VentasBaseTestCase


class CajaChicaTestCase(VentasBaseTestCase):
    """Rosa es la responsable de servicios del escenario: la caja chica sale de su cajita."""

    def entrar(self, empleado=None, caja=None):
        self.login(empleado or self.cajero)
        s = self.client.session
        s["caja_actual"] = (caja or self.caja_anais).id
        s["sucursal_actual"] = self.sucursal.id
        s.save()

    def post(self, nombre_url, cuerpo):
        return self.client.post(reverse(f"caja_chica:{nombre_url}"), data=json.dumps(cuerpo),
                                content_type="application/json")

    def vale(self, **cuerpo):
        return self.post("registrar_vale", cuerpo)

    def gasto(self, descripcion, monto):
        return self.post("registrar_gasto", {"descripcion": descripcion, "monto": monto})


class ModalPosTest(CajaChicaTestCase):

    def test_fuera_de_caja_no_puede(self):
        self.login(self.cajero)
        self.assertEqual(self.client.get(reverse("caja_chica:estado")).status_code, 403)
        self.assertEqual(self.vale(nombre="Pablo", monto=10).status_code, 403)

    def test_vale_y_nombres_sin_repetir(self):
        self.entrar()
        r = self.vale(nombre="  pablo ", monto="200")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["mensaje"], "Listo. Saca $200.00 de la cajita de Rosa.")
        # Misma persona escrita distinto: se reusa.
        self.assertEqual(self.vale(nombre="PABLO", monto=50).status_code, 201)
        self.assertEqual(PersonaVale.objects.count(), 1)
        # Parecida: 409 con sugerencias, no guarda.
        r = self.vale(nombre="pabblo", monto=50)
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["sugerencias"][0]["nombre"], "Pablo")
        self.assertEqual(MovimientoCaja.objects.count(), 2)
        # Elige la sugerida o confirma que es otra.
        pablo = PersonaVale.objects.get()
        self.assertEqual(self.vale(persona_id=pablo.id, monto=5).status_code, 201)
        self.assertEqual(self.vale(nombre="pabblo", monto=5, es_otra_persona=True).status_code, 201)
        self.assertEqual(sorted(PersonaVale.objects.values_list("nombre", flat=True)), ["Pabblo", "Pablo"])

        estado = self.client.get(reverse("caja_chica:estado")).json()
        self.assertEqual(estado["duena"], "Rosa")
        self.assertEqual([p["nombre"] for p in estado["personas"]], ["Pabblo", "Pablo"])
        self.assertEqual(len(estado["sin_corte"]), 4)

    def test_gasto_y_errores(self):
        self.entrar()
        self.assertEqual(self.gasto("garrafón", "35").status_code, 201)
        m = MovimientoCaja.objects.get()
        self.assertEqual((m.tipo, m.descripcion, m.monto, m.descontado_a_id), ("gasto", "Garrafón", D(35), self.rosa.id))
        self.assertEqual(self.gasto("", "35").status_code, 400)
        self.assertEqual(self.gasto("agua", "0").json()["mensaje"], "La cantidad tiene que ser mayor a $0.")

    def test_sin_responsable_de_servicios(self):
        self.sucursal.dueño_servicios = None
        self.sucursal.save()
        self.entrar()
        r = self.gasto("agua", 10)
        self.assertEqual(r.status_code, 400)
        self.assertIn("responsable de servicios", r.json()["mensaje"])

    # Sin el manifiesto de collectstatic (no se corre en local): estáticos simples.
    @override_settings(STORAGES={**settings.STORAGES, "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_pos_tiene_el_boton_y_el_modal(self):
        self.entrar()
        html = self.client.get(reverse("ventas:pos")).content.decode()
        for s in ('id="btn-compraste"', "¿Compraste algo?", 'id="modal-compraste"', "caja_chica/compraste.js"):
            self.assertIn(s, html)


class CorteConCajaChicaTest(CajaChicaTestCase):

    def cortar(self):
        self.entrar()
        with mock.patch("ventas.views.ticket_corte_views.imprimir_silencioso"):
            self.client.get(reverse("ventas:corte_caja"))
        return CorteCaja.objects.latest("id")

    def test_gastos_y_vales_se_restan_a_la_cajita(self):
        self.crear_venta([self.renglon(self.prod_rosa, 300), self.renglon(self.prod_anais, 100)], efectivo=400)
        self.entrar()
        self.gasto("Garrafón", 50)
        self.vale(nombre="Pablo", monto=100)
        corte = self.cortar()
        self.assertEqual(MovimientoCaja.objects.filter(corte=corte).count(), 2)

        ctx = self.client.get(reverse("ventas:ticket_corte", args=[corte.id])).context["efectivo"]
        cajones = {c["nombre"]: c for c in ctx["cajones"]}
        self.assertEqual((cajones["Rosa"]["debe_haber"], cajones["Rosa"]["del_fondo"]), (D(150), D(0)))
        self.assertEqual(cajones["Anais"]["debe_haber"], D(100))
        self.assertEqual(ctx["total_debe_haber"], D(250))

        texto = generar_texto_ticket(corte)
        for s in ("VALES Y GASTOS", "Garrafón", "-$50.00", "Vales (1):", "(ya sin vales y gastos)"):
            self.assertIn(s, texto)
        self.assertNotIn("Pablo", texto)   # el detalle de vales solo lo ven las dueñas

    def test_sin_efectivo_sale_del_fondo_sin_negativos(self):
        self.entrar()
        self.gasto("Garrafón", 80)
        corte = self.cortar()
        ctx = self.client.get(reverse("ventas:ticket_corte", args=[corte.id])).context["efectivo"]
        rosa = ctx["cajones"][0]
        self.assertEqual((rosa["nombre"], rosa["debe_haber"], rosa["del_fondo"]), ("Rosa", D(0), D(80)))
        texto = generar_texto_ticket(corte)
        self.assertIn("Del fondo se usaron:", texto)
        self.assertNotIn("$-", texto)

    def test_lo_de_despues_del_corte_va_al_siguiente(self):
        self.entrar()
        self.gasto("Antes", 10)
        primero = self.cortar()
        self.entrar()
        self.gasto("Despues", 20)
        segundo = self.cortar()
        self.assertEqual(list(MovimientoCaja.objects.filter(corte=primero).values_list("descripcion", flat=True)), ["Antes"])
        self.assertEqual(list(MovimientoCaja.objects.filter(corte=segundo).values_list("descripcion", flat=True)), ["Despues"])


class DashboardCajaChicaTest(CajaChicaTestCase):

    def test_seccion_y_correcciones_de_duenas(self):
        self.entrar()
        self.vale(nombre="Pablo", monto=100)
        m = MovimientoCaja.objects.get()

        self.login(self.anais)
        html = self.client.get(reverse("tienda_temp:dashboard_dueno")).content.decode()
        for s in ('id="caja-chica"', "Vales y gastos", "Pablo"):
            self.assertIn(s, html)

        self.client.post(reverse("caja_chica:cambiar_monto", args=[m.id]), {"monto": "80"})
        m.refresh_from_db()
        self.assertEqual((m.monto, m.monto_original, m.editado_por_id), (D(80), D(100), self.anais.id))
        self.client.post(reverse("caja_chica:eliminar", args=[m.id]))
        m.refresh_from_db()
        self.assertIsNotNone(m.eliminado_en)

    def test_cajera_no_puede_corregir(self):
        self.entrar()
        self.vale(nombre="Pablo", monto=100)
        m = MovimientoCaja.objects.get()
        self.client.post(reverse("caja_chica:eliminar", args=[m.id]))
        self.client.post(reverse("caja_chica:cambiar_monto", args=[m.id]), {"monto": "1"})
        m.refresh_from_db()
        self.assertEqual((m.monto, m.eliminado_en), (D(100), None))

    def test_cuanto_llevo_yo_de_la_responsable(self):
        self.crear_venta([self.renglon(self.prod_rosa, 300)], efectivo=300, fecha=timezone.now())
        self.entrar()
        self.gasto("Garrafón", 50)
        self.login(self.rosa)
        mis = self.client.get(reverse("ventas:api_ventas_hoy")).json()["mis_ventas"]
        self.assertEqual((mis["efectivo"], mis["salidas"], mis["en_caja"], mis["del_fondo"]),
                         (300.0, 50.0, 250.0, 0.0))
        self.assertIn('id="dueno-ahorita-salidas"',
                      self.client.get(reverse("tienda_temp:dashboard_dueno")).content.decode())
