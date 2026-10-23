"""
Consumidores de ventas/services/reparto.py: ticket de corte (web y
térmico), corte del día, "¿Cuánto llevo yo?" (resumen_ventas_dueno_*),
"Ventas del mes" y las cards/API de ventas de hoy. Lo que importa es que
todas las pantallas cuadren entre sí y con lo que hay en la caja.
"""
from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

from django.urls import reverse
from django.utils import timezone

from sucursales.models import Caja
from ventas.models import CorteCaja, Venta
from ventas.services.corte_service import (
    generar_corte_para_fecha,
    resumen_ventas_dueno_por_caja,
    resumen_ventas_dueno_por_fecha,
)
from ventas.services.reparto import (
    NOMBRE_SERVICIOS_SIN_RESPONSABLE,
    desglose_por_dueno,
    totales_caja,
    ventas_para_desglose,
)
from ventas.services.ticket_service import generar_texto_ticket
from ventas.tests.base import D, VentasBaseTestCase

CERO = Decimal("0.00")


def hoy_local():
    return timezone.localtime().date()


def a_las(dia, hora, minuto=0, segundo=0):
    """datetime aware (zona local de settings) del día dado."""
    return timezone.make_aware(datetime.combine(dia, time(hora, minuto, segundo)))


def suma(filas, campo):
    return sum((f[campo] for f in filas), CERO)


class ConsumidoresTestCase(VentasBaseTestCase):

    def ventas_variadas(self, caja=None, fecha=None):
        """
        Efectivo con cambio, mixto, 10% de descuento, servicios (incluido
        "Prod. sin registro"), regalo y una cuenta con las 3 dueñas que
        obliga a repartir centavos.
        """
        caja = caja or self.caja_anais
        kw = {"caja": caja, "fecha": fecha}
        return [
            # 120 pagado con 500 → cambio 380, neto 120.
            self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, **kw),
            # 300 mixto: 200 efectivo + 150 tarjeta → cambio 50, neto 150.
            self.crear_venta([self.renglon(self.prod_rosa, 200), self.renglon(self.prod_anais, 100)],
                             efectivo=200, tarjeta=150, **kw),
            # 1000 con 10% → 900; paga 1000 → cambio 100.
            self.crear_venta([self.renglon(self.prod_anais, 600), self.renglon(self.prod_yareli, 400)],
                             efectivo=1000, descuento_pct=10, **kw),
            # Servicios (van a Rosa, responsable de servicios) + Yareli, con tarjeta.
            self.crear_venta([self.servicio("Prod. sin registro", 35), self.servicio("Copias", 15),
                              self.renglon(self.prod_yareli, 50)], tarjeta=100, **kw),
            # Regalo en $0 + Rosa 80; paga 100 → cambio 20.
            self.crear_venta([self.regalo(self.prod_yareli), self.renglon(self.prod_rosa, 80)],
                             efectivo=100, **kw),
            # 3 dueñas iguales, 10 efectivo + 20 tarjeta: centavos por repartir.
            self.crear_venta([self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
                              self.renglon(self.prod_yareli, 10)], efectivo=10, tarjeta=20, **kw),
            # 300 con 10% → 270 mixto: 100 efectivo + 170 tarjeta.
            self.crear_venta([self.renglon(self.prod_rosa, 100), self.renglon(self.prod_anais, 100),
                              self.renglon(self.prod_yareli, 100)],
                             efectivo=100, tarjeta=170, descuento_pct=10, **kw),
        ]

    def crear_corte(self, ventas, caja=None, caja_nombre="Caja Anais"):
        corte = CorteCaja.objects.create(
            caja=caja if caja is not None else self.caja_anais,
            caja_nombre=caja_nombre,
            empleado=self.cajero,
            total_general=sum((v.total for v in ventas), CERO),
            total_por_dueno={},
        )
        corte.ventas.set(ventas)
        return corte


# ---------------------------------------------------------------------------
# Ticket de corte (vista web)
# ---------------------------------------------------------------------------

class TicketCorteVistaTest(ConsumidoresTestCase):

    def setUp(self):
        self.login(self.cajero)

    def test_desglose_cuadra_exacto_con_la_caja(self):
        ventas = self.ventas_variadas()
        corte = self.crear_corte(ventas)

        response = self.client.get(reverse("ventas:ticket_corte", args=[corte.id]))
        self.assertEqual(response.status_code, 200)
        ctx = response.context

        resumen = ctx["resumen_duenos"]
        filas = list(resumen.values())

        # Efectivo neto esperado: 120 + 150 + 900 + 0 + 80 + 10 + 100.
        self.assertEqual(ctx["total_efectivo"], D(1360))
        self.assertEqual(ctx["total_tarjeta"], D(150 + 100 + 20 + 170))
        self.assertIsInstance(ctx["total_efectivo"], Decimal)

        # Σ filas == totales de la caja, al centavo (Decimal, sin tolerancia).
        self.assertEqual(suma(filas, "efectivo"), ctx["total_efectivo"])
        self.assertEqual(suma(filas, "tarjeta"), ctx["total_tarjeta"])
        self.assertEqual(suma(filas, "total"), sum((v.total for v in ventas), CERO))
        self.assertEqual(ctx["total_general"], corte.total_general)

        # Servicios dentro de la fila de Rosa (Sucursal.dueño_servicios), no sueltos.
        self.assertEqual(set(resumen), {"Rosa", "Anais", "Yareli"})
        rosa = resumen["Rosa"]
        self.assertIsNotNone(rosa["servicios"])
        self.assertEqual(rosa["servicios"]["total"], D(50))
        self.assertEqual({c["concepto"] for c in rosa["servicios"]["conceptos"]},
                         {"Prod. sin registro", "Copias"})
        self.assertEqual(rosa["productos"] + rosa["servicios"]["total"], rosa["total"])

        # Montos ya con descuento: Anais 120 + 100 + 540 + 10 + 90.
        self.assertEqual(resumen["Anais"]["total"], D(860))

        # filas_duenos: la misma lista, en el mismo orden.
        self.assertEqual([f["nombre"] for f in ctx["filas_duenos"]], list(resumen))

        html = response.content.decode()
        self.assertIn("Caja Anais", html)
        self.assertIn("ROSA", html.upper())

    def test_corte_sin_ventas(self):
        corte = self.crear_corte([])
        response = self.client.get(reverse("ventas:ticket_corte", args=[corte.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["resumen_duenos"], {})
        self.assertEqual(response.context["total_efectivo"], CERO)
        self.assertContains(response, "Sin ventas en este corte.")


# ---------------------------------------------------------------------------
# Ticket de corte (texto térmico)
# ---------------------------------------------------------------------------

class TicketCorteTextoTest(ConsumidoresTestCase):

    def _montos(self, texto, etiqueta):
        """Σ de las líneas '  <etiqueta>: $X' del bloque por dueño."""
        total = CERO
        for linea in texto.splitlines():
            linea = linea.strip()
            if linea.startswith(etiqueta + ":"):
                total += Decimal(linea.split("$", 1)[1])
        return total

    def test_texto_cuadra_con_totales_caja(self):
        ventas = self.ventas_variadas()
        corte = self.crear_corte(ventas)
        tot = totales_caja(corte.ventas.all())

        texto = generar_texto_ticket(corte)

        for nombre in ("Rosa", "Anais", "Yareli"):
            self.assertIn(f"  {nombre}\n", texto)
        self.assertNotIn("  Servicios\n", texto)
        self.assertIn("DEBE HABER EN EFECTIVO", texto)
        self.assertTrue(any(l.startswith("TOTAL ") and l.endswith(f"${tot['efectivo']:.2f}")
                            for l in texto.splitlines()))

        # Las líneas por dueña suman exacto lo que hay en la caja. Las
        # dueñas dicen "En su caja"/"En su Clip"; las filas especiales
        # (aquí no hay) dirían "Efectivo"/"Tarjeta".
        efectivo = self._montos(texto, "En su caja") + self._montos(texto, "Efectivo")
        tarjeta = self._montos(texto, "En su Clip") + self._montos(texto, "Tarjeta")
        self.assertEqual(efectivo, tot["efectivo"])
        self.assertEqual(tarjeta, tot["tarjeta"])
        self.assertEqual(self._montos(texto, "Vendio"), tot["total"])
        # Caja + Clip == vendido en total. El corte nunca habla de deudas
        # entre dueñas.
        self.assertEqual(efectivo + tarjeta, self._montos(texto, "Vendio"))
        for s in ("CUENTAS ENTRE", "Le deben", "Debe:", "le debe"):
            self.assertNotIn(s, texto, s)

    def test_caja_borrada_usa_el_snapshot(self):
        caja_x = Caja.objects.create(sucursal=self.sucursal, nombre="Caja X")
        ventas = [
            self.crear_venta([self.renglon(self.prod_anais, 100), self.servicio("Copias", 20)],
                             efectivo=200, caja=caja_x),
        ]
        corte = self.crear_corte(ventas, caja=caja_x, caja_nombre="Caja X")
        caja_x.delete()   # FK SET_NULL en CorteCaja.caja y en Venta.caja
        corte.refresh_from_db()
        self.assertIsNone(corte.caja)

        texto = generar_texto_ticket(corte)

        self.assertIn("Caja: Caja X", texto)
        self.assertIn("DEBE HABER EN EFECTIVO", texto)
        self.assertTrue(any(l.startswith("TOTAL ") and l.endswith("$120.00")
                            for l in texto.splitlines()))
        # Sin caja no hay sucursal → los servicios no tienen responsable.
        self.assertIn(NOMBRE_SERVICIOS_SIN_RESPONSABLE, texto)

    def test_caja_borrada_sin_snapshot(self):
        caja_x = Caja.objects.create(sucursal=self.sucursal, nombre="Caja X")
        corte = self.crear_corte([], caja=caja_x, caja_nombre=None)
        caja_x.delete()
        corte.refresh_from_db()

        texto = generar_texto_ticket(corte)

        self.assertIn("Caja: Caja eliminada", texto)
        self.assertIn("DEBE HABER EN EFECTIVO", texto)


# ---------------------------------------------------------------------------
# Corte del día
# ---------------------------------------------------------------------------

class CorteDelDiaTest(ConsumidoresTestCase):

    def setUp(self):
        self.login(self.cajero)
        self.hoy = hoy_local()
        self.t0 = a_las(self.hoy, 12)

    def entrar_a_caja(self, caja):
        session = self.client.session
        session["caja_actual"] = caja.id
        session["sucursal_actual"] = caja.sucursal_id
        session.save()

    def cortar(self, t0, caja=None):
        """
        GET al corte con el reloj de la VISTA fijo en t0. Solo se reemplaza
        el `timezone` del módulo de la vista: el auto_now_add de CorteCaja
        sigue usando el reloj real, así se comprueba que fecha quede en t0.
        """
        self.entrar_a_caja(caja or self.caja_anais)
        reloj = SimpleNamespace(now=lambda: t0, localtime=timezone.localtime)
        antes = set(CorteCaja.objects.values_list("id", flat=True))
        with mock.patch("ventas.views.ticket_corte_views.timezone", reloj), \
                mock.patch("ventas.views.ticket_corte_views.imprimir_silencioso") as imprimir:
            response = self.client.get(reverse("ventas:corte_caja"))
        nuevos = CorteCaja.objects.exclude(id__in=antes)
        self.assertEqual(nuevos.count(), 1)
        corte = nuevos.get()
        self.assertRedirects(response, reverse("ventas:ticket_corte", args=[corte.id]),
                             fetch_redirect_response=False)
        imprimir.assert_called_once()
        return corte

    def assert_corte_consistente(self, corte, esperadas):
        self.assertEqual(set(corte.ventas.values_list("id", flat=True)), {v.id for v in esperadas})
        self.assertEqual(corte.total_general, sum((v.total for v in esperadas), CERO))
        self.assertEqual(corte.caja_nombre, "Caja Anais")
        self.assertEqual(corte.empleado, self.cajero)

        filas = desglose_por_dueno(ventas_para_desglose(corte.ventas.all()))
        self.assertEqual(corte.total_por_dueno, {f["nombre"]: float(f["total"]) for f in filas})
        for valor in corte.total_por_dueno.values():
            self.assertIsInstance(valor, float)
        self.assertAlmostEqual(sum(corte.total_por_dueno.values()), float(corte.total_general),
                               places=2)
        for v in corte.ventas.all():
            self.assertLessEqual(v.fecha, corte.fecha)

    def test_sin_corte_previo_toma_hoy_hasta_t0(self):
        ayer = self.crear_venta([self.renglon(self.prod_anais, 70)], efectivo=70,
                                fecha=a_las(self.hoy - timedelta(days=1), 11))
        v1 = self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500,
                              fecha=a_las(self.hoy, 10))
        v2 = self.crear_venta([self.renglon(self.prod_rosa, 200), self.servicio("Copias", 50)],
                              efectivo=100, tarjeta=150, descuento_pct=10, fecha=a_las(self.hoy, 11))
        justo_t0 = self.crear_venta([self.renglon(self.prod_yareli, 30)], tarjeta=30, fecha=self.t0)
        despues = self.crear_venta([self.renglon(self.prod_yareli, 40)], efectivo=40,
                                   fecha=self.t0 + timedelta(minutes=30))
        otra_caja = self.crear_venta([self.renglon(self.prod_anais, 90)], efectivo=90,
                                     caja=self.caja_fabiola, fecha=a_las(self.hoy, 11))

        corte = self.cortar(self.t0)
        corte.refresh_from_db()

        self.assertEqual(corte.fecha, self.t0)
        self.assert_corte_consistente(corte, [v1, v2, justo_t0])
        for fuera in (ayer, despues, otra_caja):
            self.assertFalse(corte.ventas.filter(id=fuera.id).exists())
        # Servicios dentro de Rosa; ya con descuento: 250 * 0.9 = 225.
        self.assertEqual(corte.total_por_dueno, {"Anais": 120.0, "Rosa": 225.0, "Yareli": 30.0})

        # La sesión se limpia como antes.
        self.assertNotIn("caja_actual", self.client.session)
        self.assertNotIn("sucursal_actual", self.client.session)

    def test_con_corte_previo_y_la_venta_tardia_cae_en_el_siguiente(self):
        previo = self.crear_corte([])
        CorteCaja.objects.filter(pk=previo.pk).update(fecha=a_las(self.hoy, 9))
        antes_del_previo = self.crear_venta([self.renglon(self.prod_anais, 10)], efectivo=10,
                                            fecha=a_las(self.hoy, 8))
        v1 = self.crear_venta([self.renglon(self.prod_anais, 600), self.renglon(self.prod_yareli, 400)],
                              efectivo=1000, descuento_pct=10, fecha=a_las(self.hoy, 10))
        v2 = self.crear_venta([self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
                               self.renglon(self.prod_yareli, 10)], efectivo=10, tarjeta=20,
                              fecha=a_las(self.hoy, 11, 59, 59))
        # "Entra durante el corte": después de t0 (antes del INSERT del corte).
        tardia = self.crear_venta([self.renglon(self.prod_rosa, 55)], efectivo=55,
                                  fecha=self.t0 + timedelta(seconds=1))

        corte = self.cortar(self.t0)
        corte.refresh_from_db()

        self.assertEqual(corte.fecha, self.t0)
        self.assert_corte_consistente(corte, [v1, v2])
        self.assertFalse(corte.ventas.filter(id=antes_del_previo.id).exists())
        self.assertFalse(corte.ventas.filter(id=tardia.id).exists())

        # El siguiente corte arranca en t0 exacto: la venta tardía no queda huérfana.
        t1 = a_las(self.hoy, 13)
        siguiente = self.cortar(t1)
        siguiente.refresh_from_db()
        self.assertEqual(siguiente.fecha, t1)
        self.assertEqual(set(siguiente.ventas.values_list("id", flat=True)), {tardia.id})
        self.assertEqual(siguiente.total_por_dueno, {"Rosa": 55.0})

    def test_la_pagina_del_ticket_cuadra_con_el_corte(self):
        self.ventas_variadas(fecha=a_las(self.hoy, 10))
        corte = self.cortar(self.t0)

        response = self.client.get(reverse("ventas:ticket_corte", args=[corte.id]))
        self.assertEqual(response.status_code, 200)
        resumen = response.context["resumen_duenos"]
        self.assertEqual(suma(resumen.values(), "total"), corte.total_general)
        self.assertEqual({n: float(f["total"]) for n, f in resumen.items()}, corte.total_por_dueno)


class GenerarCorteParaFechaTest(ConsumidoresTestCase):

    def test_total_por_dueno_con_reparto(self):
        ayer = hoy_local() - timedelta(days=1)
        ventas = self.ventas_variadas(fecha=a_las(ayer, 15))

        corte = generar_corte_para_fecha(self.caja_anais, ayer)
        corte.refresh_from_db()

        self.assertEqual(corte.caja_nombre, "Caja Anais")
        self.assertEqual(corte.total_general, sum((v.total for v in ventas), CERO))
        self.assertEqual(set(corte.total_por_dueno), {"Rosa", "Anais", "Yareli"})
        self.assertAlmostEqual(sum(corte.total_por_dueno.values()), float(corte.total_general),
                               places=2)
        self.assertEqual(corte.total_por_dueno["Anais"], 860.0)
        self.assertEqual(corte.ventas.count(), len(ventas))

    def corte_manual(self, ventas):
        corte = CorteCaja.objects.create(caja=self.caja_anais, caja_nombre="Caja Anais", empleado=self.cajero,
                                         total_general=0, total_por_dueno={})
        corte.ventas.set(ventas)
        return corte

    def test_no_repite_ventas_de_un_corte_manual(self):
        # En oct-2026 el automático repetía las ventas del corte manual: 119
        # ventas en dos cortes y $44k de más al sumar tickets.
        ayer = hoy_local() - timedelta(days=1)
        v1 = self.crear_venta([self.renglon(self.prod_anais, 100)], efectivo=100, fecha=a_las(ayer, 11))
        self.corte_manual([v1])
        v2 = self.crear_venta([self.renglon(self.prod_yareli, 50)], efectivo=50, fecha=a_las(ayer, 15))

        auto = generar_corte_para_fecha(self.caja_anais, ayer)
        self.assertEqual(set(auto.ventas.values_list("id", flat=True)), {v2.id})
        self.assertEqual(auto.total_general, v2.total)

    def test_no_se_crea_si_todo_ya_se_corto(self):
        ayer = hoy_local() - timedelta(days=1)
        v1 = self.crear_venta([self.renglon(self.prod_anais, 100)], efectivo=100, fecha=a_las(ayer, 11))
        self.corte_manual([v1])
        cortes = CorteCaja.objects.count()

        self.assertIsNone(generar_corte_para_fecha(self.caja_anais, ayer))
        self.assertEqual(CorteCaja.objects.count(), cortes)

    def test_entrar_a_la_caja_no_crea_corte_repetido(self):
        # Corte manual ayer a las 3pm hora local con todo lo del día: al
        # entrar hoy a la caja no se genera otro corte de ayer.
        ayer = hoy_local() - timedelta(days=1)
        v1 = self.crear_venta([self.renglon(self.prod_anais, 100)], efectivo=100, fecha=a_las(ayer, 11))
        manual = self.corte_manual([v1])
        CorteCaja.objects.filter(pk=manual.pk).update(fecha=a_las(ayer, 15))
        cortes = CorteCaja.objects.count()

        self.login(self.cajero)
        resp = self.client.post(reverse("sucursales:entrar_caja_ajax"),
                                {"caja_id": self.caja_anais.id, "password": "x"})
        self.assertEqual(resp.json(), {"ok": True})
        self.assertEqual(CorteCaja.objects.count(), cortes)


# ---------------------------------------------------------------------------
# "¿Cuánto llevo yo?" (resumen_ventas_dueno_por_caja / _por_fecha)
# ---------------------------------------------------------------------------

class ResumenDuenoPorCajaTest(ConsumidoresTestCase):

    def setUp(self):
        self.hoy = hoy_local()
        self.mediodia = a_las(self.hoy, 12)

    def test_descuento_mixto_sin_caja_y_sin_servicios(self):
        # Anais 600 + Yareli 400 con 10% → Anais 540, todo en efectivo (cambio 100).
        self.crear_venta([self.renglon(self.prod_anais, 600), self.renglon(self.prod_yareli, 400)],
                         efectivo=1000, descuento_pct=10, caja=self.caja_anais, fecha=self.mediodia)
        # Mixto en la otra caja: Anais 100 (50 efectivo + 50 tarjeta).
        self.crear_venta([self.renglon(self.prod_anais, 100)], efectivo=50, tarjeta=50,
                         caja=self.caja_fabiola, fecha=self.mediodia)
        # Venta sin caja: no cuenta.
        sin_caja = self.crear_venta([self.renglon(self.prod_anais, 77)], efectivo=77,
                                    fecha=self.mediodia)
        Venta.objects.filter(pk=sin_caja.pk).update(caja=None)
        # Otro día: no cuenta.
        self.crear_venta([self.renglon(self.prod_anais, 33)], efectivo=33,
                         fecha=self.mediodia - timedelta(days=1))
        # Rosa 80 + servicio 20 + sin registro 15: a la responsable de
        # servicios se le suman, como en el corte, y se desglosan.
        self.crear_venta([self.renglon(self.prod_rosa, 80), self.servicio("Copias", 20),
                          self.servicio("Prod. sin registro", 15)],
                         tarjeta=115, caja=self.caja_fabiola, fecha=self.mediodia)
        # Venta de puro servicio (ningún producto de Rosa): también es suya.
        self.crear_venta([self.servicio("Copias", 5)], efectivo=5, caja=self.caja_anais, fecha=self.mediodia)

        anais = resumen_ventas_dueno_por_caja(self.anais, self.hoy)

        self.assertEqual([d["caja"] for d in anais], ["Caja Anais", "Caja Fabiola"])
        caja_a, caja_f = anais
        self.assertEqual(caja_a["caja_id"], self.caja_anais.id)
        self.assertEqual(caja_a["sucursal"], "Sucursal Centro")
        for d in anais:
            for campo in ("efectivo", "tarjeta", "total"):
                self.assertIsInstance(d[campo], float)
        self.assertEqual((caja_a["total"], caja_a["efectivo"], caja_a["tarjeta"]), (540.0, 540.0, 0.0))
        self.assertEqual((caja_f["total"], caja_f["efectivo"], caja_f["tarjeta"]), (100.0, 50.0, 50.0))

        # Saldo 0: en las dos cuentas Anais es la que más vende (recibe y
        # cobra la tarjeta en su Clip) y el efectivo alcanza para Yareli.
        for d in anais:
            self.assertEqual(d["saldo"], 0.0)
        self.assertEqual(resumen_ventas_dueno_por_fecha(self.anais, self.hoy),
                         {"efectivo": 590.0, "tarjeta": 50.0, "total": 640.0, "saldo": 0.0,
                          "productos": 640.0, "servicios": 0.0, "sin_registro": 0.0,
                          "salidas": 0.0, "en_caja": 590.0, "del_fondo": 0.0})

        rosa = {d["caja"]: d for d in resumen_ventas_dueno_por_caja(self.rosa, self.hoy)}
        self.assertEqual(set(rosa), {"Caja Anais", "Caja Fabiola"})
        f = rosa["Caja Fabiola"]
        self.assertEqual((f["total"], f["tarjeta"], f["productos"], f["servicios"], f["sin_registro"]),
                         (115.0, 115.0, 80.0, 20.0, 15.0))
        a = rosa["Caja Anais"]
        self.assertEqual((a["total"], a["efectivo"], a["productos"], a["servicios"]), (5.0, 5.0, 0.0, 5.0))
        self.assertEqual(resumen_ventas_dueno_por_fecha(self.rosa, self.hoy),
                         {"efectivo": 5.0, "tarjeta": 115.0, "total": 120.0, "saldo": 0.0,
                          "productos": 80.0, "servicios": 25.0, "sin_registro": 15.0,
                          "salidas": 0.0, "en_caja": 5.0, "del_fondo": 0.0})

    def test_coincide_con_el_corte(self):
        # El desglose de "¿Cuánto llevo yo?" y el del corte salen del mismo reparto.
        ventas = self.ventas_variadas(fecha=self.mediodia)
        filas = {f["nombre"]: f for f in desglose_por_dueno(
            ventas_para_desglose(Venta.objects.filter(pk__in=[v.pk for v in ventas])))}
        for emp, nombre in ((self.anais, "Anais"), (self.yareli, "Yareli")):
            r = resumen_ventas_dueno_por_fecha(emp, self.hoy)
            self.assertEqual(r["total"], float(filas[nombre]["total"]))
            self.assertEqual(r["efectivo"], float(filas[nombre]["efectivo"]))
            self.assertEqual(r["tarjeta"], float(filas[nombre]["tarjeta"]))
            self.assertEqual(r["saldo"], float(filas[nombre]["saldo"]))
        # Rosa (responsable de servicios): igual que su fila del corte, con
        # sus servicios dentro y desglosados.
        r = resumen_ventas_dueno_por_fecha(self.rosa, self.hoy)
        for campo in ("total", "efectivo", "tarjeta", "saldo", "productos"):
            self.assertEqual(r[campo], float(filas["Rosa"][campo]), campo)
        serv = filas["Rosa"]["servicios"]
        self.assertGreater(r["servicios"] + r["sin_registro"], 0)
        self.assertEqual(r["servicios"] + r["sin_registro"], float(serv["total"]))
        self.assertEqual(r["total"], round(r["productos"] + r["servicios"] + r["sin_registro"], 2))


# ---------------------------------------------------------------------------
# Dashboard de la dueña: "Ventas del mes" y cards/API de hoy
# ---------------------------------------------------------------------------

class DashboardDuenoTest(ConsumidoresTestCase):

    def setUp(self):
        self.login(self.anais)
        self.hoy = hoy_local()

    def dashboard(self):
        response = self.client.get(reverse("tienda_temp:dashboard_dueno"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_ventas_del_mes_ya_descontadas(self):
        primero = self.hoy.replace(day=1)
        # 333 + 667 con 10% → Anais 299.70 (con montos enteros SQLite
        # dividiría entero y daría 299).
        self.crear_venta([self.renglon(self.prod_anais, 333), self.renglon(self.prod_yareli, 667)],
                         efectivo=900, descuento_pct=10, fecha=a_las(primero, 12))
        self.crear_venta([self.renglon(self.prod_anais, 250), self.regalo(self.prod_anais)],
                         tarjeta=250, caja=self.caja_fabiola, fecha=a_las(self.hoy, 12))
        # Venta de puro regalo (subtotal 0): no debe dividir entre 0.
        self.crear_venta([self.regalo(self.prod_anais)], fecha=a_las(self.hoy, 12))
        # Mes anterior y productos de otra dueña: no cuentan.
        self.crear_venta([self.renglon(self.prod_anais, 1000)], efectivo=1000,
                         fecha=a_las(primero - timedelta(days=1), 12))
        self.crear_venta([self.renglon(self.prod_yareli, 500)], efectivo=500,
                         fecha=a_las(self.hoy, 12))

        valor = self.dashboard().context["ventas_mes_dueno"]

        self.assertIsInstance(valor, Decimal)
        self.assertEqual(valor, D("549.70"))
        dias = {primero, self.hoy}
        esperado = sum(resumen_ventas_dueno_por_fecha(self.anais, d)["total"] for d in dias)
        self.assertAlmostEqual(float(valor), esperado, delta=0.01)

    def test_ventas_del_mes_sin_ventas(self):
        self.assertEqual(self.dashboard().context["ventas_mes_dueno"], CERO)

    def test_responsable_de_servicios_ve_su_corte_desglosado(self):
        hoy = a_las(self.hoy, 12)
        # Rosa 200 + copias 50 + sin registro 30 + Anais 100, con 10% → 342 total
        # (Rosa 180 + copias 45 + sin registro 27, Anais 90); más copias 10.
        self.crear_venta([self.renglon(self.prod_rosa, 200), self.servicio("Copias", 50),
                          self.servicio("Prod. sin registro", 30), self.renglon(self.prod_anais, 100)],
                         efectivo=400, descuento_pct=10, caja=self.caja_fabiola, fecha=hoy)
        self.crear_venta([self.servicio("Copias", 10)], tarjeta=10, fecha=hoy)

        self.login(self.rosa)
        response = self.dashboard()
        ctx = response.context
        self.assertTrue(ctx["es_responsable_servicios"])
        self.assertEqual((ctx["ventas_mes_dueno"], ctx["ventas_mes_servicios"], ctx["ventas_mes_sin_registro"]),
                         (D(180), D(55), D(27)))
        self.assertEqual(ctx["ventas_mes_total"], D(262))
        # El mes cuadra con lo que suman sus filas del corte.
        filas = {f["nombre"]: f for f in desglose_por_dueno(ventas_para_desglose(Venta.objects.all()))}
        self.assertEqual(ctx["ventas_mes_total"], filas["Rosa"]["total"])

        hoy_rosa = ctx["ventas_hoy_dueno"]
        self.assertEqual((hoy_rosa["total"], hoy_rosa["productos"], hoy_rosa["servicios"], hoy_rosa["sin_registro"]),
                         (262.0, 180.0, 55.0, 27.0))
        self.assertEqual(self.client.get(reverse("ventas:api_ventas_hoy")).json()["mis_ventas"], hoy_rosa)
        html = response.content.decode()
        for s in ("Esto has vendido durante este mes", 'id="dueno-ahorita-servicios"', "Prod. sin registro: $"):
            self.assertIn(s, html)

        # A las demás no se les desglosa nada.
        self.login(self.anais)
        response = self.dashboard()
        self.assertFalse(response.context["es_responsable_servicios"])
        self.assertEqual(response.context["ventas_mes_total"], D(90))
        html = response.content.decode()
        self.assertIn("Esto has vendido de tus productos durante este mes", html)
        self.assertNotIn('id="dueno-ahorita-servicios"', html)

    def test_dashboard_api_y_corte_coinciden(self):
        mediodia = a_las(self.hoy, 12)
        ventas_a = self.ventas_variadas(caja=self.caja_anais, fecha=mediodia)
        ventas_f = [
            self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 200)],
                             efectivo=150, tarjeta=150, descuento_pct=10, caja=self.caja_fabiola,
                             fecha=mediodia),
            self.crear_venta([self.servicio("Copias", 12), self.renglon(self.prod_anais, 45)],
                             efectivo=100, caja=self.caja_fabiola, fecha=mediodia),
        ]

        api = self.client.get(reverse("ventas:api_ventas_hoy")).json()
        response = self.dashboard()

        api_cajas = {c["caja"]: c for c in api["cajas"]}
        dash_cajas = {c["nombre"]: c for c in response.context["ventas_por_sucursal"][0]["cajas"]}
        self.assertEqual(set(api_cajas), {"Caja Anais", "Caja Fabiola"})
        for nombre, ventas in (("Caja Anais", ventas_a), ("Caja Fabiola", ventas_f)):
            tot = totales_caja(Venta.objects.filter(pk__in=[v.pk for v in ventas]))
            for campo in ("efectivo", "tarjeta", "total"):
                self.assertIsInstance(api_cajas[nombre][campo], float)
                self.assertEqual(dash_cajas[nombre][campo], tot[campo], f"{nombre}/{campo}")
                self.assertEqual(api_cajas[nombre][campo], float(tot[campo]), f"{nombre}/{campo}")

        # "¿Cuánto llevo yo?": dashboard y API dicen lo mismo, caja por caja.
        api_mis = {c["caja"]: c for c in api["mis_cajas"]}
        for d in response.context["ventas_hoy_dueno_por_caja"]:
            for campo in ("efectivo", "tarjeta", "total", "saldo"):
                self.assertEqual(d[campo], api_mis[d["caja"]][campo])
        self.assertEqual(api["mis_ventas"], response.context["ventas_hoy_dueno"])
        # Anais: 860 (variadas) + 90 + 45.
        self.assertEqual(api["mis_ventas"]["total"], 995.0)

        chart = response.context["ventas_chart_sucursal"][0]
        self.assertEqual(chart, api["chart"][0])
        self.assertNotIn("Decimal(", response.content.decode())


class CuantoLlevoYoPagoEnSecoTest(ConsumidoresTestCase):
    """
    "¿Cuánto llevo yo?" con la venta del dueño: gelish $100 (Anais) + tinte
    $50 (Yareli) + $10 (Rosa). Anais es la que más vendió → cobra toda la
    tarjeta en SU Clip y les paga a las demás en efectivo en el momento.
    Ya no hay deudas entre dueñas en ninguna parte del dashboard.
    """

    CAMPOS = ("efectivo", "tarjeta", "total")

    def setUp(self):
        self.hoy = hoy_local()

    def venta_del_dueno(self, efectivo, tarjeta):
        return self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
                                 self.renglon(self.prod_rosa, 10)], efectivo=efectivo, tarjeta=tarjeta,
                                caja=self.caja_anais, fecha=a_las(self.hoy, 12), pago_en_seco=True)

    def ver(self, empleado):
        self.login(empleado)
        api = self.client.get(reverse("ventas:api_ventas_hoy")).json()
        response = self.client.get(reverse("tienda_temp:dashboard_dueno"))
        self.assertEqual(response.status_code, 200)
        return api, response

    def montos(self, d):
        return {c: d[c] for c in self.CAMPOS}

    def assert_sin_deudas(self, api, html):
        self.assertNotIn("mis_deudas", api)
        for s in ("Cuentas con otras dueñas", "card-cuentas-duenas", "init-mis-deudas", "Ya se pagó",
                  "Debes $", "Te deben $", "le debes", "te debe"):
            self.assertNotIn(s, html, s)

    def test_todo_tarjeta_se_paga_en_el_momento(self):
        self.venta_del_dueno(efectivo=0, tarjeta=160)

        # Anais: vendió 100; los 160 entraron a su Clip y de su caja salieron
        # 60 (50 a Yareli, 10 a Rosa).
        api, response = self.ver(self.anais)
        esperado = {"efectivo": -60.0, "tarjeta": 160.0, "total": 100.0}
        self.assertEqual(self.montos(api["mis_ventas"]), esperado)
        self.assertEqual(self.montos(response.context["ventas_hoy_dueno"]), esperado)
        self.assertEqual(api["mis_ventas"]["saldo"], 0.0)
        html = response.content.decode()
        for s in ("En tu caja (efectivo)", "En tu Clip (tarjeta)", "Vendiste hoy"):
            self.assertIn(s, html)
        self.assert_sin_deudas(api, html)

        # Yareli: sus 50 le llegaron en efectivo a su caja.
        api, response = self.ver(self.yareli)
        esperado = {"efectivo": 50.0, "tarjeta": 0.0, "total": 50.0}
        self.assertEqual(self.montos(api["mis_ventas"]), esperado)
        self.assert_sin_deudas(api, response.content.decode())

    def test_mixto(self):
        # 70 tarjeta + 90 efectivo: Anais 30 caja + 70 Clip = 100 vendido.
        self.venta_del_dueno(efectivo=90, tarjeta=70)
        api, response = self.ver(self.anais)
        self.assertEqual(self.montos(api["mis_ventas"]), {"efectivo": 30.0, "tarjeta": 70.0, "total": 100.0})
        self.assert_sin_deudas(api, response.content.decode())
