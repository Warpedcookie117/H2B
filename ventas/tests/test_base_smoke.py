from decimal import Decimal

from ventas.tests.base import VentasBaseTestCase


class BaseSmokeTest(VentasBaseTestCase):
    """Garantiza que el helper crear_venta replica la aritmética del POS."""

    def test_venta_210_pagada_con_500(self):
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60),
             self.renglon(self.prod_yareli, 10)],
            efectivo=500,
        )
        self.assertEqual(v.total, Decimal("210.00"))
        self.assertEqual(v.cambio, Decimal("290.00"))
        self.assertEqual(v.metodo_pago, "efectivo")
        self.assertEqual(v.detalles.count(), 3)
