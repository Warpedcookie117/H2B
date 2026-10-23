"""
Tests de ventas/services/reparto.py: la única fuente de verdad del dinero
por dueña. Lo importante son los invariantes EXACTOS (en Decimal): ningún
centavo aparece ni desaparece al repartir una venta o un corte.
"""
import json
import random
from decimal import Decimal

from django.test import override_settings

from inventario.models import Producto
from sucursales.models import Caja, Sucursal
from tienda_temp.models import Empleado
from ventas.models import CorteCaja, Venta, VentaDetalle
from ventas.services.reparto import (
    CENT,
    Grupo,
    desglose_como_dict,
    desglose_por_dueno,
    efectivo_neto,
    grupo_de_renglon,
    reparto_efectivo_venta,
    reparto_venta,
    totales_caja,
    ventas_para_desglose,
)
from ventas.tests.base import D, VentasBaseTestCase, crear_empleado

CERO = Decimal("0.00")


def Df(x):
    """float del JSON → Decimal exacto (los floats vienen de Decimal de 2 decimales)."""
    return Decimal(repr(x)).quantize(CENT)


def suma(filas, campo):
    return sum((f[campo] for f in filas), CERO)


# create_user con el hasher real tarda ~1.4 s por usuario y cada clase crea 4
# en setUpTestData; los passwords aquí no importan.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class RepartoTestCase(VentasBaseTestCase):

    def de_bd(self, venta):
        return ventas_para_desglose(Venta.objects.filter(pk=venta.pk)).get()

    def desglose(self, *ventas):
        return desglose_por_dueno(ventas_para_desglose(Venta.objects.filter(pk__in=[v.pk for v in ventas])))

    def saldos(self, *ventas):
        """{nombre: saldo} del desglose: lo que no le llegó ni a su caja ni a
        su Clip (solo ventas de antes del pago en seco)."""
        return {f["nombre"]: f["saldo"] for f in self.desglose(*ventas)}

    def assert_invariantes(self, venta):
        """
        Invariantes de reparto_venta (regla de la receptora: ella cobra toda
        la tarjeta en su Clip y con el efectivo se completa a las demás) y su
        congruencia con el modal (reparto_efectivo_venta v2).
        """
        v = self.de_bd(venta)
        filas = reparto_venta(v)
        neto = efectivo_neto(v)
        tarjeta = v.pagado_tarjeta
        cuadra = neto + tarjeta == v.total

        # Columnas exactas.
        self.assertEqual(suma(filas, "total"), v.total)
        self.assertEqual(suma(filas, "efectivo"), neto)
        self.assertEqual(suma(filas, "tarjeta"), tarjeta)
        for f in filas:
            self.assertEqual(f["efectivo"] + f["tarjeta"] + f["saldo"], f["total"])
            self.assertGreaterEqual(f["efectivo"], 0)
            self.assertGreaterEqual(f["tarjeta"], 0)
        if cuadra:
            self.assertEqual(suma(filas, "saldo"), CERO)

        r = reparto_efectivo_venta(v.pk)
        self.assertEqual(r["version"], 2)
        self.assertEqual(Df(r["neto"]), neto)
        self.assertEqual(Df(r["tarjeta"]), tarjeta)
        self.assertEqual(
            Df(r["queda_receptora"]) + sum((Df(p["efectivo"]) for p in r["pasar"]), CERO)
            + Df(r["sin_cajon"]),
            neto,
        )

        # Acumulado por caja (dueña) y por especial, como lo ve el modal.
        cajon, especiales = {}, {}
        for f in filas:
            cid = f["grupo"].cajon_id
            acc = cajon.setdefault(cid, {}) if cid is not None else especiales.setdefault(f["grupo"].nombre, {})
            for k in ("total", "efectivo", "tarjeta", "saldo"):
                acc[k] = acc.get(k, CERO) + f[k]
        self.assertEqual(Df(r["sin_cajon"]), sum((e["efectivo"] for e in especiales.values()), CERO))

        if not cajon:
            if neto > 0:  # con neto 0 hoy también sale "sin_duena" (dudoso, reportado)
                self.assertEqual(r["caso"], "sin_duena")
            self.assertIsNone(r["receptora"])
            self.assertIsNone(r["clip"])
            self.assertEqual((r["pasar"], r["queda_receptora"]), ([], 0.0))
            return filas, r

        rid = r["receptora"]["empleado_id"]
        self.assertIn(rid, cajon)
        for f in filas:
            if f["grupo"].cajon_id != rid:
                # Solo el Clip de la receptora cobra; a las demás se les debe o se les pagó.
                self.assertEqual(f["tarjeta"], CERO, f)
                self.assertGreaterEqual(f["saldo"], CERO, f)
        rec = cajon[rid]
        if neto + tarjeta >= v.total:
            # Por dueña, no por fila: si la receptora tiene 2+ filas (producto +
            # servicio), efectivo y tarjeta se redondean por separado y una
            # fila puede quedar con saldo +0.01 (reportado como posible bug).
            self.assertLessEqual(rec["saldo"], CERO)
        if any(c["saldo"] > 0 for cid, c in cajon.items() if cid != rid) or \
                any(e["saldo"] > 0 for e in especiales.values()):
            self.assertEqual(rec["efectivo"], CERO)  # con saldo, todo el efectivo se pasó

        # Modal congruente con las filas.
        self.assertEqual(Df(r["queda_receptora"]), rec["efectivo"])
        self.assertEqual({p["empleado_id"]: Df(p["efectivo"]) for p in r["pasar"]},
                         {cid: c["efectivo"] for cid, c in cajon.items() if cid != rid and c["efectivo"] > 0})
        self.assertNotIn("deudas", r)
        if tarjeta > 0:
            self.assertEqual(r["clip"], {"empleado_id": rid, "nombre": r["receptora"]["nombre"],
                                         "monto": float(tarjeta)})
        else:
            self.assertIsNone(r["clip"])
        ids = [p["empleado_id"] for p in r["por_duena"]]
        self.assertEqual(ids[0], rid)
        self.assertEqual(ids[:len(cajon)], [i for i in ids if i is not None])  # especiales al final
        self.assertEqual({p["empleado_id"]: Df(p["total"]) for p in r["por_duena"] if p["empleado_id"]},
                         {cid: c["total"] for cid, c in cajon.items()})
        self.assertEqual({p["nombre"]: Df(p["total"]) for p in r["por_duena"] if p["empleado_id"] is None},
                         {n: e["total"] for n, e in especiales.items()})
        if neto == 0:
            self.assertEqual(r["caso"], "sin_efectivo")
        elif r["pasar"] or r["sin_cajon"]:
            self.assertEqual(r["caso"], "varias")
        else:
            self.assertEqual(r["caso"], "una")
        return filas, r

    def por_nombre(self, filas):
        return {f["grupo"].nombre: f for f in filas}


# ---------------------------------------------------------------------------
# reparto_efectivo_venta: los casos del modal
# ---------------------------------------------------------------------------

class RepartoEfectivoCasosTest(RepartoTestCase):

    def test_ejemplo_del_dueno_210_pagado_con_500(self):
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60),
             self.renglon(self.prod_yareli, 10)],
            efectivo=500,
        )
        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["version"], 2)
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["receptora"], {"empleado_id": self.rosa.id, "nombre": "Rosa"})
        self.assertEqual(r["recibido"], 500.0)
        self.assertEqual(r["cambio"], 290.0)
        self.assertEqual(r["neto"], 210.0)
        self.assertEqual(r["tarjeta"], 0.0)
        self.assertEqual(r["queda_receptora"], 140.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "efectivo": 60.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "efectivo": 10.0},
        ])
        self.assertEqual(r["sin_cajon"], 0.0)
        # Sin tarjeta no hay Clip, y el efectivo alcanzó para todas: nadie debe.
        self.assertIsNone(r["clip"])
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "total": 140.0},
            {"empleado_id": self.anais.id, "nombre": "Anais", "total": 60.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "total": 10.0},
        ])
        filas, _ = self.assert_invariantes(v)
        self.assertEqual({f["grupo"].nombre: f["saldo"] for f in filas},
                         {"Rosa": CERO, "Anais": CERO, "Yareli": CERO})

    def test_una_sola_duena(self):
        v = self.crear_venta([self.renglon(self.prod_anais, 100, cantidad=2)], efectivo=200)
        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["caso"], "una")
        self.assertEqual(r["receptora"], {"empleado_id": self.anais.id, "nombre": "Anais"})
        self.assertEqual(r["queda_receptora"], 100.0)
        self.assertEqual(r["cambio"], 100.0)
        self.assertEqual(r["pasar"], [])
        self.assertEqual(r["sin_cajon"], 0.0)

    def test_solo_tarjeta_es_sin_efectivo(self):
        # Regla nueva: aunque no haya efectivo, la receptora (Rosa, 140) cobra
        # los 200 en SU Clip y le queda debiendo sus 60 a Anais.
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60)], tarjeta=200
        )
        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["caso"], "sin_efectivo")
        self.assertEqual(r["receptora"], {"empleado_id": self.rosa.id, "nombre": "Rosa"})
        self.assertEqual(r["clip"], {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 200.0})
        self.assertEqual(r["queda_receptora"], 0.0)
        self.assertEqual(r["pasar"], [])
        self.assertEqual(r["sin_cajon"], 0.0)
        self.assertEqual(r["neto"], 0.0)
        self.assertEqual(r["tarjeta"], 200.0)
        filas, _ = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        self.assertEqual((fx["Rosa"]["tarjeta"], fx["Rosa"]["saldo"]), (D(200), D(-60)))
        self.assertEqual((fx["Anais"]["tarjeta"], fx["Anais"]["saldo"]), (CERO, D(60)))

    def test_venta_solo_regalos_no_truena(self):
        v = self.crear_venta([self.regalo(self.prod_rosa), self.regalo(self.prod_anais, cantidad=2)])
        self.assertEqual(v.total, CERO)
        self.assertEqual(reparto_venta(self.de_bd(v)), [])
        r = reparto_efectivo_venta(v.id)
        self.assertEqual((r["neto"], r["tarjeta"], r["sin_cajon"]), (0.0, 0.0, 0.0))
        self.assertIsNone(r["receptora"])
        self.assertIsNone(r["clip"])
        self.assertEqual((r["pasar"], r["por_duena"]), ([], []))
        self.assertEqual(self.desglose(v), [])
        # El "caso" de una venta sin dueñas con neto 0 NO se fija aquí: hoy sale
        # "sin_duena" (antes "sin_efectivo"); reportado como posible bug.

    def test_regalos_no_cuentan_en_la_base(self):
        v = self.crear_venta(
            [self.renglon(self.prod_anais, 100), self.regalo(self.prod_rosa)], efectivo=100
        )
        filas, r = self.assert_invariantes(v)
        self.assertEqual([f["grupo"].nombre for f in filas], ["Anais"])
        self.assertEqual(r["caso"], "una")
        regalo = v.detalles.get(atributos_snapshot__tipo="regalo")
        self.assertIsNone(grupo_de_renglon(regalo, v))

    def test_mixto(self):
        # 210 = 100 tarjeta + 110 efectivo (pagó 200, cambio 90)
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60),
             self.renglon(self.prod_yareli, 10)],
            efectivo=200, tarjeta=100,
        )
        self.assertEqual(v.cambio, D(90))
        filas, r = self.assert_invariantes(v)
        self.assertEqual(suma(filas, "efectivo"), D(110))
        self.assertEqual(suma(filas, "tarjeta"), D(100))
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["neto"], 110.0)
        # Los 100 de tarjeta van al Clip de Rosa; de los 110 en efectivo se
        # completa Anais 60 + Yareli 10 y a Rosa le quedan 40 (40 + 100 = 140).
        self.assertEqual(r["clip"], {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 100.0})
        self.assertEqual(r["queda_receptora"], 40.0)
        self.assertEqual([p["efectivo"] for p in r["pasar"]], [60.0, 10.0])

    def test_inexistente_devuelve_none(self):
        self.assertIsNone(reparto_efectivo_venta(999999))

    def test_json_serializable_y_floats(self):
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 33.33), self.renglon(self.prod_anais, 20.01),
             self.servicio("Copias", 5.5), self.renglon(self.prod_sin_dueno, 7.77)],
            efectivo=60, tarjeta=10, descuento_pct=5,
        )
        r = reparto_efectivo_venta(v.id)
        json.dumps(r)
        for k in ("recibido", "cambio", "neto", "tarjeta", "queda_receptora", "sin_cajon"):
            self.assertIs(type(r[k]), float, k)
        self.assertIs(type(r["receptora"]["empleado_id"]), int)
        self.assertTrue(r["pasar"])
        for p in r["pasar"]:
            self.assertIs(type(p["efectivo"]), float)
            self.assertIs(type(p["empleado_id"]), int)
        self.assertIs(type(r["clip"]["monto"]), float)
        self.assertIs(type(r["clip"]["empleado_id"]), int)
        for p in r["por_duena"]:
            self.assertIs(type(p["total"]), float)
        self.assert_invariantes(v)
        # Los casos sin receptora también son JSON puro.
        v2 = self.crear_venta([self.renglon(self.prod_sin_dueno, 10)], efectivo=10)
        r2 = reparto_efectivo_venta(v2.id)
        json.dumps(r2)
        self.assertIs(type(r2["sin_cajon"]), float)

    def test_dos_queries(self):
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 20),
             self.servicio("Copias", 5), self.regalo(self.prod_yareli),
             self.renglon(self.prod_sin_dueno, 3)],
            efectivo=100,
        )
        with self.assertNumQueries(2):
            reparto_efectivo_venta(v.id)


# ---------------------------------------------------------------------------
# Aritmética: descuentos, ofertas, mayor residuo
# ---------------------------------------------------------------------------

class RepartoAritmeticaTest(RepartoTestCase):

    def test_descuento_10(self):
        v = self.crear_venta(
            [self.renglon(self.prod_anais, 600), self.renglon(self.prod_yareli, 400)],
            efectivo=900, descuento_pct=10,
        )
        filas, _ = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        self.assertEqual(fx["Anais"]["total"], D(540))
        self.assertEqual(fx["Yareli"]["total"], D(360))
        self.assertEqual(fx["Anais"]["base"], D(600))
        dd = desglose_como_dict(self.desglose(v))
        self.assertEqual(dd["Anais"]["total"], D(540))
        self.assertEqual(dd["Anais"]["efectivo"], D(540))
        self.assertEqual(dd["Yareli"]["total"], D(360))
        self.assertEqual(dd["Yareli"]["productos"], D(360))

    def test_subtotal_forzado_por_oferta(self):
        # Renglones suman 66.68 pero la venta se cobró 66.67 (oferta nxprecio).
        v = self.crear_venta(
            [self.renglon(self.prod_anais, 33.34), self.renglon(self.prod_yareli, 33.34)],
            efectivo=100, subtotal=66.67,
        )
        self.assertEqual(v.total, D(66.67))
        filas, _ = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        # Empate exacto: el centavo extra va por prioridad (Anais 2 < Yareli 3).
        self.assertEqual(fx["Anais"]["total"], D(33.34))
        self.assertEqual(fx["Yareli"]["total"], D(33.33))
        v2 = self.crear_venta(
            [self.renglon(self.prod_anais, 33.34), self.renglon(self.prod_yareli, 33.34)],
            efectivo=50, tarjeta=20, subtotal=66.67, descuento_pct=15,
        )
        self.assert_invariantes(v2)

    def test_mayor_residuo_centavo_extra_a_prioridad_1(self):
        # 3 x $10 por $10: cada dueña aporta 1/3.
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
             self.renglon(self.prod_yareli, 10)],
            efectivo=10, subtotal=10,
        )
        filas, r = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        self.assertEqual([fx[n]["efectivo"] for n in ("Rosa", "Anais", "Yareli")],
                         [D(3.34), D(3.33), D(3.33)])
        self.assertEqual(suma(filas, "efectivo"), D(10))
        self.assertEqual(r["queda_receptora"], 3.34)

    def test_mayor_residuo_mixto_cada_fila_cuadra(self):
        # 30 = 19.99 tarjeta + 10.01 efectivo, $10 c/u. Rosa (prioridad 1) es
        # receptora: los 19.99 van a su Clip. Anais+Yareli necesitan 20 y solo
        # hay 10.01 → se reparte 50/50 = 5.005 c/u; el centavo sobrante va a
        # Anais (prioridad 2). Rosa no recibe efectivo y queda debiendo.
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
             self.renglon(self.prod_yareli, 10)],
            efectivo=10.01, tarjeta=19.99,
        )
        filas, r = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        self.assertEqual([fx[n]["efectivo"] for n in ("Rosa", "Anais", "Yareli")],
                         [CERO, D(5.01), D(5.00)])
        self.assertEqual([fx[n]["tarjeta"] for n in ("Rosa", "Anais", "Yareli")],
                         [D(19.99), CERO, CERO])
        # Saldos: Rosa 10 - 19.99 = -9.99; Anais 10 - 5.01; Yareli 10 - 5. Σ = 0.
        self.assertEqual([fx[n]["saldo"] for n in ("Rosa", "Anais", "Yareli")],
                         [D(-9.99), D(4.99), D(5.00)])
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["queda_receptora"], 0.0)
        self.assertEqual([p["efectivo"] for p in r["pasar"]], [5.01, 5.0])

    def test_venta_que_no_cuadra_por_floats(self):
        # neto + tarjeta = total + 0.01 (cambio mal redondeado por floats del
        # POS): las columnas se reparten por separado y aun así suman exacto.
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
             self.renglon(self.prod_yareli, 10.01)],
            efectivo=10, tarjeta=20.02,
        )
        Venta.objects.filter(pk=v.pk).update(cambio=CERO)
        v.refresh_from_db()
        self.assertNotEqual(efectivo_neto(v) + v.pagado_tarjeta, v.total)
        filas, r = self.assert_invariantes(v)
        self.assertEqual(suma(filas, "efectivo"), D(10))
        self.assertEqual(suma(filas, "tarjeta"), D(20.02))
        self.assertEqual(suma(filas, "total"), D(30.01))

    def test_efectivo_neto_acepta_floats_en_memoria(self):
        # Así queda el objeto tras POSService.crear_venta (sin refresh_from_db).
        v = Venta(pagado_efectivo=100.0, cambio=33.33, pagado_tarjeta=0.0, total=66.67)
        self.assertEqual(efectivo_neto(v), D(66.67))
        self.assertEqual(efectivo_neto(Venta(pagado_efectivo=0, cambio=0)), CERO)


# ---------------------------------------------------------------------------
# Receptora y desempates
# ---------------------------------------------------------------------------

class RepartoReceptoraTest(RepartoTestCase):

    def receptora(self, a, b):
        v = self.crear_venta([self.renglon(a, 100), self.renglon(b, 100)], efectivo=200)
        return reparto_efectivo_venta(v.id)["receptora"]["empleado_id"]

    def test_empate_por_prioridad(self):
        self.assertEqual(self.receptora(self.prod_anais, self.prod_yareli), self.anais.id)
        self.assertEqual(self.receptora(self.prod_yareli, self.prod_anais), self.anais.id)
        self.assertEqual(self.receptora(self.prod_anais, self.prod_rosa), self.rosa.id)

    def test_sin_prioridades_es_alfabetico(self):
        Empleado.objects.update(prioridad_cambio=None)
        self.assertEqual(self.receptora(self.prod_rosa, self.prod_anais), self.anais.id)
        self.assertEqual(self.receptora(self.prod_yareli, self.prod_rosa), self.rosa.id)

    def test_vacio_va_despues_de_las_numeradas(self):
        Empleado.objects.filter(pk=self.rosa.pk).update(prioridad_cambio=None)
        self.assertEqual(self.receptora(self.prod_rosa, self.prod_yareli), self.yareli.id)

    def test_receptora_por_base_no_por_efectivo(self):
        # Rosa vende más (60 + 60 de servicios vs 100 de Anais) aunque Anais
        # tenga la fila más grande: Rosa es la receptora, cobra los 219.99 en
        # su Clip y le pasa a Anais el único centavo de efectivo (venta de
        # antes del pago en seco: a Anais le quedan 99.99 de saldo).
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 60), self.servicio("Copias", 60),
             self.renglon(self.prod_anais, 100)],
            efectivo=0.01, tarjeta=219.99,
        )
        filas, r = self.assert_invariantes(v)
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["queda_receptora"], 0.0)
        self.assertEqual(r["pasar"], [{"empleado_id": self.anais.id, "nombre": "Anais", "efectivo": 0.01}])
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["clip"], {"empleado_id": self.rosa.id, "nombre": "Rosa", "monto": 219.99})
        self.assertEqual(self.por_nombre(filas)["Anais"]["saldo"], D(99.99))
        # Las 2 filas de Rosa se reparten la tarjeta 50/50 (21999 c / 2): el
        # centavo extra a la de producto (va antes que "servicio" en el orden).
        rosa = sorted((f for f in filas if f["grupo"].cajon_id == self.rosa.id), key=lambda f: f["grupo"].tipo)
        self.assertEqual([f["tarjeta"] for f in rosa], [D(110.00), D(109.99)])


# ---------------------------------------------------------------------------
# Servicios y grupos especiales
# ---------------------------------------------------------------------------

class RepartoServiciosEspecialesTest(RepartoTestCase):

    def test_servicio_con_responsable(self):
        v = self.crear_venta(
            [self.servicio("Prod. sin registro", 50), self.servicio("Prod. sin registro", 50),
             self.servicio("Copias", 30), self.renglon(self.prod_anais, 100)],
            efectivo=500,
        )
        filas = self.desglose(v)
        self.assertEqual([f["nombre"] for f in filas], ["Anais", "Rosa"])
        rosa = desglose_como_dict(filas)["Rosa"]
        self.assertEqual(rosa["empleado_id"], self.rosa.id)
        self.assertFalse(rosa["especial"])
        self.assertEqual(rosa["productos"], CERO)
        self.assertEqual(rosa["total"], D(130))
        self.assertEqual(rosa["servicios"]["total"], D(130))
        self.assertEqual(rosa["servicios"]["efectivo"], D(130))
        self.assertEqual(rosa["servicios"]["tarjeta"], CERO)
        self.assertEqual(rosa["servicios"]["conceptos"], [
            {"concepto": "Prod. sin registro", "cantidad": 2, "total": D(100),
             "pago_efectivo": D(100), "pago_tarjeta": CERO},
            {"concepto": "Copias", "cantidad": 1, "total": D(30),
             "pago_efectivo": D(30), "pago_tarjeta": CERO},
        ])
        anais = desglose_como_dict(filas)["Anais"]
        self.assertEqual(anais["productos"], D(100))
        self.assertIsNone(anais["servicios"])

        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["queda_receptora"], 130.0)
        self.assertEqual(r["pasar"], [{"empleado_id": self.anais.id, "nombre": "Anais", "efectivo": 100.0}])
        self.assertEqual(r["sin_cajon"], 0.0)

        servicio = v.detalles.filter(producto__isnull=True).first()
        self.assertEqual(grupo_de_renglon(servicio, v),
                         Grupo(("empleado", self.rosa.id), "Rosa", self.rosa.id, "servicio"))

    def test_servicios_y_productos_de_la_responsable_en_su_fila(self):
        v = self.crear_venta(
            [self.servicio("Copias", 30), self.renglon(self.prod_rosa, 70)], efectivo=100
        )
        filas, r = self.assert_invariantes(v)
        self.assertEqual({(f["grupo"].tipo, f["concepto"]) for f in filas},
                         {("producto", None), ("servicio", "Copias")})
        rosa = desglose_como_dict(self.desglose(v))["Rosa"]
        self.assertEqual((rosa["total"], rosa["productos"], rosa["servicios"]["total"]),
                         (D(100), D(70), D(30)))
        self.assertEqual(r["caso"], "una")
        self.assertEqual(r["queda_receptora"], 100.0)

    def test_concepto_sin_prefijo_y_vacio(self):
        v = self.crear_venta(
            [self.servicio("x", 10), self.servicio("y", 20), self.servicio("z", 30)], efectivo=60
        )
        nombres = iter(["SERVICIO:Copias", "Engargolado", "Servicio: "])
        for d in v.detalles.order_by("pk"):
            VentaDetalle.objects.filter(pk=d.pk).update(nombre_snapshot=next(nombres))
        conceptos = {f["concepto"]: f["total"] for f in reparto_venta(self.de_bd(v))}
        self.assertEqual(conceptos, {"Copias": D(10), "Engargolado": D(20), "Servicio": D(30)})

    def test_servicio_sin_responsable(self):
        Sucursal.objects.filter(pk=self.sucursal.pk).update(dueño_servicios=None)
        v = self.crear_venta(
            [self.servicio("Copias", 30), self.renglon(self.prod_anais, 70)], efectivo=100
        )
        filas = self.desglose(v)
        self.assertEqual([f["nombre"] for f in filas], ["Anais", "Servicios (sin responsable)"])
        esp = filas[1]
        self.assertTrue(esp["especial"])
        self.assertIsNone(esp["empleado_id"])
        self.assertEqual(esp["clave"], ("servicios_sin_responsable",))
        self.assertEqual(esp["productos"], CERO)
        self.assertEqual(esp["servicios"]["total"], D(30))
        self.assertEqual(esp["servicios"]["conceptos"], [{"concepto": "Copias", "cantidad": 1, "total": D(30),
                                                          "pago_efectivo": D(30), "pago_tarjeta": CERO}])

        _, r = self.assert_invariantes(v)
        # v2: hay sin_cajon > 0 (30 de servicios sin responsable) → "varias".
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["receptora"]["empleado_id"], self.anais.id)
        self.assertEqual(r["queda_receptora"], 70.0)
        self.assertEqual(r["sin_cajon"], 30.0)
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "total": 70.0},
            {"empleado_id": None, "nombre": "Servicios (sin responsable)", "total": 30.0},
        ])

        solo = self.crear_venta([self.servicio("Copias", 30)], efectivo=50)
        r = reparto_efectivo_venta(solo.id)
        self.assertEqual(r["caso"], "sin_duena")
        self.assertIsNone(r["receptora"])
        self.assertEqual((r["queda_receptora"], r["pasar"], r["sin_cajon"]), (0.0, [], 30.0))

    def test_servicios_dicen_como_se_pagaron(self):
        # Corte con 3 cuentas: una en efectivo, una con tarjeta y una mixta.
        # Por concepto sale cómo PAGÓ el cliente (proporcional a esa venta),
        # aunque la tarjeta haya entrado al Clip de otra dueña.
        efectivo = self.crear_venta([self.servicio("Copias", 30)], efectivo=50)
        tarjeta = self.crear_venta([self.servicio("Copias", 20), self.renglon(self.prod_anais, 200)],
                                   tarjeta=220)
        mixta = self.crear_venta([self.servicio("Vinil", 50), self.renglon(self.prod_anais, 50)],
                                 efectivo=40, tarjeta=60)
        serv = desglose_como_dict(self.desglose(efectivo, tarjeta, mixta))["Rosa"]["servicios"]
        por_concepto = {c["concepto"]: (c["total"], c["pago_efectivo"], c["pago_tarjeta"])
                        for c in serv["conceptos"]}
        self.assertEqual(por_concepto, {
            "Copias": (D(50), D(30), D(20)),   # 30 en efectivo + 20 de la cuenta con tarjeta
            "Vinil": (D(50), D(20), D(30)),    # la cuenta se pagó 40% efectivo / 60% tarjeta
        })
        self.assertEqual((serv["pago_efectivo"], serv["pago_tarjeta"]), (D(50), D(50)))
        for c in serv["conceptos"]:
            self.assertEqual(c["pago_efectivo"] + c["pago_tarjeta"], c["total"])

    def test_servicio_de_venta_sin_caja(self):
        v = self.crear_venta([self.servicio("Copias", 30)], efectivo=30)
        Venta.objects.filter(pk=v.pk).update(caja=None)
        filas = reparto_venta(self.de_bd(v))
        self.assertEqual(filas[0]["grupo"].clave, ("servicios_sin_responsable",))

    def test_producto_sin_dueno(self):
        v = self.crear_venta(
            [self.renglon(self.prod_sin_dueno, 50), self.renglon(self.prod_rosa, 50)], efectivo=100
        )
        filas = self.desglose(v)
        self.assertEqual([f["nombre"] for f in filas], ["Rosa", "Sin dueño"])
        self.assertTrue(filas[1]["especial"])
        self.assertEqual(filas[1]["clave"], ("sin_dueno", "Sin dueño"))
        self.assertEqual(filas[1]["total"], D(50))
        _, r = self.assert_invariantes(v)
        # Empate de base con la especial: la receptora siempre es un cajón.
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        # v2: hay sin_cajon > 0 → "varias".
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["sin_cajon"], 50.0)

    def test_producto_borrado_usa_snapshot(self):
        borrable = Producto.objects.create(nombre="Llavero", precio_mayoreo=1, precio_menudeo=1,
                                           dueño=self.anais)
        v = self.crear_venta([self.renglon(borrable, 25), self.renglon(self.prod_anais, 75)],
                             efectivo=100)
        borrable.delete()
        filas = self.desglose(v)
        self.assertEqual([f["nombre"] for f in filas], ["Anais", "Llavero"])
        self.assertEqual(filas[1]["clave"], ("sin_dueno", "Llavero"))
        _, r = self.assert_invariantes(v)
        self.assertEqual(r["sin_cajon"], 25.0)

    def test_base_cero_con_dinero_es_sin_asignar(self):
        v = self.crear_venta([self.renglon(self.prod_rosa, 0)], efectivo=50, subtotal=50)
        filas, r = self.assert_invariantes(v)
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["grupo"], Grupo(("sin_asignar",), "Sin asignar", None, "especial"))
        self.assertIsNone(filas[0]["concepto"])
        self.assertEqual(filas[0]["base"], CERO)
        self.assertEqual((filas[0]["total"], filas[0]["efectivo"], filas[0]["tarjeta"]),
                         (D(50), D(50), CERO))
        self.assertEqual(r["caso"], "sin_duena")
        self.assertEqual(r["sin_cajon"], 50.0)
        self.assertEqual([f["nombre"] for f in self.desglose(v)], ["Sin asignar"])

    def test_dos_duenas_con_el_mismo_nombre(self):
        otra = crear_empleado("anais_g", "Anais")
        prod_otra = Producto.objects.create(nombre="Collar", precio_mayoreo=1, precio_menudeo=1,
                                            dueño=otra)
        v = self.crear_venta(
            [self.renglon(self.prod_anais, 60), self.renglon(prod_otra, 40),
             self.renglon(self.prod_rosa, 10)],
            efectivo=110,
        )
        filas = self.desglose(v)
        self.assertEqual([f["nombre"] for f in filas], ["Anais (anais)", "Anais (anais_g)", "Rosa"])
        self.assertEqual(filas[0]["clave"], ("empleado", self.anais.id))
        self.assertEqual(filas[1]["clave"], ("empleado", otra.id))
        self.assertEqual(len(desglose_como_dict(filas)), 3)
        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["receptora"]["nombre"], "Anais (anais)")
        self.assertEqual([p["nombre"] for p in r["pasar"]], ["Anais (anais_g)", "Rosa"])

    def test_especial_que_se_llama_como_una_duena_no_se_pierde(self):
        borrable = Producto.objects.create(nombre="Rosa", precio_mayoreo=1, precio_menudeo=1)
        v = self.crear_venta([self.renglon(borrable, 5), self.renglon(self.prod_rosa, 10)], efectivo=15)
        borrable.delete()
        dd = desglose_como_dict(self.desglose(v))
        self.assertEqual(list(dd), ["Rosa", "Rosa (2)"])
        self.assertEqual(sum((f["total"] for f in dd.values()), CERO), D(15))


# ---------------------------------------------------------------------------
# Desglose de varias ventas / totales de caja
# ---------------------------------------------------------------------------

class DesgloseConjuntoTest(RepartoTestCase):

    def ventas_variadas(self):
        return [
            self.crear_venta([self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60),
                              self.renglon(self.prod_yareli, 10)], efectivo=500),
            self.crear_venta([self.renglon(self.prod_anais, 600), self.renglon(self.prod_yareli, 400)],
                             tarjeta=300, efectivo=700, descuento_pct=10),
            self.crear_venta([self.servicio("Copias", 12.5), self.renglon(self.prod_sin_dueno, 9.99),
                              self.regalo(self.prod_rosa)], tarjeta=22.49),
            self.crear_venta([self.renglon(self.prod_anais, 33.34), self.renglon(self.prod_rosa, 33.34)],
                             efectivo=70, subtotal=66.67, descuento_pct=15),
            self.crear_venta([self.regalo(self.prod_yareli)]),
        ]

    def assert_cuadra(self, filas, totales):
        for campo in ("total", "efectivo", "tarjeta"):
            self.assertEqual(suma(filas, campo), totales[campo], campo)

    def test_dos_queries_y_cuadra_con_totales_caja(self):
        ventas = self.ventas_variadas()
        qs = Venta.objects.filter(pk__in=[v.pk for v in ventas])
        with self.assertNumQueries(2):
            filas = desglose_por_dueno(ventas_para_desglose(qs))
        totales = totales_caja(qs)
        self.assertEqual(totales["num_ventas"], 5)
        self.assert_cuadra(filas, totales)
        self.assertEqual([f["nombre"] for f in filas],
                         ["Anais", "Rosa", "Yareli", "Sin dueño"])
        for f in filas:
            serv = f["servicios"]["total"] if f["servicios"] else CERO
            self.assertEqual(f["productos"] + serv, f["total"])
            # v2: ya no efectivo + tarjeta == total por fila; el saldo cierra.
            self.assertEqual(f["efectivo"] + f["tarjeta"] + f["saldo"], f["total"])
        # Todas las ventas cuadran → nadie le debe a nadie en el neto.
        self.assertEqual(suma(filas, "saldo"), CERO)

    def test_con_m2m_de_corte(self):
        ventas = self.ventas_variadas()
        corte = CorteCaja.objects.create(caja=self.caja_anais, caja_nombre="Caja Anais",
                                         total_general=0, total_por_dueno={})
        corte.ventas.set(ventas)
        totales = totales_caja(corte.ventas.all())
        self.assertEqual(totales, totales_caja(Venta.objects.filter(pk__in=[v.pk for v in ventas])))
        with self.assertNumQueries(2):
            filas = desglose_por_dueno(ventas_para_desglose(corte.ventas.all()))
        self.assert_cuadra(filas, totales)

    def test_totales_caja_vacio(self):
        self.assertEqual(totales_caja(Venta.objects.none()),
                         {"efectivo": CERO, "tarjeta": CERO, "total": CERO, "num_ventas": 0})

    def test_totales_caja_un_solo_query(self):
        self.ventas_variadas()
        with self.assertNumQueries(1):
            t = totales_caja(Venta.objects.all())
        self.assertIsInstance(t["efectivo"], Decimal)
        self.assertEqual(t["efectivo"], D(210) + D(600) + D(0) + D(56.67))


# ---------------------------------------------------------------------------
# Regla del Clip: ejemplos reales del dueño
# ---------------------------------------------------------------------------

class RepartoClipEjemplosTest(RepartoTestCase):
    """
    La que más vendió en la cuenta (receptora) recibe el billete, da el
    cambio y cobra TODA la tarjeta en SU Clip; con el efectivo se completa lo
    de las demás. Estas son ventas de antes del pago en seco: si el efectivo
    no alcanzaba, a las demás les quedaba saldo (ver PagoEnSecoTest).
    """

    def gelish_tinte_producto(self, **pago):
        # Gelish $100 (Anais) + tinte $50 (Yareli) + producto $10 (Rosa) = $160.
        return self.crear_venta(
            [self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
             self.renglon(self.prod_rosa, 10)],
            **pago,
        )

    def test_a_mixto_70_tarjeta_90_efectivo(self):
        v = self.gelish_tinte_producto(tarjeta=70, efectivo=90)
        filas, r = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        # Anais (100) es receptora: los 70 van a su Clip; de los 90 en
        # efectivo salen Yareli 50 y Rosa 10, y a Anais le quedan 30 (30+70=100).
        self.assertEqual(r["receptora"], {"empleado_id": self.anais.id, "nombre": "Anais"})
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 70.0})
        self.assertEqual({n: fx[n]["efectivo"] for n in fx}, {"Anais": D(30), "Yareli": D(50), "Rosa": D(10)})
        self.assertEqual({n: fx[n]["tarjeta"] for n in fx}, {"Anais": D(70), "Yareli": CERO, "Rosa": CERO})
        self.assertEqual({n: fx[n]["saldo"] for n in fx}, {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})
        self.assertEqual(r["caso"], "varias")
        self.assertEqual(r["queda_receptora"], 30.0)
        self.assertEqual(r["pasar"], [
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "efectivo": 50.0},
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "efectivo": 10.0},
        ])
        self.assertEqual(r["por_duena"], [
            {"empleado_id": self.anais.id, "nombre": "Anais", "total": 100.0},
            {"empleado_id": self.yareli.id, "nombre": "Yareli", "total": 50.0},
            {"empleado_id": self.rosa.id, "nombre": "Rosa", "total": 10.0},
        ])

    def test_b_todo_con_tarjeta_160(self):
        v = self.gelish_tinte_producto(tarjeta=160)
        filas, r = self.assert_invariantes(v)
        fx = self.por_nombre(filas)
        # Los 160 entran al Clip de Anais y no hay efectivo que repartir:
        # a Yareli (50) y a Rosa (10) les queda saldo (Anais 100-160).
        self.assertEqual(r["caso"], "sin_efectivo")
        self.assertEqual(r["receptora"], {"empleado_id": self.anais.id, "nombre": "Anais"})
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 160.0})
        self.assertEqual({n: fx[n]["efectivo"] for n in fx}, {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})
        self.assertEqual({n: fx[n]["saldo"] for n in fx}, {"Anais": D(-60), "Yareli": D(50), "Rosa": D(10)})
        self.assertEqual((r["queda_receptora"], r["pasar"]), (0.0, []))
        self.assertEqual(self.saldos(v), {"Anais": D(-60), "Yareli": D(50), "Rosa": D(10)})

    def test_c_empate_150_efectivo_170_tarjeta(self):
        # $320 a partes iguales ($160 c/u). Empate de base: gana la prioridad.
        for prod_a, prod_b, gana, otra in (
            (self.prod_anais, self.prod_yareli, self.anais, self.yareli),  # prioridad 2 vs 3
            (self.prod_anais, self.prod_rosa, self.rosa, self.anais),      # prioridad 1 vs 2
        ):
            with self.subTest(gana=gana.user.first_name):
                v = self.crear_venta([self.renglon(prod_a, 160), self.renglon(prod_b, 160)],
                                     efectivo=150, tarjeta=170)
                filas, r = self.assert_invariantes(v)
                fx = {f["grupo"].cajon_id: f for f in filas}
                # La receptora cobra 170 en su Clip; a la otra le tocan 160
                # pero solo hay 150 en efectivo, le quedan 10 de saldo.
                # Receptora: 160 - 0 - 170 = -10.
                self.assertEqual(r["receptora"]["empleado_id"], gana.id)
                self.assertEqual(r["clip"]["monto"], 170.0)
                self.assertEqual(r["clip"]["empleado_id"], gana.id)
                self.assertEqual((fx[gana.id]["efectivo"], fx[gana.id]["saldo"]), (CERO, D(-10)))
                self.assertEqual((fx[otra.id]["efectivo"], fx[otra.id]["saldo"]), (D(150), D(10)))
                self.assertEqual(r["queda_receptora"], 0.0)
                self.assertEqual(r["pasar"], [{"empleado_id": otra.id, "nombre": otra.user.first_name,
                                               "efectivo": 150.0}])
                self.assertEqual(r["caso"], "varias")

    def test_d_con_cambio_210_pagado_con_500(self):
        v = self.crear_venta(
            [self.renglon(self.prod_rosa, 140), self.renglon(self.prod_anais, 60),
             self.renglon(self.prod_yareli, 10)],
            efectivo=500,
        )
        _, r = self.assert_invariantes(v)
        self.assertEqual(r["receptora"]["empleado_id"], self.rosa.id)
        self.assertEqual(r["cambio"], 290.0)
        self.assertEqual(r["queda_receptora"], 140.0)
        self.assertEqual([(p["nombre"], p["efectivo"]) for p in r["pasar"]], [("Anais", 60.0), ("Yareli", 10.0)])
        self.assertIsNone(r["clip"])

    def test_e_saldos_se_suman_entre_ventas(self):
        # Venta 1: Anais 100 + Yareli 60 con tarjeta: a Yareli le quedan 60.
        v1 = self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 60)],
                              tarjeta=160)
        # Venta 2: Yareli 100 + Anais 20 con tarjeta: a Anais le quedan 20.
        v2 = self.crear_venta([self.renglon(self.prod_yareli, 100), self.renglon(self.prod_anais, 20)],
                              tarjeta=120)
        self.assert_invariantes(v1)
        self.assert_invariantes(v2)
        # 60 - 20 = 40.
        self.assertEqual(self.saldos(v1, v2), {"Anais": D(-40), "Yareli": D(40)})
        # Todo en efectivo: a nadie le queda saldo.
        e1 = self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 60)],
                              efectivo=200)
        e2 = self.crear_venta([self.renglon(self.prod_rosa, 30), self.servicio("Copias", 10),
                               self.renglon(self.prod_yareli, 50)], efectivo=90)
        self.assertTrue(all(s == CERO for s in self.saldos(e1, e2).values()))

    def test_f_servicio_de_la_responsable_pagado_con_tarjeta(self):
        # Anais 100 + servicio Copias 30 (de Rosa, responsable) todo con
        # tarjeta: Anais es receptora y cobra 130 en su Clip; a Rosa le quedan
        # 30 de saldo (venta de antes del pago en seco).
        v = self.crear_venta([self.renglon(self.prod_anais, 100), self.servicio("Copias", 30)],
                             tarjeta=130)
        filas, r = self.assert_invariantes(v)
        self.assertEqual(r["receptora"]["empleado_id"], self.anais.id)
        self.assertEqual(r["clip"], {"empleado_id": self.anais.id, "nombre": "Anais", "monto": 130.0})
        rosa = desglose_como_dict(self.desglose(v))["Rosa"]
        self.assertEqual((rosa["total"], rosa["efectivo"], rosa["tarjeta"], rosa["saldo"]),
                         (D(30), CERO, CERO, D(30)))
        self.assertEqual(rosa["servicios"]["total"], D(30))


# ---------------------------------------------------------------------------
# Propiedad: 200 ventas pseudoaleatorias
# ---------------------------------------------------------------------------

class PagoEnSecoTest(RepartoTestCase):
    """
    Ventas con pago_en_seco (todas las del POS desde el deploy): a las demás
    dueñas se les pasa lo suyo en efectivo aunque se pague con tarjeta, del
    fondo de la caja de la receptora. Nunca queda deuda entre dueñas.
    """

    def gelish(self, **pago):
        # Gelish $100 (Anais) + tinte $50 (Yareli) + producto $10 (Rosa) = $160.
        return self.crear_venta(
            [self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
             self.renglon(self.prod_rosa, 10)],
            pago_en_seco=True, **pago,
        )

    def test_todo_con_tarjeta_se_paga_del_fondo(self):
        v = self.gelish(tarjeta=160)
        fx = self.por_nombre(reparto_venta(self.de_bd(v)))
        self.assertEqual({n: fx[n]["efectivo"] for n in fx}, {"Anais": D(-60), "Yareli": D(50), "Rosa": D(10)})
        self.assertEqual({n: fx[n]["tarjeta"] for n in fx}, {"Anais": D(160), "Yareli": CERO, "Rosa": CERO})
        self.assertEqual({n: fx[n]["saldo"] for n in fx}, {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})

        r = reparto_efectivo_venta(v.id)
        self.assertEqual(r["caso"], "varias")
        self.assertEqual((r["queda_receptora"], r["del_fondo"]), (-60.0, 60.0))

    def test_mixto_que_no_alcanza(self):
        # 30 en efectivo + 130 tarjeta: a Yareli y Rosa se les pasan 60; 30
        # vienen del billete y 30 del fondo de Anais.
        v = self.gelish(efectivo=30, tarjeta=130)
        fx = self.por_nombre(reparto_venta(self.de_bd(v)))
        self.assertEqual({n: fx[n]["efectivo"] for n in fx}, {"Anais": D(-30), "Yareli": D(50), "Rosa": D(10)})
        self.assertEqual({n: fx[n]["saldo"] for n in fx}, {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})
        self.assertEqual(reparto_efectivo_venta(v.id)["del_fondo"], 30.0)

    def test_si_alcanza_es_igual_que_antes(self):
        for en_seco in (False, True):
            with self.subTest(en_seco=en_seco):
                v = self.crear_venta(
                    [self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
                     self.renglon(self.prod_rosa, 10)],
                    efectivo=90, tarjeta=70, pago_en_seco=en_seco,
                )
                fx = self.por_nombre(reparto_venta(self.de_bd(v)))
                self.assertEqual({n: fx[n]["efectivo"] for n in fx},
                                 {"Anais": D(30), "Yareli": D(50), "Rosa": D(10)})
                self.assertEqual(reparto_efectivo_venta(v.id)["del_fondo"], 0.0)

    def test_sin_duena_no_saca_del_fondo(self):
        # Lo sin dueña no tiene caja: no se le "pasa" efectivo que no entró.
        v = self.crear_venta([self.renglon(self.prod_anais, 60), self.renglon(self.prod_sin_dueno, 40)],
                             tarjeta=100, pago_en_seco=True)
        filas = reparto_venta(self.de_bd(v))
        self.assertEqual(suma(filas, "efectivo"), CERO)
        sin = next(f for f in filas if f["grupo"].cajon_id is None)
        self.assertEqual((sin["efectivo"], sin["saldo"]), (CERO, D(40)))
        r = reparto_efectivo_venta(v.id)
        self.assertEqual((r["sin_cajon"], r["del_fondo"]), (0.0, 0.0))

    def test_ventas_de_antes_no_cambian(self):
        # Reimprimir un corte viejo da lo mismo que cuando se cobró.
        v = self.gelish(tarjeta=160)
        Venta.objects.filter(pk=v.pk).update(pago_en_seco=False)
        self.assertEqual(self.saldos(v), {"Anais": D(-60), "Yareli": D(50), "Rosa": D(10)})
        self.assertEqual({f["nombre"]: f["efectivo"] for f in self.desglose(v)},
                         {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})

    def test_desglose_del_corte_cuadra_con_negativos(self):
        ventas = [self.gelish(tarjeta=160), self.gelish(efectivo=200), self.gelish(efectivo=30, tarjeta=130)]
        filas = self.desglose(*ventas)
        tot = totales_caja(Venta.objects.filter(pk__in=[v.pk for v in ventas]))
        self.assertEqual(suma(filas, "efectivo"), tot["efectivo"])
        self.assertEqual(suma(filas, "tarjeta"), tot["tarjeta"])
        self.assertEqual({f["nombre"]: f["saldo"] for f in filas}, {"Anais": CERO, "Yareli": CERO, "Rosa": CERO})
        # Anais: +100 de la venta en efectivo (160 neto - 60 que pasó), -60 y -30 del fondo.
        self.assertEqual({f["nombre"]: f["efectivo"] for f in filas},
                         {"Anais": D(10), "Yareli": D(150), "Rosa": D(30)})


class RepartoPropiedadTest(RepartoTestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.sucursal_sur = Sucursal.objects.create(nombre="Sucursal Sur", dueño_servicios=None)
        cls.caja_sur = Caja.objects.create(sucursal=cls.sucursal_sur, nombre="Caja Sur")

    def generar(self, rng):
        productos = [self.prod_rosa, self.prod_anais, self.prod_yareli, self.prod_sin_dueno]
        renglones = []
        for _ in range(rng.randint(1, 4)):
            k = rng.random()
            cantidad = rng.randint(1, 3)
            precio = Decimal(rng.randint(1, 50000)) / 100
            if k < 0.55:
                renglones.append(self.renglon(rng.choice(productos[:3]), precio * cantidad, cantidad))
            elif k < 0.75:
                renglones.append(self.servicio(rng.choice(["Copias", "Prod. sin registro", "Impresión"]),
                                               precio * cantidad, cantidad))
            elif k < 0.9:
                renglones.append(self.regalo(rng.choice(productos[:3]), cantidad))
            else:
                renglones.append(self.renglon(self.prod_sin_dueno, precio * cantidad, cantidad))

        suma_r = sum((r["subtotal"] for r in renglones), CERO)
        subtotal = None
        if suma_r > 0 and rng.random() < 0.15:  # oferta que cobra menos que los renglones
            subtotal = D(suma_r * Decimal(rng.randint(60, 99)) / 100)
        sub = subtotal if subtotal is not None else suma_r
        pct = rng.choice([0, 5, 10, 15])
        total = sub - D(sub * pct / 100)

        extra = D(rng.choice([0, 0, rng.randint(1, 50000) / 100]))
        pago = rng.choice(["efectivo", "tarjeta", "mixto"])
        if pago == "mixto" and total >= D(0.02):
            tarjeta = Decimal(rng.randint(1, int(total * 100) - 1)) / 100
            efectivo = total - tarjeta + extra
        elif pago == "tarjeta":
            tarjeta, efectivo = total, CERO
        else:
            tarjeta, efectivo = CERO, total + extra
        caja = self.caja_sur if rng.random() < 0.2 else rng.choice([self.caja_anais, self.caja_fabiola])
        return self.crear_venta(renglones, efectivo=efectivo, tarjeta=tarjeta, descuento_pct=pct,
                                caja=caja, subtotal=subtotal)

    def test_invariantes_200_ventas(self):
        rng = random.Random(42)
        ventas = [self.generar(rng) for _ in range(200)]
        qs = Venta.objects.filter(pk__in=[v.pk for v in ventas])

        efectivo_por_duena = {}
        tarjeta_por_duena = {}
        sin_cajon = CERO
        casos = set()
        con_saldo = 0
        # assert_invariantes revisa por venta: columnas exactas, e+t+saldo ==
        # total por fila, tarjeta solo en la receptora, saldo >= 0 fuera de
        # ella y <= 0 en ella, Σsaldo == 0 si cuadra, y el invariante del modal.
        for v in ventas_para_desglose(qs):
            filas_v, r = self.assert_invariantes(v)
            casos.add(r["caso"])
            sin_cajon += Df(r["sin_cajon"])
            if r["receptora"]:
                rid = r["receptora"]["empleado_id"]
                efectivo_por_duena[rid] = efectivo_por_duena.get(rid, CERO) + Df(r["queda_receptora"])
                if r["clip"]:
                    tarjeta_por_duena[rid] = tarjeta_por_duena.get(rid, CERO) + Df(r["clip"]["monto"])
            con_saldo += any(f["saldo"] > 0 for f in filas_v)
            for p in r["pasar"]:
                efectivo_por_duena[p["empleado_id"]] = (
                    efectivo_por_duena.get(p["empleado_id"], CERO) + Df(p["efectivo"])
                )
        # El generador sí ejercita todos los casos del modal, y también ventas
        # (de antes del pago en seco) donde a alguien le quedó saldo.
        self.assertEqual(casos, {"varias", "una", "sin_efectivo", "sin_duena"})
        self.assertGreater(con_saldo, 0)

        filas = desglose_por_dueno(ventas_para_desglose(qs))
        totales = totales_caja(qs)
        self.assertEqual(totales["num_ventas"], 200)
        for campo in ("total", "efectivo", "tarjeta"):
            self.assertEqual(suma(filas, campo), totales[campo], campo)
        for f in filas:
            serv = f["servicios"]["total"] if f["servicios"] else CERO
            self.assertEqual(f["productos"] + serv, f["total"])
            self.assertEqual(f["efectivo"] + f["tarjeta"] + f["saldo"], f["total"])
            if f["servicios"]:
                self.assertEqual(sum((c["total"] for c in f["servicios"]["conceptos"]), CERO), serv)
            if f["especial"]:
                continue
            # Σ por dueña de lo que dice el modal == su fila del desglose.
            self.assertEqual(efectivo_por_duena.get(f["empleado_id"], CERO), f["efectivo"], f["nombre"])
            self.assertEqual(tarjeta_por_duena.get(f["empleado_id"], CERO), f["tarjeta"], f["nombre"])
        self.assertEqual(sum((f["efectivo"] for f in filas if f["especial"]), CERO), sin_cajon)
        self.assertIn("Servicios (sin responsable)", desglose_como_dict(filas))
