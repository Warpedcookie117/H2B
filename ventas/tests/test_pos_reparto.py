"""
Llave `reparto_efectivo` en la respuesta de procesar_venta (modal de cambio
del POS): a qué cajón físico de cada dueña va el efectivo del cobro.

Lo crítico no es el cálculo (eso lo cubre test_reparto.py) sino que la llave
es OPCIONAL: la venta ya está guardada cuando se calcula, así que si el
reparto truena o devuelve algo que no se puede guardar en la IdempotencyKey,
el cobro tiene que seguir respondiendo "ok" y la llave idempotente NO se
libera — si no, la cajera ve error, reintenta y la venta se duplica.

Todo pasa por el endpoint real; solo se mockea el descuento de inventario.
"""
import json
import math
import random
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.urls import reverse

import ventas.services.reparto as reparto_mod
from inventario.models import Categoria, Inventario, Ubicacion
from ventas.models import IdempotencyKey, Promocion, Venta
from ventas.services.pos_service import DESCUENTOS_PERMITIDOS
from ventas.tests.base import VentasBaseTestCase

LLAVES_DE_SIEMPRE = {
    "status", "venta_id", "total_venta", "pagado_efectivo", "pagado_tarjeta",
    "cambio", "impresion_ok", "descuento", "url_html", "url_pdf", "url_termico",
    "ticket_texto",
    # Stock de lo vendido (cards al día sin websocket). Opcional como el reparto.
    "stock",
}


def centavos(x):
    return round(x * 100)


class PosRepartoTestCase(VentasBaseTestCase):

    def setUp(self):
        # El candado pos_lock_<empleado> vive en la caché: que no se cuele
        # de un test a otro.
        cache.clear()
        self.addCleanup(cache.clear)

        patcher = mock.patch(
            "ventas.services.pos_service.InventarioService.salida_inteligente"
        )
        self.salida = patcher.start()
        self.addCleanup(patcher.stop)

        self.login(self.cajero)
        s = self.client.session
        s["sucursal_actual"] = self.sucursal.id
        s["caja_actual"] = self.caja_anais.id
        s.save()
        self.url = reverse("ventas:procesar_venta")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def item(self, producto, precio, cantidad=1):
        return {
            "producto_id": producto.id,
            "cantidad": cantidad,
            "precio_aplicado": precio,
            "es_servicio": False,
        }

    def item_servicio(self, precio, nombre="Prod. sin registro", cantidad=1):
        return {
            "producto_id": None,
            "cantidad": cantidad,
            "precio_aplicado": precio,
            "es_servicio": True,
            "nombre_servicio": nombre,
        }

    def cobrar(self, carrito, efectivo=0, tarjeta=0, descuento_pct=0, key=None):
        payload = {
            "carrito": carrito,
            "pagado_efectivo": efectivo,
            "pagado_tarjeta": tarjeta,
            "descuento_pct": descuento_pct,
        }
        if key is not None:
            payload["idempotency_key"] = key
        return self.client.post(self.url, data=json.dumps(payload), content_type="application/json")

    def cobrar_ok(self, *args, **kwargs):
        resp = self.cobrar(*args, **kwargs)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data["status"], "ok", data)
        return data

    def carrito_210(self):
        """Ejemplo del dueño: Rosa 140 + Anais 60 + Yareli 10."""
        return [
            self.item(self.prod_rosa, 140),
            self.item(self.prod_anais, 60),
            self.item(self.prod_yareli, 10),
        ]

    def assertCuadra(self, r):
        """neto == lo que se queda la receptora + lo que pasa + lo sin cajón (centavos)."""
        suma = (centavos(r["queda_receptora"])
                + sum(centavos(p["efectivo"]) for p in r["pasar"])
                + centavos(r["sin_cajon"]))
        self.assertEqual(centavos(r["neto"]), suma, r)


# ----------------------------------------------------------------------
# Respuesta normal
# ----------------------------------------------------------------------

class RespuestaConRepartoTest(PosRepartoTestCase):

    def test_ejemplo_210_pagado_con_500(self):
        data = self.cobrar_ok(self.carrito_210(), efectivo=500)

        venta = Venta.objects.get()
        # Las llaves de siempre, con los mismos valores que antes del cambio.
        self.assertEqual(set(data), LLAVES_DE_SIEMPRE | {"reparto_efectivo"})
        self.assertEqual(data["venta_id"], venta.id)
        self.assertEqual(data["total_venta"], 210.0)
        self.assertEqual(data["pagado_efectivo"], 500.0)
        self.assertEqual(data["pagado_tarjeta"], 0.0)
        self.assertEqual(data["cambio"], 290.0)
        self.assertIs(data["impresion_ok"], False)
        self.assertEqual(data["descuento"], 0.0)
        self.assertEqual(data["url_html"], reverse("ventas:ticket_venta", args=[venta.id]))
        self.assertEqual(data["url_pdf"], reverse("ventas:ticket_venta_pdf", args=[venta.id]))
        self.assertEqual(data["url_termico"], reverse("ventas:ticket_venta_termico", args=[venta.id]))
        self.assertIsInstance(data["ticket_texto"], str)
        self.assertTrue(data["ticket_texto"])

        r = data["reparto_efectivo"]
        self.assertEqual(r["version"], 2)
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["recibido"], 500.0)
        self.assertEqual(r["cambio"], 290.0)
        self.assertEqual(r["neto"], 210.0)
        self.assertEqual(r["tarjeta"], 0.0)
        self.assertEqual(r["receptora"], {"empleado_id": self.rosa.id, "nombre": "Rosa"})
        self.assertEqual(r["queda_receptora"], 140.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "efectivo": 60.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "efectivo": 10.0},
        ])
        self.assertEqual(r["sin_cajon"], 0.0)
        # Sin tarjeta no hay Clip y el efectivo alcanzó para todas.
        self.assertIsNone(r["clip"])
        self.assertEqual(r["deudas"], [])
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "total": 140.0},
            {"empleado_id": self.anais.id, "nombre": "Anais", "total": 60.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "total": 10.0},
        ])
        self.assertCuadra(r)
        self.assertEqual(self.salida.call_count, 3)

    def test_pago_mixto_varias(self):
        # 150 = Rosa 100 + Anais 50; 50 con tarjeta y 100 en efectivo exacto.
        data = self.cobrar_ok(
            [self.item(self.prod_rosa, 100), self.item(self.prod_anais, 50)],
            efectivo=100, tarjeta=50,
        )
        r = data["reparto_efectivo"]
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["neto"], 100.0)
        self.assertEqual(r["tarjeta"], 50.0)
        self.assertEqual(r["cambio"], 0.0)
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual([p["empleado_id"] for p in r["pasar"]], [self.anais.id])
        # Regla del Clip: los 50 de tarjeta van al Clip de Rosa (receptora) y
        # del efectivo se le completan a Anais sus 50; a Rosa le quedan 50
        # (50 + 50 = 100). Antes era proporcional (66.67 / 33.33).
        self.assertEqual(r["queda_receptora"], 50.0)
        self.assertEqual(r["pasar"][0]["efectivo"], 50.0)
        self.assertEqual(r["clip"], {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 50.0})
        self.assertEqual(r["deudas"], [])
        self.assertCuadra(r)

    def test_pago_mixto_una(self):
        data = self.cobrar_ok([self.item(self.prod_anais, 200)], efectivo=150, tarjeta=100)
        r = data["reparto_efectivo"]
        self.assertEqual(r["caso"], "una")
        self.assertEqual(r["receptora"]["empleado_id"], self.anais.id)
        self.assertEqual(r["cambio"], 50.0)
        self.assertEqual(r["neto"], 100.0)
        self.assertEqual(r["queda_receptora"], 100.0)
        self.assertEqual(r["pasar"], [])
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 100.0})
        self.assertEqual(r["deudas"], [])
        self.assertCuadra(r)

    def test_solo_tarjeta_es_sin_efectivo(self):
        data = self.cobrar_ok(
            [self.item(self.prod_rosa, 80), self.item(self.prod_anais, 20)], tarjeta=100,
        )
        r = data["reparto_efectivo"]
        self.assertEqual(r["caso"], "sin_efectivo")
        self.assertEqual(r["neto"], 0.0)
        self.assertEqual(r["tarjeta"], 100.0)
        # v2: Rosa (80) es receptora aunque no haya efectivo: cobra los 100 en
        # su Clip y le debe sus 20 a Anais.
        self.assertEqual(r["receptora"], {"empleado_id": self.rosa.id, "nombre": "Rosa"})
        self.assertEqual(r["clip"], {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 100.0})
        self.assertEqual(r["deudas"], [{"empleado_id": self.anais.id, "nombre": "Anais", "monto": 20.0}])
        self.assertEqual(r["queda_receptora"], 0.0)
        self.assertEqual(r["pasar"], [])
        self.assertCuadra(r)

    def test_servicio_va_al_cajon_de_la_responsable(self):
        # Rosa no vende productos en esta cuenta, pero es responsable de
        # servicios: el efectivo del servicio va a SU cajón.
        data = self.cobrar_ok(
            [self.item_servicio(30), self.item(self.prod_anais, 50)], efectivo=100,
        )
        r = data["reparto_efectivo"]
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["neto"], 80.0)
        self.assertEqual(r["receptora"]["empleado_id"], self.anais.id)
        self.assertEqual(r["queda_receptora"], 50.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "efectivo": 30.0},
        ])
        self.assertCuadra(r)
        # El servicio se guardó sin producto y no descontó inventario.
        venta = Venta.objects.get()
        self.assertTrue(venta.detalles.filter(producto=None, nombre_snapshot="Servicio: Prod. sin registro").exists())
        self.assertEqual(self.salida.call_count, 1)

    def test_servicio_mayor_hace_receptora_a_la_responsable(self):
        data = self.cobrar_ok(
            [self.item_servicio(70), self.item(self.prod_anais, 20)], efectivo=90,
        )
        r = data["reparto_efectivo"]
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["queda_receptora"], 70.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "efectivo": 20.0},
        ])

    def test_producto_sin_duena_queda_sin_cajon(self):
        data = self.cobrar_ok(
            [self.item(self.prod_rosa, 60), self.item(self.prod_sin_dueno, 40)], efectivo=100,
        )
        r = data["reparto_efectivo"]
        # v2: con sin_cajon > 0 el caso es "varias" (antes "una").
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["queda_receptora"], 60.0)
        self.assertEqual(r["sin_cajon"], 40.0)
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "total": 60.0},
            {"empleado_id": None, "nombre": "Sin dueño", "total": 40.0},
        ])
        self.assertCuadra(r)

    def carrito_gelish(self):
        """Gelish $100 (Anais) + tinte $50 (Yareli) + producto $10 (Rosa) = $160."""
        return [
            self.item(self.prod_anais, 100),
            self.item(self.prod_yareli, 50),
            self.item(self.prod_rosa, 10),
        ]

    def test_ejemplo_gelish_70_tarjeta_90_efectivo(self):
        data = self.cobrar_ok(self.carrito_gelish(), efectivo=90, tarjeta=70)
        r = data["reparto_efectivo"]
        # Anais (100) recibe, cobra los 70 en su Clip y pasa Yareli 50 + Rosa 10;
        # le quedan 30 en efectivo (30 + 70 = 100). Nadie debe.
        self.assertEqual(r["version"], 2)
        self.assertEqual(r["caso"], "varias")
        self.assertEqual((r["neto"], r["tarjeta"], r["cambio"]), (90.0, 70.0, 0.0))
        self.assertEqual(r["receptora"], {"empleado_id": self.anais.id, "nombre": "Anais"})
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 70.0})
        self.assertEqual(r["queda_receptora"], 30.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "efectivo": 50.0},
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "efectivo": 10.0},
        ])
        self.assertEqual(r["deudas"], [])
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "total": 100.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "total": 50.0},
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "total": 10.0},
        ])
        self.assertEqual(r["sin_cajon"], 0.0)
        self.assertCuadra(r)

    def test_ejemplo_gelish_todo_con_tarjeta(self):
        data = self.cobrar_ok(self.carrito_gelish(), tarjeta=160)
        r = data["reparto_efectivo"]
        # Los 160 entran al Clip de Anais; no hay efectivo que pasar, así
        # que Anais le debe 50 a Yareli y 10 a Rosa.
        self.assertEqual(r["version"], 2)
        self.assertEqual(r["caso"], "sin_efectivo")
        self.assertEqual((r["neto"], r["tarjeta"]), (0.0, 160.0))
        self.assertEqual(r["receptora"], {"empleado_id": self.anais.id, "nombre": "Anais"})
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 160.0})
        self.assertEqual((r["queda_receptora"], r["pasar"]), (0.0, []))
        self.assertEqual(r["deudas"], [
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "monto": 50.0},
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 10.0},
        ])
        self.assertEqual([p["total"] for p in r["por_duena"]], [100.0, 50.0, 10.0])
        self.assertCuadra(r)

    def test_error_de_validacion_no_trae_reparto(self):
        # Pago insuficiente: la venta no se crea y la respuesta es la de siempre.
        resp = self.cobrar(self.carrito_210(), efectivo=100)
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertEqual(data["status"], "error")
        self.assertNotIn("reparto_efectivo", data)
        self.assertEqual(Venta.objects.count(), 0)


# ----------------------------------------------------------------------
# Idempotencia
# ----------------------------------------------------------------------

class IdempotenciaConRepartoTest(PosRepartoTestCase):

    def test_llave_guarda_reparto_y_reintento_no_duplica(self):
        data = self.cobrar_ok(self.carrito_210(), efectivo=500, key="k-ok")

        idem = IdempotencyKey.objects.get(key="k-ok")
        self.assertEqual(idem.status_code, 200)
        self.assertEqual(idem.response_json, data)
        self.assertIn("reparto_efectivo", idem.response_json)

        resp = self.cobrar(self.carrito_210(), efectivo=500, key="k-ok")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), data)
        self.assertEqual(Venta.objects.count(), 1)

    def assertCobroSinRepartoNoSeDuplica(self, key):
        """La llave se omite, el cobro es ok, la llave idempotente NO se libera."""
        with self.assertLogs("ventas.views.pos_views", level="ERROR") as logs:
            data = self.cobrar_ok(self.carrito_210(), efectivo=500, key=key)
        self.assertTrue(any("reparto_efectivo_venta falló" in m for m in logs.output), logs.output)

        self.assertNotIn("reparto_efectivo", data)
        self.assertEqual(set(data), LLAVES_DE_SIEMPRE)
        self.assertEqual(data["total_venta"], 210.0)
        self.assertEqual(data["cambio"], 290.0)

        idem = IdempotencyKey.objects.get(key=key)
        self.assertEqual(idem.response_json, data)
        self.assertEqual(Venta.objects.count(), 1)

        # La cajera reintenta con la misma llave: misma respuesta, sin otra venta.
        resp = self.cobrar(self.carrito_210(), efectivo=500, key=key)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), data)
        self.assertEqual(Venta.objects.count(), 1)

    def test_reparto_truena(self):
        with mock.patch("ventas.services.reparto.reparto_efectivo_venta", side_effect=RuntimeError("boom")):
            self.assertCobroSinRepartoNoSeDuplica("k-truena")

    def test_reparto_no_serializable(self):
        casos = {
            "decimal": {"x": Decimal("1")},
            "nan": {"x": float("nan")},
            "infinito": {"x": float("inf")},
        }
        for nombre, valor in casos.items():
            with self.subTest(nombre):
                Venta.objects.all().delete()
                with mock.patch("ventas.services.reparto.reparto_efectivo_venta", return_value=valor):
                    self.assertCobroSinRepartoNoSeDuplica(f"k-{nombre}")

    def test_modulo_de_reparto_no_importa(self):
        # Si el import perezoso falla (módulo roto o sin la función), el POS
        # sigue cobrando.
        with mock.patch.dict(reparto_mod.__dict__):
            del reparto_mod.__dict__["reparto_efectivo_venta"]
            self.assertCobroSinRepartoNoSeDuplica("k-import")

    def test_reparto_none_omite_la_llave_sin_log(self):
        with mock.patch("ventas.services.reparto.reparto_efectivo_venta", return_value=None):
            data = self.cobrar_ok(self.carrito_210(), efectivo=500, key="k-none")
        self.assertEqual(set(data), LLAVES_DE_SIEMPRE)
        self.assertEqual(IdempotencyKey.objects.get(key="k-none").response_json, data)

    def test_sin_llave_idempotente_y_reparto_truena(self):
        with mock.patch("ventas.services.reparto.reparto_efectivo_venta", side_effect=RuntimeError):
            with self.assertLogs("ventas.views.pos_views", level="ERROR"):
                data = self.cobrar_ok(self.carrito_210(), efectivo=500)
        self.assertNotIn("reparto_efectivo", data)
        self.assertEqual(Venta.objects.count(), 1)


# ----------------------------------------------------------------------
# Propiedad: el reparto siempre cuadra con el efectivo neto
# ----------------------------------------------------------------------

class RepartoPorEndpointPropiedadTest(PosRepartoTestCase):

    def _total_pos(self, carrito, pct):
        """Misma aritmética float que POSService.crear_venta."""
        subtotal = 0
        for it in carrito:
            subtotal += float(it["precio_aplicado"]) * int(it["cantidad"])
        return subtotal - subtotal * (pct / 100)

    def test_30_ventas_variadas(self):
        rng = random.Random(20261019)
        productos = [self.prod_rosa, self.prod_anais, self.prod_yareli, self.prod_sin_dueno]
        casos_vistos = set()

        for i in range(30):
            carrito = []
            for _ in range(rng.randint(1, 4)):
                precio = round(rng.uniform(0.5, 100), 2)
                cantidad = rng.randint(1, 2)
                if rng.random() < 0.2:
                    carrito.append(self.item_servicio(precio, cantidad=cantidad))
                else:
                    carrito.append(self.item(rng.choice(productos), precio, cantidad))
            pct = rng.choice((0,) + tuple(DESCUENTOS_PERMITIDOS))
            total = self._total_pos(carrito, pct)

            modo = rng.choice(("efectivo", "efectivo", "tarjeta", "mixto"))
            if modo == "tarjeta":
                tarjeta = math.floor(total * 100) / 100
                while tarjeta > total:  # la tarjeta nunca puede pasarse del total float
                    tarjeta = round(tarjeta - 0.01, 2)
                # Lo que falte por el truncado se paga en efectivo.
                efectivo = 0 if tarjeta >= total else 1
            elif modo == "mixto":
                tarjeta = math.floor(total * rng.uniform(0.1, 0.9) * 100) / 100
                efectivo = math.ceil(total - tarjeta) + rng.choice((0, 0, 5, 20))
            else:
                tarjeta = 0
                efectivo = math.ceil(total) + rng.choice((0, 0, 1, 10, 50))

            with self.subTest(i=i, carrito=carrito, pct=pct, efectivo=efectivo, tarjeta=tarjeta):
                data = self.cobrar_ok(carrito, efectivo=efectivo, tarjeta=tarjeta,
                                      descuento_pct=pct, key=f"prop-{i}")
                r = data["reparto_efectivo"]
                venta = Venta.objects.get(pk=data["venta_id"])

                self.assertCuadra(r)
                self.assertEqual(centavos(r["neto"]),
                                 int((venta.pagado_efectivo - venta.cambio) * 100))
                self.assertEqual(centavos(r["tarjeta"]), int(venta.pagado_tarjeta * 100))
                self.assertEqual(r["version"], 2)
                rid = (r["receptora"] or {}).get("empleado_id")
                for p in r["pasar"]:
                    self.assertGreater(p["efectivo"], 0)
                    self.assertNotEqual(p["empleado_id"], rid)
                for d in r["deudas"]:
                    self.assertGreater(d["monto"], 0)
                    self.assertNotEqual(d["empleado_id"], rid)
                if rid is None:
                    # Sin dueñas en la cuenta: nadie cobra en su Clip ni debe.
                    self.assertIsNone(r["clip"])
                    self.assertEqual(r["deudas"], [])
                    if r["neto"] > 0:
                        self.assertEqual(r["caso"], "sin_duena")
                else:
                    # Toda la tarjeta va al Clip de la receptora.
                    if r["tarjeta"] > 0:
                        self.assertEqual(r["clip"], {"empleado_id": rid, "nombre": r["receptora"]["nombre"],
                                                     "monto": r["tarjeta"]})
                    else:
                        self.assertIsNone(r["clip"])
                    self.assertEqual(r["por_duena"][0]["empleado_id"], rid)
                    if r["neto"] == 0:
                        self.assertEqual(r["caso"], "sin_efectivo")
                    elif r["pasar"] or r["sin_cajon"]:
                        self.assertEqual(r["caso"], "varias")
                    else:
                        self.assertEqual(r["caso"], "una")
                # Lo que le toca a cada quien suma el total de la venta.
                self.assertEqual(sum(centavos(p["total"]) for p in r["por_duena"]),
                                 int(venta.total * 100))
                casos_vistos.add(r["caso"])

                # Lo que quedó en la llave idempotente es exactamente lo respondido.
                self.assertEqual(IdempotencyKey.objects.get(key=f"prop-{i}").response_json, data)

        self.assertEqual(Venta.objects.count(), 30)
        self.assertGreaterEqual(len(casos_vistos), 2, casos_vistos)


# ----------------------------------------------------------------------
# Aviso "Cobra $X en el Clip de …" del modal de cobro (antes de cobrar)
# ----------------------------------------------------------------------

class ClipDeLaVentaTest(PosRepartoTestCase):

    def pedir(self, carrito):
        return self.client.post(reverse("ventas:clip_de_la_venta"), data=json.dumps({"carrito": carrito}),
                                content_type="application/json")

    def clip(self, carrito):
        resp = self.pedir(carrito)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["status"], "ok")
        return resp.json()["clip"]

    def test_es_la_que_mas_vende(self):
        self.assertEqual(self.clip(self.carrito_210()), {"empleado_id": self.rosa.id, "nombre": "Rosa"})

    def test_coincide_con_el_clip_de_la_venta_ya_cobrada(self):
        carritos = [
            self.carrito_210(),
            [self.item(self.prod_anais, 50), self.item(self.prod_yareli, 50)],
            [self.item_servicio(100, "Copias"), self.item(self.prod_anais, 60)],
            [self.item(self.prod_yareli, 30, cantidad=3), self.item(self.prod_anais, 80)],
        ]
        for i, carrito in enumerate(carritos):
            with self.subTest(i=i):
                antes = self.clip(carrito)
                total = sum(it["precio_aplicado"] * it["cantidad"] for it in carrito)
                r = self.cobrar_ok(carrito, tarjeta=total, key=f"clip-{i}")["reparto_efectivo"]
                self.assertEqual(antes, {k: r["clip"][k] for k in ("empleado_id", "nombre")})

    def test_empate_por_prioridad(self):
        carrito = [self.item(self.prod_yareli, 50), self.item(self.prod_anais, 50)]
        self.assertEqual(self.clip(carrito)["empleado_id"], self.anais.id)

    def test_servicios_cuentan_para_la_responsable(self):
        carrito = [self.item_servicio(100, "Copias"), self.item(self.prod_anais, 60)]
        self.assertEqual(self.clip(carrito)["empleado_id"], self.rosa.id)

    def test_regalos_no_cuentan(self):
        carrito = [self.item(self.prod_anais, 20),
                   {"es_regalo": True, "producto_id": self.prod_yareli.id, "cantidad": 5, "precio_aplicado": 0}]
        self.assertEqual(self.clip(carrito)["empleado_id"], self.anais.id)

    def test_sin_duenas_no_hay_clip(self):
        self.assertIsNone(self.clip([]))
        self.assertIsNone(self.clip([self.item(self.prod_sin_dueno, 10)]))

    def test_no_guarda_nada(self):
        self.clip(self.carrito_210())
        self.assertEqual(Venta.objects.count(), 0)
        self.salida.assert_not_called()

    def test_carrito_invalido_da_400(self):
        resp = self.pedir([{"producto_id": self.prod_anais.id, "cantidad": "x", "precio_aplicado": 10}])
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["status"], "error")

    def test_solo_post(self):
        self.assertEqual(self.client.get(reverse("ventas:clip_de_la_venta")).status_code, 405)


# ----------------------------------------------------------------------
# Sin stock: mensaje claro con el nombre del producto
# ----------------------------------------------------------------------

class SinStockMensajeClaroTest(PosRepartoTestCase):

    ERROR = ("No hay suficiente inventario en la sucursal Sucursal Centro. "
             "Piso: 0, Bodega: 0, Pedido: 1. Revisar disponibilidad en CEDIS (Moderna).")

    def test_producto_sin_stock_dice_cual(self):
        self.salida.side_effect = ValidationError(self.ERROR)
        resp = self.cobrar([self.item(self.prod_anais, 100)], efectivo=100, key="sin-stock")
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"status": "error", "message": f'"Aretes Anais": {self.ERROR}'})
        # No queda nada a medias y la llave se libera para reintentar.
        self.assertEqual(Venta.objects.count(), 0)
        self.assertFalse(IdempotencyKey.objects.filter(key="sin-stock").exists())

    def test_regalo_sin_stock_dice_que_es_regalo(self):
        # El producto normal sí sale; el regalo (segunda salida) no tiene stock.
        self.salida.side_effect = [None, ValidationError(self.ERROR)]
        regalo = {"es_regalo": True, "producto_id": self.prod_yareli.id, "cantidad": 1,
                  "precio_aplicado": 0, "promo_id": None, "promo_nombre": "2x1"}
        resp = self.cobrar([self.item(self.prod_anais, 100), regalo], efectivo=100)
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()["message"], f'"Pulsera Yareli" (regalo): {self.ERROR}')
        self.assertEqual(Venta.objects.count(), 0)


# ----------------------------------------------------------------------
# Stock de lo vendido en la respuesta (cards al día sin websocket)
# ----------------------------------------------------------------------

class StockTrasLaVentaTest(PosRepartoTestCase):

    def setUp(self):
        super().setUp()
        # Sin Redis en tests: que el post_save de Inventario no intente difundir.
        patcher = mock.patch("inventario.signals._broadcast")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.bodega = Ubicacion.objects.create(nombre="Bodega", direccion="x", sucursal=self.sucursal,
                                               tipo="bodega")
        Inventario.objects.create(producto=self.prod_anais, ubicacion=self.piso, cantidad_actual=4)
        Inventario.objects.create(producto=self.prod_anais, ubicacion=self.bodega, cantidad_actual=7)
        Inventario.objects.create(producto=self.prod_rosa, ubicacion=self.piso, cantidad_actual=1)

    def test_trae_piso_y_bodega_de_lo_vendido(self):
        data = self.cobrar_ok([self.item(self.prod_anais, 10), self.item(self.prod_yareli, 10),
                               self.item_servicio(5)], efectivo=25)
        # Solo productos (no servicios); sin registro → 0. salida_inteligente
        # está mockeada, así que son las cantidades de arriba.
        self.assertEqual(data["stock"], {
            str(self.prod_anais.id): {"piso": 4, "bodega": 7},
            str(self.prod_yareli.id): {"piso": 0, "bodega": 0},
        })

    def test_si_falla_se_omite_y_la_venta_sigue_ok(self):
        with mock.patch("ventas.views.pos_views._stock_por_producto", side_effect=RuntimeError("boom")):
            with self.assertLogs("ventas.views.pos_views", level="ERROR"):
                data = self.cobrar_ok([self.item(self.prod_anais, 10)], efectivo=10, key="stock-falla")
        self.assertNotIn("stock", data)
        self.assertEqual(Venta.objects.count(), 1)
        self.assertEqual(IdempotencyKey.objects.get(key="stock-falla").response_json, data)

    def test_endpoint_de_stock_sigue_igual(self):
        data = self.client.get(reverse("ventas:stock_productos")).json()
        self.assertEqual(data, {
            str(self.prod_anais.id): {"piso": 4, "bodega": 7},
            str(self.prod_rosa.id): {"piso": 1, "bodega": 0},
        })

    def test_regalos_traen_stock_de_bodega(self):
        cat = Categoria.objects.create(nombre="Aretes")
        self.prod_anais.categoria = cat
        self.prod_anais.save(update_fields=["categoria"])
        promo = Promocion.objects.create(nombre="Regalo aretes", tipo_condicion="monto", monto_minimo=100,
                                         tipo_resultado="regalo_variante", categoria_regalo=cat)
        data = self.client.get(reverse("ventas:promocion_productos_regalo", args=[promo.id])).json()
        self.assertEqual([(p["id"], p["stock"], p["stock_bodega"]) for p in data["productos"]],
                         [(self.prod_anais.id, 4, 7)])
