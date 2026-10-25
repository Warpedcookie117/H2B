"""
Venta con precio por cantidad (Caja, Media docena, Decena) por el endpoint
real del POS: precio de la BD, piezas al inventario, ticket, regalos y
reportes que cuentan piezas.
"""
import json
from decimal import Decimal

from django.core.cache import cache
from django.urls import reverse

from inventario.models import Categoria, Inventario, Presentacion, TipoPresentacion
from ventas.models import Promocion, Venta, VentaDetalle, piezas_vendidas
from ventas.services.ticket_service import generar_texto_ticket
from ventas.tests.test_pos_reparto import PosRepartoTestCase
from ventas.tests.base import VentasBaseTestCase


class VentaConPresentacionTest(PosRepartoTestCase):

    def setUp(self):
        super().setUp()
        self.caja = Presentacion.objects.create(producto=self.prod_rosa, tipo=TipoPresentacion.CAJA,
                                                piezas=24, precio=Decimal("550"))

    def item_caja(self, precio=550, cantidad=1, presentacion=None):
        item = self.item(self.prod_rosa, precio, cantidad)
        item["presentacion_id"] = (presentacion or self.caja).id
        return item

    def test_dos_cajas_descuentan_48_piezas_y_guardan_el_snapshot(self):
        self.cobrar_ok([self.item_caja(cantidad=2)], efectivo=1100)

        detalle = VentaDetalle.objects.get()
        self.assertEqual((detalle.cantidad, detalle.piezas_por_unidad, detalle.piezas), (2, 24, 48))
        self.assertEqual(detalle.presentacion_nombre, "Caja de 24")
        self.assertEqual(detalle.subtotal, Decimal("1100.00"))
        self.assertEqual(self.salida.call_args.kwargs["cantidad"], 48)

    def test_pieza_y_caja_del_mismo_producto_en_la_misma_venta(self):
        self.cobrar_ok([self.item(self.prod_rosa, 30, 3), self.item_caja()], efectivo=640)
        cantidades = sorted(c.kwargs["cantidad"] for c in self.salida.call_args_list)
        self.assertEqual(cantidades, [3, 24])
        self.assertEqual(Venta.objects.get().total, Decimal("640.00"))

    def test_precio_distinto_al_de_la_bd_no_se_cobra(self):
        resp = self.cobrar([self.item_caja(precio=1)], efectivo=1)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ahora cuesta $550.00", resp.json()["message"])
        self.assertFalse(Venta.objects.exists())

    def test_presentacion_de_otro_producto_no_se_acepta(self):
        ajena = Presentacion.objects.create(producto=self.prod_anais, tipo=TipoPresentacion.DECENA,
                                            piezas=10, precio=Decimal("90"))
        resp = self.cobrar([self.item_caja(precio=90, presentacion=ajena)], efectivo=90)
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(Venta.objects.exists())

    def test_presentacion_borrada_no_se_acepta(self):
        item = self.item_caja()
        self.caja.delete()
        resp = self.cobrar([item], efectivo=550)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("ya no existe", resp.json()["message"])

    def test_ticket_dice_la_caja(self):
        self.cobrar_ok([self.item_caja()], efectivo=550)
        texto = generar_texto_ticket(Venta.objects.get())
        self.assertIn("Caja de 24", texto)

    def test_la_caja_no_dispara_regalos(self):
        cat = Categoria.objects.create(nombre="Luces")
        self.prod_rosa.categoria = cat
        self.prod_rosa.save(update_fields=["categoria"])
        promo = Promocion.objects.create(nombre="Regalo luces", tipo_condicion="categoria",
                                         categoria_disparadora=cat, tipo_resultado="regalo_fijo",
                                         producto_regalo=self.prod_yareli)
        regalo = {"producto_id": self.prod_yareli.id, "cantidad": 1, "precio_aplicado": 0,
                  "es_regalo": True, "promo_id": promo.id, "promo_nombre": promo.nombre}
        carrito = [self.item_caja(cantidad=3), regalo]
        from ventas.services.pos_service import POSService
        reales = [dict(i, cantidad=int(i["cantidad"]), precio_aplicado=float(i["precio_aplicado"])) for i in carrito]
        POSService._cap_regalos(reales)
        # Sin disparadores de pieza el tope es el mínimo conservador (1), no las 3 cajas.
        self.assertEqual(reales[1]["cantidad"], 1)

    def test_mas_vendidos_cuenta_piezas(self):
        self.cobrar_ok([self.item(self.prod_rosa, 30, 3), self.item_caja(cantidad=2)], efectivo=1190)
        total = VentaDetalle.objects.filter(producto=self.prod_rosa).aggregate(n=piezas_vendidas())["n"]
        self.assertEqual(total, 3 + 48)


class InventarioRealTest(VentasBaseTestCase):
    """Sin mock: la caja sale del inventario real del piso."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.login(self.cajero)
        s = self.client.session
        s["sucursal_actual"] = self.sucursal.id
        s["caja_actual"] = self.caja_anais.id
        s.save()
        from inventario.models import Ubicacion
        Ubicacion.objects.create(nombre="Bodega", direccion="x", sucursal=self.sucursal, tipo="bodega")
        Inventario.objects.create(producto=self.prod_rosa, ubicacion=self.piso, cantidad_actual=50)
        self.caja = Presentacion.objects.create(producto=self.prod_rosa, tipo=TipoPresentacion.CAJA,
                                                piezas=24, precio=Decimal("550"))

    def cobrar(self, cantidad):
        payload = {"carrito": [{"producto_id": self.prod_rosa.id, "cantidad": cantidad,
                                "precio_aplicado": 550, "presentacion_id": self.caja.id}],
                   "pagado_efectivo": 550 * cantidad, "pagado_tarjeta": 0, "descuento_pct": 0}
        return self.client.post(reverse("ventas:procesar_venta"), json.dumps(payload),
                                content_type="application/json")

    def test_dos_cajas_dejan_2_piezas(self):
        self.assertEqual(self.cobrar(2).status_code, 200)
        self.assertEqual(Inventario.objects.get(producto=self.prod_rosa).cantidad_actual, 2)

    def test_tres_cajas_no_alcanzan_y_no_se_vende_nada(self):
        resp = self.cobrar(3)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Bolsa Rosa", resp.json()["message"])
        self.assertEqual(Inventario.objects.get(producto=self.prod_rosa).cantidad_actual, 50)
        self.assertFalse(Venta.objects.exists())
