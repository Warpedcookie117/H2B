"""
Deudas entre dueñas (ventas/services/deudas_service.py): ya no salen en el
corte; se registran al cortar (DeudaEntreDuenas) y cada dueña ve en su
dashboard solo las suyas: "hoy" en vivo y el historial con "Ya se pagó".
"""
import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from tienda_temp.models import Usuario
from ventas.models import CorteCaja, DeudaEntreDuenas
from ventas.services.corte_service import generar_corte_para_fecha
from ventas.services.deudas_service import (
    PAGADAS_A_CONSERVAR,
    DeudaCambio,
    _desde_txt,
    deudas_hoy,
    historial,
    marcar_pagada,
    marcar_pagada_hoy,
    registrar_deudas_de_corte,
    ventas_pendientes_de_corte,
)
from ventas.tests.base import D, VentasBaseTestCase


def hoy_local():
    return timezone.localtime().date()


def a_las(dia, hora, minuto=0):
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto)))


class DeudasTestCase(VentasBaseTestCase):

    def venta_gelish(self, caja=None, fecha=None):
        """Anais 100 + Yareli 50 + Rosa 10, todo con tarjeta (160): Anais
        es receptora, cobra los 160 en su Clip y le debe 50 a Yareli y 10 a Rosa."""
        return self.crear_venta(
            [self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
             self.renglon(self.prod_rosa, 10)],
            tarjeta=160, caja=caja, fecha=fecha,
        )

    def cortar(self, caja=None, empleado=None):
        """Corte del día por la vista, como lo hace la cajera."""
        caja = caja or self.caja_anais
        self.login(empleado or self.cajero)
        session = self.client.session
        session["caja_actual"] = caja.id
        session["sucursal_actual"] = caja.sucursal_id
        session.save()
        antes = set(CorteCaja.objects.values_list("id", flat=True))
        with mock.patch("ventas.views.ticket_corte_views.imprimir_silencioso"):
            response = self.client.get(reverse("ventas:corte_caja"))
        corte = CorteCaja.objects.exclude(id__in=antes).get()
        self.assertRedirects(response, reverse("ventas:ticket_corte", args=[corte.id]),
                             fetch_redirect_response=False)
        return corte

    def corte_manual(self, ventas, caja=None):
        """Corte armado a mano (sin la vista) con esas ventas y sus deudas registradas."""
        caja = caja or self.caja_anais
        corte = CorteCaja.objects.create(caja=caja, caja_nombre=caja.nombre, empleado=self.cajero,
                                         total_general=0, total_por_dueno={})
        corte.ventas.set(ventas)
        registrar_deudas_de_corte(corte)
        return corte

    def pares(self, qs=None):
        qs = DeudaEntreDuenas.objects.all() if qs is None else qs
        return sorted((d.deudor_nombre, d.acreedor_nombre, d.monto) for d in qs)


# ---------------------------------------------------------------------------
# Registro al cortar
# ---------------------------------------------------------------------------

class RegistrarDeudasTest(DeudasTestCase):

    def test_corte_del_dia_registra_deudas_con_fecha_de_la_venta(self):
        venta = self.venta_gelish()
        corte = self.cortar()

        deudas = DeudaEntreDuenas.objects.filter(corte=corte)
        self.assertEqual(self.pares(deudas), [("Anais", "Rosa", D(10)), ("Anais", "Yareli", D(50))])
        for d in deudas:
            self.assertEqual(d.deudor, self.anais)
            self.assertIn(d.acreedor, (self.yareli, self.rosa))
            self.assertEqual(d.fecha, venta.fecha)
            self.assertEqual(d.caja_nombre, "Caja Anais")
            self.assertFalse(d.pagada)

    def test_registrar_es_idempotente(self):
        corte = self.corte_manual([self.venta_gelish()])
        registrar_deudas_de_corte(corte)
        self.assertEqual(DeudaEntreDuenas.objects.count(), 2)

    def test_venta_en_efectivo_no_registra_deudas(self):
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50)],
                         efectivo=200)
        self.cortar()
        self.assertFalse(DeudaEntreDuenas.objects.exists())

    def test_si_registrar_falla_el_corte_igual_se_hace(self):
        self.venta_gelish()
        with mock.patch("ventas.views.ticket_corte_views.registrar_deudas_de_corte",
                        side_effect=RuntimeError("boom")), \
                self.assertLogs("ventas.views.ticket_corte_views", level="ERROR"):
            corte = self.cortar()
        self.assertEqual(corte.ventas.count(), 1)
        self.assertFalse(DeudaEntreDuenas.objects.exists())

    def test_corte_automatico_no_duplica_ventas_ya_cortadas(self):
        ayer = hoy_local() - timedelta(days=1)
        v1 = self.venta_gelish(fecha=a_las(ayer, 11))
        self.corte_manual([v1])
        self.assertEqual(DeudaEntreDuenas.objects.count(), 2)

        # Venta posterior al corte manual: Yareli 100 + Anais 30 con tarjeta
        # → Yareli le debe 30 a Anais.
        v2 = self.crear_venta([self.renglon(self.prod_yareli, 100), self.renglon(self.prod_anais, 30)],
                              tarjeta=130, fecha=a_las(ayer, 15))

        # El automático toma TODO el día (v1 incluida, el bug conocido) pero
        # solo registra deudas de lo que no estaba ya en otro corte.
        auto = generar_corte_para_fecha(self.caja_anais, ayer)
        self.assertEqual(set(auto.ventas.values_list("id", flat=True)), {v1.id, v2.id})
        self.assertEqual(self.pares(auto.deudas_duenas.all()), [("Yareli", "Anais", D(30))])
        self.assertEqual(auto.deudas_duenas.get().fecha, v2.fecha)
        self.assertEqual(DeudaEntreDuenas.objects.count(), 3)


class PodaTest(DeudasTestCase):

    def deuda(self, deudor, acreedor, dias_atras, pagada):
        corte = CorteCaja.objects.create(caja=self.caja_anais, caja_nombre="Caja Anais",
                                         total_general=0, total_por_dueno={})
        return DeudaEntreDuenas.objects.create(
            corte=corte, deudor=deudor, acreedor=acreedor,
            deudor_nombre=deudor.user.first_name, acreedor_nombre=acreedor.user.first_name,
            monto=D(10), fecha=timezone.now() - timedelta(days=dias_atras), caja_nombre="Caja Anais",
            pagada=pagada, pagada_por=acreedor if pagada else None,
            pagada_en=timezone.now() if pagada else None,
        )

    def test_conserva_5_pagadas_y_nunca_borra_no_pagadas(self):
        # 7 pagadas entre Anais y Yareli (días 10..16 atrás) + 2 no pagadas muy viejas.
        pagadas = [self.deuda(self.anais, self.yareli, 10 + i, True) for i in range(7)]
        no_pagadas = [self.deuda(self.yareli, self.anais, 100 + i, False) for i in range(2)]
        # Pagada de Rosa con Anais, la más vieja: fuera del top 5 de Anais
        # pero dentro del de Rosa → se conserva.
        de_rosa = self.deuda(self.rosa, self.anais, 200, True)

        # Un corte nuevo con deuda de Anais dispara la poda.
        self.corte_manual([self.venta_gelish()])

        entre = DeudaEntreDuenas.objects.filter(pagada=True, deudor=self.anais, acreedor=self.yareli)
        self.assertEqual(set(entre.values_list("id", flat=True)), {d.id for d in pagadas[:5]})
        for d in no_pagadas:
            self.assertTrue(DeudaEntreDuenas.objects.filter(pk=d.pk).exists())
        self.assertTrue(DeudaEntreDuenas.objects.filter(pk=de_rosa.pk).exists())
        # Las nuevas (no pagadas) del corte siguen ahí.
        self.assertEqual(DeudaEntreDuenas.objects.filter(pagada=False).count(), 4)

        # El historial de Anais: todas las no pagadas + 5 pagadas.
        h = historial(self.anais)
        self.assertEqual(sum(1 for i in h if i["pagada"]), 5)
        self.assertEqual(sum(1 for i in h if not i["pagada"]), 4)
        fechas = [i["fecha"] for i in h]
        self.assertEqual(fechas, sorted(fechas, reverse=True))


# ---------------------------------------------------------------------------
# Lo que ve cada dueña
# ---------------------------------------------------------------------------

class DeudasHoyTest(DeudasTestCase):

    def test_hoy_antes_y_despues_del_corte(self):
        venta = self.venta_gelish()
        desde = _desde_txt(venta.fecha, hoy_local())

        anais = deudas_hoy(self.anais)
        self.assertEqual([i.pop("desde_txt") for i in anais["items"]], [desde, desde])
        self.assertEqual(anais["items"], [
            {"caja": "Caja Anais", "caja_id": self.caja_anais.id, "con_id": self.yareli.id,
             "con_nombre": "Yareli", "yo_debo": True, "monto": 50.0},
            {"caja": "Caja Anais", "caja_id": self.caja_anais.id, "con_id": self.rosa.id,
             "con_nombre": "Rosa", "yo_debo": True, "monto": 10.0},
        ])
        self.assertEqual(anais["resumen"], [
            {"con_id": self.yareli.id, "con_nombre": "Yareli", "monto": -50.0},
            {"con_id": self.rosa.id, "con_nombre": "Rosa", "monto": -10.0},
        ])
        self.assertEqual((anais["total_debes"], anais["total_te_deben"]), (60.0, 0.0))

        yareli = deudas_hoy(self.yareli)
        self.assertEqual([i.pop("desde_txt") for i in yareli["items"]], [desde])
        self.assertEqual(yareli["items"], [
            {"caja": "Caja Anais", "caja_id": self.caja_anais.id, "con_id": self.anais.id,
             "con_nombre": "Anais", "yo_debo": False, "monto": 50.0},
        ])
        self.assertEqual(yareli["resumen"], [{"con_id": self.anais.id, "con_nombre": "Anais", "monto": 50.0}])
        self.assertEqual((yareli["total_debes"], yareli["total_te_deben"]), (0.0, 50.0))

        # Al cortar, "hoy" queda vacío y la deuda pasa al historial.
        self.cortar()
        vacio = {"items": [], "pagadas": [], "resumen": [], "total_debes": 0.0, "total_te_deben": 0.0}
        self.assertEqual(deudas_hoy(self.anais), vacio)
        self.assertEqual(deudas_hoy(self.yareli), vacio)

        h = historial(self.anais)
        self.assertEqual(sorted((i["con_nombre"], i["yo_debo"], i["monto"]) for i in h),
                         [("Rosa", True, 10.0), ("Yareli", True, 50.0)])
        hy = historial(self.yareli)
        self.assertEqual(len(hy), 1)
        self.assertEqual((hy[0]["con_nombre"], hy[0]["yo_debo"], hy[0]["monto"]), ("Anais", False, 50.0))
        self.assertEqual(historial(self.cajero), [])

    def test_por_caja_no_se_mezcla_pero_el_resumen_netea(self):
        # Caja Anais: Anais 100 + Yareli 60 con tarjeta → Anais debe 60.
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 60)],
                         tarjeta=160, caja=self.caja_anais)
        # Caja Fabiola: Yareli 100 + Anais 20 con tarjeta → Yareli debe 20.
        self.crear_venta([self.renglon(self.prod_yareli, 100), self.renglon(self.prod_anais, 20)],
                         tarjeta=120, caja=self.caja_fabiola)

        r = deudas_hoy(self.anais)
        self.assertTrue(all(i.pop("desde_txt").startswith("desde ") for i in r["items"]))
        self.assertEqual(r["items"], [
            {"caja": "Caja Anais", "caja_id": self.caja_anais.id, "con_id": self.yareli.id,
             "con_nombre": "Yareli", "yo_debo": True, "monto": 60.0},
            {"caja": "Caja Fabiola", "caja_id": self.caja_fabiola.id, "con_id": self.yareli.id,
             "con_nombre": "Yareli", "yo_debo": False, "monto": 20.0},
        ])
        self.assertEqual(r["resumen"], [{"con_id": self.yareli.id, "con_nombre": "Yareli", "monto": -40.0}])
        self.assertEqual((r["total_debes"], r["total_te_deben"]), (40.0, 0.0))

        ry = deudas_hoy(self.yareli)
        self.assertEqual(ry["resumen"], [{"con_id": self.anais.id, "con_nombre": "Anais", "monto": 40.0}])
        self.assertEqual((ry["total_debes"], ry["total_te_deben"]), (0.0, 40.0))
        # Rosa no participa.
        self.assertEqual(deudas_hoy(self.rosa)["items"], [])

    def test_desde_txt_formato(self):
        dia = datetime(2026, 10, 20).date()
        self.assertEqual(_desde_txt(a_las(dia, 16, 12), dia), "desde las 4:12 pm")
        self.assertEqual(_desde_txt(a_las(dia, 13, 5), dia), "desde la 1:05 pm")
        self.assertEqual(_desde_txt(a_las(dia, 0, 30), dia), "desde las 12:30 am")
        self.assertEqual(_desde_txt(a_las(dia, 9, 0), dia + timedelta(days=2)), "desde el 20/10 a las 9:00 am")

    def test_desde_es_la_primera_venta_con_deuda_de_esa_pareja(self):
        ahora = timezone.now()
        # Sin tarjeta: no deja deuda, no cuenta para el "desde".
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50)],
                         efectivo=150, fecha=ahora - timedelta(minutes=3))
        primera = self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50)],
                                   tarjeta=150, fecha=ahora - timedelta(minutes=2))
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 30)],
                         tarjeta=130, fecha=ahora - timedelta(minutes=1))

        items = deudas_hoy(self.yareli)["items"]
        self.assertEqual([(i["con_nombre"], i["monto"]) for i in items], [("Anais", 80.0)])
        self.assertEqual(items[0]["desde_txt"], _desde_txt(primera.fecha, hoy_local()))

    def test_queries_no_crecen_con_las_cajas(self):
        self.venta_gelish(caja=self.caja_anais)
        self.venta_gelish(caja=self.caja_fabiola)
        with self.assertNumQueries(4):
            deudas_hoy(self.anais)

    def test_ventas_pendientes_de_corte(self):
        ayer = hoy_local() - timedelta(days=1)
        vieja = self.venta_gelish(fecha=a_las(ayer, 10))
        hoy = self.venta_gelish()
        # Sin corte nunca: solo las de hoy.
        self.assertEqual(list(ventas_pendientes_de_corte(self.caja_anais)), [hoy])
        # Con corte: lo posterior al último corte.
        corte = self.corte_manual([vieja])
        CorteCaja.objects.filter(pk=corte.pk).update(fecha=a_las(ayer, 11))
        self.assertEqual(list(ventas_pendientes_de_corte(self.caja_anais)), [hoy])
        CorteCaja.objects.filter(pk=corte.pk).update(fecha=a_las(ayer, 9))
        self.assertEqual(set(ventas_pendientes_de_corte(self.caja_anais)), {vieja, hoy})


class MarcarPagadaTest(DeudasTestCase):

    def setUp(self):
        self.corte_manual([self.crear_venta(
            [self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50)], tarjeta=150)])
        self.deuda = DeudaEntreDuenas.objects.get()   # Anais le debe 50 a Yareli

    def item(self, empleado):
        return next(i for i in historial(empleado) if i["id"] == self.deuda.id)

    def test_la_acreedora_la_marca(self):
        marcar_pagada(self.deuda.id, self.yareli, True)
        a = self.item(self.anais)
        self.assertEqual((a["pagada"], a["pagada_por_mi"], a["aviso"]),
                         (True, False, "Yareli dice que ya le pagaste"))
        y = self.item(self.yareli)
        self.assertEqual((y["pagada"], y["pagada_por_mi"], y["aviso"]), (True, True, None))

        # Desmarcar (cualquiera de las dos) limpia todo.
        marcar_pagada(self.deuda.id, self.anais, False)
        self.deuda.refresh_from_db()
        self.assertEqual((self.deuda.pagada, self.deuda.pagada_por, self.deuda.pagada_en), (False, None, None))
        for emp in (self.anais, self.yareli):
            i = self.item(emp)
            self.assertEqual((i["pagada"], i["pagada_por_mi"], i["aviso"]), (False, False, None))

    def test_la_deudora_la_marca(self):
        marcar_pagada(self.deuda.id, self.anais, True)
        y = self.item(self.yareli)
        self.assertEqual((y["pagada"], y["pagada_por_mi"], y["aviso"]),
                         (True, False, "Anais dice que ya te pagó"))
        a = self.item(self.anais)
        self.assertEqual((a["pagada_por_mi"], a["aviso"]), (True, None))

    def test_idempotente(self):
        marcar_pagada(self.deuda.id, self.yareli, True)
        self.deuda.refresh_from_db()
        en = self.deuda.pagada_en
        marcar_pagada(self.deuda.id, self.yareli, True)
        self.deuda.refresh_from_db()
        self.assertEqual((self.deuda.pagada, self.deuda.pagada_por, self.deuda.pagada_en),
                         (True, self.yareli, en))

    def test_ajena_no_puede(self):
        with self.assertRaises(DeudaEntreDuenas.DoesNotExist):
            marcar_pagada(self.deuda.id, self.rosa, True)
        self.assertEqual(historial(self.rosa), [])

    def test_item_historial(self):
        i = self.item(self.anais)
        self.assertEqual(set(i), {"id", "fecha", "fecha_txt", "caja", "yo_debo", "con_nombre", "monto",
                                  "pagada", "pagada_por_mi", "aviso"})
        local = timezone.localtime(self.deuda.fecha)
        self.assertEqual(i["fecha"], local.isoformat())
        self.assertEqual(i["fecha_txt"], local.strftime("%d/%m"))
        self.assertEqual((i["caja"], i["yo_debo"], i["con_nombre"], i["monto"]),
                         ("Caja Anais", True, "Yareli", 50.0))


# ---------------------------------------------------------------------------
# Vistas / API
# ---------------------------------------------------------------------------

class EndpointPagadaTest(MarcarPagadaTest):

    def post(self, empleado, body, raw=False):
        if empleado is not None:
            self.login(empleado)
        return self.client.post(
            reverse("ventas:api_deuda_pagada", args=[self.deuda.id]),
            data=body if raw else json.dumps(body), content_type="application/json",
        )

    def test_ok(self):
        r = self.post(self.yareli, {"pagada": True})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["deuda"]["id"], self.deuda.id)
        self.assertEqual((data["deuda"]["pagada"], data["deuda"]["pagada_por_mi"], data["deuda"]["yo_debo"]),
                         (True, True, False))
        self.assertIsInstance(data["deuda"]["monto"], float)
        self.deuda.refresh_from_db()
        self.assertEqual((self.deuda.pagada, self.deuda.pagada_por), (True, self.yareli))

        r = self.post(self.anais, {"pagada": False})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["deuda"]["pagada"])

    def test_duena_ajena_404(self):
        self.assertEqual(self.post(self.rosa, {"pagada": True}).status_code, 404)
        self.deuda.refresh_from_db()
        self.assertFalse(self.deuda.pagada)

    def test_inexistente_404(self):
        self.login(self.anais)
        r = self.client.post(reverse("ventas:api_deuda_pagada", args=[999999]),
                             data=json.dumps({"pagada": True}), content_type="application/json")
        self.assertEqual(r.status_code, 404)

    def test_cajero_y_superusuario_sin_empleado_403(self):
        self.assertEqual(self.post(self.cajero, {"pagada": True}).status_code, 403)
        su = Usuario.objects.create_user(username="root", email="root@test.local", password="x",
                                         is_superuser=True, is_staff=True)
        self.client.force_login(su)
        self.assertEqual(self.post(None, {"pagada": True}).status_code, 403)

    def test_get_405(self):
        self.login(self.anais)
        r = self.client.get(reverse("ventas:api_deuda_pagada", args=[self.deuda.id]))
        self.assertEqual(r.status_code, 405)

    def test_body_invalido_400(self):
        for body, raw in (({}, False), ({"pagada": "si"}, False), ({"pagada": 1}, False),
                          ([True], False), ("no es json", True), ("", True)):
            with self.subTest(body=body):
                self.assertEqual(self.post(self.anais, body, raw=raw).status_code, 400)
        self.deuda.refresh_from_db()
        self.assertFalse(self.deuda.pagada)

    def test_csrf_requerido(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.anais.user)
        r = c.post(reverse("ventas:api_deuda_pagada", args=[self.deuda.id]),
                   data=json.dumps({"pagada": True}), content_type="application/json")
        self.assertEqual(r.status_code, 403)


class ApiVentasHoyDeudasTest(DeudasTestCase):

    def test_incluye_mis_deudas_numericas(self):
        ayer = hoy_local() - timedelta(days=1)
        corte = self.corte_manual([self.venta_gelish(fecha=a_las(ayer, 12))])   # historial
        # Fecha explícita: en Windows el reloj tiene ~15 ms de resolución y
        # corte y venta podían quedar con el mismo instante.
        CorteCaja.objects.filter(pk=corte.pk).update(fecha=a_las(ayer, 13))
        self.venta_gelish()                                                      # hoy, sin cortar

        self.login(self.anais)
        r = self.client.get(reverse("ventas:api_ventas_hoy"))
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        # Las llaves de siempre siguen ahí.
        for k in ("chart", "cajas", "mis_ventas", "mis_cajas"):
            self.assertIn(k, data)
        self.assertIn("saldo", data["mis_ventas"])

        hoy = data["mis_deudas"]["hoy"]
        self.assertEqual(set(hoy), {"items", "pagadas", "resumen", "total_debes", "total_te_deben"})
        self.assertEqual(len(hoy["items"]), 2)
        for it in hoy["items"]:
            self.assertIsInstance(it["monto"], float)
            self.assertIs(it["yo_debo"], True)
        self.assertIsInstance(hoy["total_debes"], float)
        self.assertEqual(hoy["total_debes"], 60.0)

        hist = data["mis_deudas"]["historial"]
        self.assertEqual(len(hist), 2)
        for it in hist:
            self.assertIsInstance(it["monto"], float)
            self.assertIsInstance(it["id"], int)

        # Yareli solo ve lo suyo.
        self.login(self.yareli)
        data = self.client.get(reverse("ventas:api_ventas_hoy")).json()
        self.assertEqual([(i["con_nombre"], i["monto"]) for i in data["mis_deudas"]["hoy"]["items"]],
                         [("Anais", 50.0)])
        self.assertEqual([(i["con_nombre"], i["monto"]) for i in data["mis_deudas"]["historial"]],
                         [("Anais", 50.0)])

    def test_dashboard_dueno_trae_mis_deudas(self):
        self.venta_gelish()
        self.login(self.anais)
        api = self.client.get(reverse("ventas:api_ventas_hoy")).json()["mis_deudas"]
        response = self.client.get(reverse("tienda_temp:dashboard_dueno"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["mis_deudas"], api)

    def test_superusuario_sin_empleado_null(self):
        su = Usuario.objects.create_user(username="root", email="root@test.local", password="x",
                                         is_superuser=True, is_staff=True)
        self.client.force_login(su)
        data = self.client.get(reverse("ventas:api_ventas_hoy")).json()
        self.assertIsNone(data["mis_deudas"])


class CorteSinDeudasTest(DeudasTestCase):

    def test_ticket_corte_no_pasa_deudas(self):
        self.venta_gelish()
        corte = self.cortar()
        response = self.client.get(reverse("ventas:ticket_corte", args=[corte.id]))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("deudas", response.context.keys())
        for k in ("filas_duenos", "resumen_duenos", "clips", "total_efectivo", "total_tarjeta"):
            self.assertIn(k, response.context.keys())
        self.assertEqual(response.context["total_tarjeta"], D(160))


# ---------------------------------------------------------------------------
# "Ya se pagó" en las deudas de HOY (pago en corto, antes del corte)
# ---------------------------------------------------------------------------

class PagoEnCortoTest(DeudasTestCase):
    """venta_gelish: Anais le debe 50 a Yareli y 10 a Rosa (Caja Anais)."""

    def pagar(self, empleado, con, monto, caja=None):
        return marcar_pagada_hoy(empleado, (caja or self.caja_anais).id, con.id, D(monto))

    def pendientes(self, empleado):
        return [(i["con_nombre"], i["yo_debo"], i["monto"]) for i in deudas_hoy(empleado)["items"]]

    def test_pagar_quita_la_deuda_y_la_muestra_pagada_a_las_dos(self):
        self.venta_gelish()
        pago = self.pagar(self.yareli, self.anais, 50)
        self.assertEqual((pago.deudor, pago.acreedor, pago.monto), (self.anais, self.yareli, D(50)))
        self.assertIsNone(pago.corte)
        self.assertTrue(pago.antes_del_corte and pago.pagada)

        self.assertEqual(self.pendientes(self.yareli), [])
        self.assertEqual(self.pendientes(self.anais), [("Rosa", True, 10.0)])
        self.assertEqual(deudas_hoy(self.anais)["total_debes"], 10.0)

        hy = deudas_hoy(self.yareli)["pagadas"]
        self.assertEqual([(i["con_nombre"], i["monto"], i["pagada"], i["pagada_por_mi"], i["aviso"]) for i in hy],
                         [("Anais", 50.0, True, True, None)])
        ha = deudas_hoy(self.anais)["pagadas"]
        self.assertEqual([i["aviso"] for i in ha], ["Yareli dice que ya le pagaste"])
        # No sale en el historial de cortes anteriores hasta que haya corte.
        self.assertEqual(historial(self.yareli), [])

    def test_si_despues_entra_otra_venta_queda_lo_nuevo_pendiente(self):
        self.venta_gelish()
        self.pagar(self.anais, self.yareli, 50)
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 20)], tarjeta=120)
        self.assertEqual(self.pendientes(self.yareli), [("Anais", False, 20.0)])

    def test_pagado_de_mas_la_deuda_queda_al_reves(self):
        self.venta_gelish()
        self.pagar(self.anais, self.yareli, 50)
        # Yareli es receptora y cobra todo en su Clip: le debe 30 a Anais.
        self.crear_venta([self.renglon(self.prod_yareli, 100), self.renglon(self.prod_anais, 30)], tarjeta=130)
        self.assertEqual(self.pendientes(self.yareli), [("Anais", True, 30.0)])

    def test_monto_distinto_no_guarda(self):
        self.venta_gelish()
        with self.assertRaises(DeudaCambio):
            self.pagar(self.yareli, self.anais, 40)
        self.pagar(self.yareli, self.anais, 50)
        # Ya pagada: volver a picar con lo que se veía antes no la paga dos veces.
        with self.assertRaises(DeudaEntreDuenas.DoesNotExist):
            self.pagar(self.anais, self.yareli, 50)
        self.assertEqual(DeudaEntreDuenas.objects.count(), 1)

    def test_sin_deuda_o_ajena(self):
        self.venta_gelish()
        with self.assertRaises(DeudaEntreDuenas.DoesNotExist):
            self.pagar(self.yareli, self.rosa, 10)          # Yareli y Rosa no tienen cuentas
        with self.assertRaises(DeudaEntreDuenas.DoesNotExist):
            self.pagar(self.yareli, self.anais, 50, caja=self.caja_fabiola)

    def test_desmarcar_lo_borra_y_vuelve_a_pendiente(self):
        self.venta_gelish()
        pago = self.pagar(self.yareli, self.anais, 50)
        self.assertIsNone(marcar_pagada(pago.id, self.anais, False))
        self.assertFalse(DeudaEntreDuenas.objects.exists())
        self.assertEqual(self.pendientes(self.yareli), [("Anais", False, 50.0)])

    def test_el_corte_registra_solo_lo_pendiente(self):
        self.venta_gelish()
        pago = self.pagar(self.yareli, self.anais, 50)
        self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 20)], tarjeta=120)
        corte = self.cortar()

        pago.refresh_from_db()
        self.assertEqual(pago.corte, corte)
        pendientes = DeudaEntreDuenas.objects.filter(corte=corte, antes_del_corte=False)
        self.assertEqual(sorted((d.deudor_nombre, d.acreedor_nombre, d.monto, d.pagada) for d in pendientes),
                         [("Anais", "Rosa", D(10), False), ("Anais", "Yareli", D(20), False)])
        self.assertTrue(all(d.caja_id == self.caja_anais.id for d in pendientes))

        # Hoy queda vacío; en el historial están el pago (pagada) y lo que faltó.
        self.assertEqual(deudas_hoy(self.yareli)["items"], [])
        self.assertEqual(deudas_hoy(self.yareli)["pagadas"], [])
        self.assertEqual(sorted((i["monto"], i["pagada"]) for i in historial(self.yareli)),
                         [(20.0, False), (50.0, True)])

        # Idempotente: registrar otra vez no duplica nada.
        antes = DeudaEntreDuenas.objects.count()
        registrar_deudas_de_corte(corte)
        self.assertEqual(DeudaEntreDuenas.objects.count(), antes)

    def test_pagada_completa_el_corte_no_registra_nada_mas(self):
        self.venta_gelish()
        self.pagar(self.yareli, self.anais, 50)
        self.pagar(self.rosa, self.anais, 10)
        corte = self.cortar()
        self.assertEqual(DeudaEntreDuenas.objects.filter(corte=corte, antes_del_corte=False).count(), 0)
        self.assertEqual(DeudaEntreDuenas.objects.filter(corte=corte, antes_del_corte=True).count(), 2)

    def test_el_pago_de_otra_caja_no_se_mezcla(self):
        self.venta_gelish(caja=self.caja_anais)
        self.venta_gelish(caja=self.caja_fabiola)
        self.pagar(self.yareli, self.anais, 50, caja=self.caja_fabiola)
        corte = self.cortar(caja=self.caja_anais)
        # El corte de Caja Anais registra sus 50 completos; el pago es de Caja Fabiola.
        self.assertTrue(DeudaEntreDuenas.objects.filter(
            corte=corte, antes_del_corte=False, acreedor=self.yareli, monto=D(50)).exists())
        self.assertEqual(self.pendientes(self.yareli), [])
        self.assertEqual(len(deudas_hoy(self.yareli)["pagadas"]), 1)

    def test_la_poda_no_borra_pagos_sin_corte(self):
        self.venta_gelish(caja=self.caja_fabiola)
        pago = self.pagar(self.yareli, self.anais, 50, caja=self.caja_fabiola)
        for i in range(PAGADAS_A_CONSERVAR + 2):
            corte = self.corte_manual([self.venta_gelish(fecha=a_las(hoy_local() - timedelta(days=i + 1), 10))])
            DeudaEntreDuenas.objects.filter(corte=corte).update(pagada=True)
        registrar_deudas_de_corte(corte)
        self.assertTrue(DeudaEntreDuenas.objects.filter(pk=pago.pk).exists())


class PagoEnCortoApiTest(DeudasTestCase):

    def setUp(self):
        self.venta_gelish()
        self.url = reverse("ventas:api_deuda_hoy_pagada")

    def post(self, empleado, body):
        self.login(empleado)
        return self.client.post(self.url, data=json.dumps(body), content_type="application/json")

    def test_ok_y_se_ve_en_el_polling(self):
        r = self.post(self.yareli, {"caja_id": self.caja_anais.id, "con_id": self.anais.id, "monto": 50.0})
        self.assertEqual((r.status_code, r.json()), (200, {"status": "ok"}))
        self.login(self.anais)
        hoy = self.client.get(reverse("ventas:api_ventas_hoy")).json()["mis_deudas"]["hoy"]
        self.assertEqual([i["con_nombre"] for i in hoy["items"]], ["Rosa"])
        self.assertEqual([i["aviso"] for i in hoy["pagadas"]], ["Yareli dice que ya le pagaste"])

    def test_cambio_409(self):
        r = self.post(self.yareli, {"caja_id": self.caja_anais.id, "con_id": self.anais.id, "monto": 45})
        self.assertEqual(r.status_code, 409)
        self.assertFalse(DeudaEntreDuenas.objects.exists())

    def test_no_existe_404(self):
        self.assertEqual(
            self.post(self.yareli, {"caja_id": 999999, "con_id": self.anais.id, "monto": 50}).status_code, 404)
        self.assertEqual(
            self.post(self.yareli, {"caja_id": self.caja_anais.id, "con_id": self.rosa.id, "monto": 10}).status_code,
            404)

    def test_body_invalido_400(self):
        for body in ({}, {"caja_id": "1", "con_id": self.anais.id, "monto": 50},
                     {"caja_id": self.caja_anais.id, "con_id": True, "monto": 50},
                     {"caja_id": self.caja_anais.id, "con_id": self.anais.id, "monto": "50"}, []):
            with self.subTest(body=body):
                self.assertEqual(self.post(self.yareli, body).status_code, 400)

    def test_solo_duenas(self):
        r = self.post(self.cajero, {"caja_id": self.caja_anais.id, "con_id": self.anais.id, "monto": 50})
        self.assertEqual(r.status_code, 403)

    def test_desmarcar_por_api_devuelve_null(self):
        self.post(self.yareli, {"caja_id": self.caja_anais.id, "con_id": self.anais.id, "monto": 50})
        pago = DeudaEntreDuenas.objects.get()
        self.login(self.anais)
        r = self.client.post(reverse("ventas:api_deuda_pagada", args=[pago.id]),
                             data=json.dumps({"pagada": False}), content_type="application/json")
        self.assertEqual(r.json(), {"status": "ok", "deuda": None})
