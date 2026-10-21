"""
Fase 1 — Hotfix del dashboard del dueño: el efectivo por caja debe ser el
NETO (pagado_efectivo - cambio), igual que el ticket de corte, y el total
debe salir de Venta.total (ya con descuento), no de efectivo + tarjeta.
"""
from django.urls import reverse

from ventas.tests.base import VentasBaseTestCase


class DashboardVentasHoyTest(VentasBaseTestCase):

    def setUp(self):
        self.login(self.anais)

    def _api(self):
        response = self.client.get(reverse("ventas:api_ventas_hoy"))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def _caja_api(self, data, nombre):
        for caja in data["cajas"]:
            if caja["caja"] == nombre:
                return caja
        self.fail(f"La API no trae la caja {nombre!r}")

    def _dashboard(self):
        response = self.client.get(reverse("tienda_temp:dashboard_dueno"))
        self.assertEqual(response.status_code, 200)
        return response

    # ------------------------------------------------------------------
    # API de polling
    # ------------------------------------------------------------------

    def test_api_ventas_hoy_resta_cambio(self):
        # Venta de 120 pagada con 500 → cambio 380; en el cajón quedan 120.
        self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, caja=self.caja_anais)

        data = self._api()
        caja = self._caja_api(data, "Caja Anais")

        self.assertIsInstance(caja["efectivo"], float)
        self.assertIsInstance(caja["tarjeta"], float)
        self.assertIsInstance(caja["total"], float)
        self.assertEqual(caja["efectivo"], 120.0)
        self.assertEqual(caja["tarjeta"], 0.0)
        self.assertEqual(caja["total"], 120.0)

        self.assertEqual(data["chart"][0]["efectivo"], 120.0)
        self.assertEqual(data["chart"][0]["total"], 120.0)

    def test_api_ventas_hoy_pago_mixto_con_descuento(self):
        # 200 con 10% de descuento → total 180. Tarjeta 100 + efectivo 100
        # → cambio 20; efectivo neto 80.
        self.crear_venta(
            [self.renglon(self.prod_anais, 200)],
            efectivo=100, tarjeta=100, descuento_pct=10, caja=self.caja_anais,
        )

        data = self._api()
        caja = self._caja_api(data, "Caja Anais")

        self.assertEqual(caja["efectivo"], 80.0)
        self.assertEqual(caja["tarjeta"], 100.0)
        self.assertEqual(caja["total"], 180.0)

        self.assertEqual(data["chart"][0]["efectivo"], 80.0)
        self.assertEqual(data["chart"][0]["tarjeta"], 100.0)
        self.assertEqual(data["chart"][0]["total"], 180.0)

    def test_api_ventas_hoy_caja_sin_ventas_en_cero(self):
        self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, caja=self.caja_anais)

        caja = self._caja_api(self._api(), "Caja Fabiola")

        self.assertEqual(caja["efectivo"], 0.0)
        self.assertEqual(caja["tarjeta"], 0.0)
        self.assertEqual(caja["total"], 0.0)

    # ------------------------------------------------------------------
    # Dashboard (render inicial) vs API
    # ------------------------------------------------------------------

    def test_dashboard_cards_coinciden_con_api(self):
        self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, caja=self.caja_anais)
        self.crear_venta(
            [self.renglon(self.prod_rosa, 200)],
            efectivo=100, tarjeta=100, descuento_pct=10, caja=self.caja_anais,
        )
        self.crear_venta([self.renglon(self.prod_yareli, 50)], tarjeta=50, caja=self.caja_fabiola)

        api_cajas = {(c["sucursal"], c["caja"]): c for c in self._api()["cajas"]}
        response = self._dashboard()

        comparadas = 0
        for sucursal in response.context["ventas_por_sucursal"]:
            for caja in sucursal["cajas"]:
                api = api_cajas[(sucursal["sucursal"], caja["nombre"])]
                for campo in ("efectivo", "tarjeta", "total"):
                    self.assertEqual(
                        float(caja[campo]), api[campo],
                        f"{caja['nombre']} / {campo}: dashboard y API no coinciden",
                    )
                comparadas += 1
        self.assertEqual(comparadas, 2)

        # Valores esperados en el render inicial: 120 + 80 neto, 100 tarjeta.
        cajas = {c["nombre"]: c for c in response.context["ventas_por_sucursal"][0]["cajas"]}
        self.assertEqual(float(cajas["Caja Anais"]["efectivo"]), 200.0)
        self.assertEqual(float(cajas["Caja Anais"]["tarjeta"]), 100.0)
        self.assertEqual(float(cajas["Caja Anais"]["total"]), 300.0)
        self.assertEqual(float(cajas["Caja Fabiola"]["total"]), 50.0)

        chart = response.context["ventas_chart_sucursal"][0]
        self.assertEqual(chart["efectivo"], 200.0)
        self.assertEqual(chart["tarjeta"], 150.0)
        self.assertEqual(chart["total"], 350.0)

    def test_chart_sin_decimal(self):
        # ventas_chart_sucursal se inyecta con |safe en un <script>: un
        # Decimal ahí se pinta como "Decimal('...')" y rompe el JS.
        self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, caja=self.caja_anais)

        response = self._dashboard()

        self.assertNotIn("Decimal(", response.content.decode())
