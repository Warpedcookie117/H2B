"""
Formato del ticket de corte (web y térmico):
  - Los servicios (incluido "Prod. sin registro" del cobro rápido) van DENTRO
    del recuadro de la responsable de servicios, desglosados por concepto.
  - El bloque negro dice cuánto efectivo debe haber POR CAJÓN de dueña y sus
    líneas suman exacto el efectivo de la caja.
  - Lo que dice cada cajón coincide al centavo con lo que el modal del POS le
    dijo a cada dueña en cada cobro.
  - Una caja borrada ya no tumba la página (NoReverseMatch).
  - Lo que se deben las dueñas entre ellas NO sale en el corte (lo ve e
    imprime la cajera): solo en el dashboard de cada dueña.
"""
import re
from decimal import Decimal

from django.urls import reverse

from sucursales.models import Caja, Sucursal
from ventas.models import CorteCaja
from ventas.services.reparto import (
    NOMBRE_SERVICIOS_SIN_RESPONSABLE,
    NOMBRE_SIN_DUENO,
    desglose_por_dueno,
    reparto_efectivo_venta,
    totales_caja,
    ventas_para_desglose,
)
from ventas.services.ticket_service import ANCHO, generar_texto_ticket
from ventas.tests.base import D, VentasBaseTestCase

CERO = Decimal("0.00")
MONTO = re.compile(r"\$(-?\d+\.\d{2})")
AVISO_WEB = "Sin dueña · avisar a la encargada"
AVISO_TERMICO = "  (sin duena: avisar)"


def texto_plano(html):
    """HTML → texto visible en una sola línea (sin comentarios, scripts ni etiquetas)."""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    return " ".join(html.split())


def centavos(valor):
    """Decimal o float de 2 decimales → entero de centavos, exacto."""
    return int(D(valor) * 100)


def renglon(etiqueta, monto):
    """Línea térmica esperada: etiqueta a la izquierda, monto pegado a la derecha."""
    precio = f"${D(monto):.2f}"
    return etiqueta + precio.rjust(ANCHO - len(etiqueta))


class FormatoCorteTestCase(VentasBaseTestCase):

    def setUp(self):
        self.login(self.cajero)

    # ------------------------------------------------------------------
    # Las deudas entre dueñas son sensibles: nunca en el corte
    # ------------------------------------------------------------------

    def assert_sin_deudas_web(self, html_o_texto):
        texto = texto_plano(html_o_texto) if "<" in html_o_texto else html_o_texto
        for s in ("CUENTAS ENTRE", "Le deben", "➡ Debe", "Debe:", "le debe", "Nadie le debe"):
            self.assertNotIn(s, texto, s)

    def assert_sin_deudas_termico(self, texto):
        for s in ("CUENTAS ENTRE", "Le deben", "Debe:", "le debe", "Nadie le debe"):
            self.assertNotIn(s, texto, s)

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

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

    def ventas_con_servicios(self, caja=None):
        """
        Las 3 dueñas, servicios "Prod. sin registro" (2 renglones en un cobro
        + otro en otra cuenta) y "Copias", un regalo y una mixta con descuento.
        Totales: Anais 220, Rosa 260 + 120 de servicios, Yareli 150.
        Efectivo neto 520, tarjeta 230.
        """
        kw = {"caja": caja}
        return [
            # Anais 120 pagado con 500 → cambio 380.
            self.crear_venta([self.renglon(self.prod_anais, 120)], efectivo=500, **kw),
            # Cobro rápido: 2 renglones "Prod. sin registro" + Yareli 50; paga 200 → cambio 90.
            self.crear_venta([self.servicio("Prod. sin registro", 35, cantidad=7),
                              self.servicio("Prod. sin registro", 25, cantidad=5),
                              self.renglon(self.prod_yareli, 50)], efectivo=200, **kw),
            # 30 copias + Rosa 80, todo con tarjeta.
            self.crear_venta([self.servicio("Copias", 15, cantidad=30), self.renglon(self.prod_rosa, 80)],
                             tarjeta=95, **kw),
            # Regalo en $0 + Rosa 80; paga 100 → cambio 20.
            self.crear_venta([self.regalo(self.prod_yareli), self.renglon(self.prod_rosa, 80)],
                             efectivo=100, **kw),
            # Mixta con 10%: 350 → 315 = 200 efectivo + 115 tarjeta.
            self.crear_venta([self.renglon(self.prod_rosa, 100), self.renglon(self.prod_anais, 100),
                              self.renglon(self.prod_yareli, 100),
                              self.servicio("Prod. sin registro", 50, cantidad=2)],
                             efectivo=200, tarjeta=115, descuento_pct=10, **kw),
            # 3 dueñas iguales, 10 efectivo + 20 tarjeta: centavos por repartir.
            self.crear_venta([self.renglon(self.prod_rosa, 10), self.renglon(self.prod_anais, 10),
                              self.renglon(self.prod_yareli, 10)], efectivo=10, tarjeta=20, **kw),
        ]

    # ------------------------------------------------------------------
    # Lectura de la página
    # ------------------------------------------------------------------

    def pagina(self, corte):
        response = self.client.get(reverse("ventas:ticket_corte", args=[corte.id]))
        self.assertEqual(response.status_code, 200)
        return response, texto_plano(response.content.decode())

    def seccion_duenos(self, texto):
        return texto[texto.index("VENTAS POR DUEÑO"):texto.index("DETALLE DEL CORTE")]

    def recuadros(self, texto, filas):
        """nombre → texto de su recuadro (de su nombre al nombre del siguiente)."""
        sec = self.seccion_duenos(texto)
        posiciones, desde = [], 0
        for f in filas:
            i = sec.index(f["nombre"], desde)
            posiciones.append(i)
            desde = i + len(f["nombre"])
        posiciones.append(len(sec))
        return {f["nombre"]: sec[posiciones[n]:posiciones[n + 1]] for n, f in enumerate(filas)}

    def bloque_cajones(self, texto):
        """Lee el bloque negro "DEBE HABER EN EFECTIVO POR CAJÓN"."""
        ini = texto.index("DEBE HABER EN EFECTIVO POR CAJÓN")
        bloque = texto[ini:texto.index("CUENTA BIEN.", ini)]
        cajones = {
            nombre: (D(monto), bool(incluye))
            for nombre, incluye, monto in re.findall(
                r"Cajón (\S+)( \(incluye servicios\))? \$(-?\d+\.\d{2})", bloque)
        }
        especiales = {
            nombre: D(monto)
            for nombre, monto in re.findall(
                r"⚠ (.+?) " + re.escape(AVISO_WEB) + r" \$(-?\d+\.\d{2})", bloque)
        }
        return {
            "cajones": cajones,
            "especiales": especiales,
            "total": D(re.search(r"TOTAL \$(-?\d+\.\d{2})", bloque).group(1)),
            "montos": [D(m) for m in MONTO.findall(bloque)],
        }

    def bloque_cajones_termico(self, lineas):
        """(líneas entre "POR CAJON:" y TOTAL, línea de TOTAL) del ticket térmico."""
        i_cajon = next(i for i, l in enumerate(lineas) if l.strip() == "POR CAJON:")
        i_total = next(i for i in range(i_cajon, len(lineas)) if lineas[i].startswith("TOTAL "))
        return lineas[i_cajon + 1:i_total], lineas[i_total]


# ---------------------------------------------------------------------------
# Vista web
# ---------------------------------------------------------------------------

class TicketCorteWebFormatoTest(FormatoCorteTestCase):

    def test_servicios_dentro_del_recuadro_de_la_responsable(self):
        corte = self.crear_corte(self.ventas_con_servicios())
        response, texto = self.pagina(corte)

        filas = response.context["filas_duenos"]
        self.assertEqual([f["nombre"] for f in filas], ["Anais", "Rosa", "Yareli"])
        rosa = filas[1]
        serv = rosa["servicios"]
        self.assertEqual((rosa["total"], rosa["productos"], serv["total"]), (D(380), D(260), D(120)))
        self.assertEqual([(c["concepto"], c["cantidad"], c["total"]) for c in serv["conceptos"]],
                         [("Prod. sin registro", 14, D(105)), ("Copias", 30, D(15))])

        # Todo lo de servicios aparece UNA vez, después del nombre de Rosa y
        # antes del recuadro siguiente (Yareli).
        sec = self.seccion_duenos(texto)
        i_rosa = sec.index("Rosa")
        i_yareli = sec.index("Yareli", i_rosa)
        for s in ("Sus productos", "Productos sin registro (x14)", "🛠 Servicios ", "Copias (x30)",
                  "Servicios agregados (incl. sin registro)"):
            self.assertEqual(sec.count(s), 1, s)
            self.assertTrue(i_rosa < sec.index(s) < i_yareli, s)

        # Sin registro va aparte de los servicios por concepto.
        rec = self.recuadros(texto, filas)
        # Regla de la receptora (reparto._repartir_fisico), a mano:
        #   Rosa vendió 60 + 95 + 80 + 135 + 10 = 380.
        #   Su caja: 60 (cobro rápido, ella recibe) + 80 (regalo) + 20 (sobra
        #   de la mixta: 200 - 90 Anais - 90 Yareli) = 160.
        #   Su Clip: 95 + 115 + 20 = 230 (es la que más vende en esas cuentas).
        #   Última venta (3 × 10, 10 efectivo + 20 tarjeta): empate de base,
        #   Rosa recibe por prioridad 1 y cobra los 20 en su Clip; a Anais y
        #   Yareli solo les alcanzan 5 en efectivo → Rosa les debe 5 a cada una.
        #   380 = 160 + 230 - 10. Esa deuda ya NO se muestra en el corte:
        #   después de "En su Clip" sigue directo lo siguiente del recuadro.
        self.assertIn("Rosa 🛍 Vendió $380.00 💵 En su caja $160.00 💳 En su Clip $230.00 📦 Sus productos",
                      rec["Rosa"])
        self.assertIn("Anais 🛍 Vendió $220.00 💵 En su caja $215.00 💳 En su Clip $0.00", rec["Anais"])
        self.assertIn("Yareli 🛍 Vendió $150.00 💵 En su caja $145.00 💳 En su Clip $0.00", rec["Yareli"])
        self.assert_sin_deudas_web(texto)
        self.assertIn("📦 Sus productos $260.00", rec["Rosa"])
        self.assertIn("🧾 Productos sin registro (x14) $105.00", rec["Rosa"])
        self.assertIn("🛠 Servicios $15.00", rec["Rosa"])
        self.assertIn("· Copias (x30) $15.00", rec["Rosa"])
        self.assertNotIn("· Prod. sin registro", rec["Rosa"])
        self.assertIn("Servicios agregados (incl. sin registro) $120.00", rec["Rosa"])
        for nombre in ("Anais", "Yareli"):
            self.assertNotIn("Servicios agregados", rec[nombre])
            self.assertNotIn("Sus productos", rec[nombre])
            self.assertNotIn(AVISO_WEB, rec[nombre])

        # Ningún recuadro suelto de servicios.
        html = response.content.decode()
        self.assertNotIn("Servicio: Prod. sin registro", html)
        self.assertNotIn("Servicio:", sec)
        self.assertNotIn(NOMBRE_SERVICIOS_SIN_RESPONSABLE, html)

    def test_bloque_por_cajon_suma_exacto_el_efectivo(self):
        corte = self.crear_corte(self.ventas_con_servicios())
        response, texto = self.pagina(corte)
        ctx = response.context
        filas = ctx["filas_duenos"]

        b = self.bloque_cajones(texto)
        self.assertEqual(b["total"], ctx["total_efectivo"])
        self.assertEqual(b["total"], D(520))
        # Una línea por cajón, en el orden de los recuadros, con la nota de
        # servicios solo en el de Rosa.
        self.assertEqual(list(b["cajones"]), ["Anais", "Rosa", "Yareli"])
        self.assertEqual(b["cajones"], {f["nombre"]: (f["efectivo"], f["servicios"] is not None)
                                        for f in filas})
        self.assertEqual([n for n, (_, incluye) in b["cajones"].items() if incluye], ["Rosa"])
        self.assertEqual(b["especiales"], {})
        # Σ líneas == TOTAL exacto, y no hay montos de más en el bloque.
        self.assertEqual(sum((m for m, _ in b["cajones"].values()), CERO), b["total"])
        self.assertEqual(len(b["montos"]), len(b["cajones"]) + 1)
        # DETALLE DEL CORTE se queda.
        self.assertIn("💵 TOTAL EFECTIVO EN CAJA $520.00", texto)
        self.assertIn("💳 TOTAL TARJETA EN CAJA $230.00", texto)
        # El "EN CAJA X DEBE HABER $Y" de un solo monto ya no existe en la web.
        self.assertNotIn("EN CAJA ANAIS DEBE HABER", texto.upper())

    def test_cada_cajon_coincide_con_lo_que_dijo_el_modal_del_pos(self):
        ventas = self.ventas_con_servicios() + [
            # Centavos: 3 dueñas casi iguales + servicio; 50 efectivo + 60 tarjeta.
            self.crear_venta([self.renglon(self.prod_rosa, "33.33"), self.renglon(self.prod_anais, "33.33"),
                              self.renglon(self.prod_yareli, "33.34"), self.servicio("Copias", "7.77")],
                             efectivo=50, tarjeta=60),
            # 7% de descuento sobre montos raros, paga con 100.
            self.crear_venta([self.renglon(self.prod_anais, "59.97", cantidad=3),
                              self.renglon(self.prod_yareli, "0.01")], efectivo=100, descuento_pct=7),
            # El servicio es lo mayor de la cuenta: Rosa recibe y da cambio.
            self.crear_venta([self.servicio("Prod. sin registro", "12.50"), self.renglon(self.prod_rosa, "7.50"),
                              self.renglon(self.prod_anais, "7.50")], efectivo=30),
        ]
        corte = self.crear_corte(ventas)
        response, texto = self.pagina(corte)

        # Lo que el modal le dijo a cada dueña, venta por venta, acumulado.
        modal = {}
        for v in ventas:
            r = reparto_efectivo_venta(v.id)
            self.assertEqual(r["sin_cajon"], 0.0)
            if r["receptora"] is None:
                continue
            rid = r["receptora"]["empleado_id"]
            modal[rid] = modal.get(rid, 0) + centavos(r["queda_receptora"])
            for p in r["pasar"]:
                modal[p["empleado_id"]] = modal.get(p["empleado_id"], 0) + centavos(p["efectivo"])
        modal = {k: c for k, c in modal.items() if c}

        filas = response.context["filas_duenos"]
        self.assertFalse(any(f["especial"] for f in filas))
        self.assertEqual({f["empleado_id"]: centavos(f["efectivo"]) for f in filas if f["efectivo"]}, modal)

        # Y es exactamente lo que se ve en el bloque por cajón.
        ids = {"Anais": self.anais.id, "Rosa": self.rosa.id, "Yareli": self.yareli.id}
        b = self.bloque_cajones(texto)
        self.assertEqual({ids[n]: centavos(m) for n, (m, _) in b["cajones"].items()}, modal)
        self.assertEqual(sum(modal.values()), centavos(response.context["total_efectivo"]))
        self.assertEqual(centavos(b["total"]), sum(modal.values()))

    def test_corte_sin_servicios_se_ve_como_antes(self):
        ventas = [
            self.crear_venta([self.renglon(self.prod_anais, 100)], efectivo=100),
            self.crear_venta([self.renglon(self.prod_rosa, 60), self.renglon(self.prod_anais, 40)],
                             efectivo=50, tarjeta=50),
            # Yareli solo con tarjeta: tiene recuadro pero no línea de cajón.
            self.crear_venta([self.renglon(self.prod_yareli, 25)], tarjeta=25),
        ]
        corte = self.crear_corte(ventas)
        response, texto = self.pagina(corte)
        filas = response.context["filas_duenos"]

        for s in ("Servicios agregados", "Total servicios", "Sus productos", "(incluye servicios)", AVISO_WEB):
            self.assertNotIn(s, texto)
        rec = self.recuadros(texto, filas)
        # Yareli es la única de su cuenta → es la receptora y los 25 de
        # tarjeta entran a SU Clip; no le deben ni debe.
        self.assertIn("Yareli 🛍 Vendió $25.00 💵 En su caja $0.00 💳 En su Clip $25.00", rec["Yareli"])
        self.assertNotIn("Debe", rec["Yareli"])
        self.assertNotIn("Le deben", rec["Yareli"])

        b = self.bloque_cajones(texto)
        self.assertEqual(list(b["cajones"]), ["Anais", "Rosa"])
        self.assertEqual(b["total"], D(150))
        self.assertEqual(sum((m for m, _ in b["cajones"].values()), CERO), b["total"])
        self.assertNotIn("Cajón Yareli", texto)

    def test_corte_sin_ventas(self):
        corte = self.crear_corte([])
        response, texto = self.pagina(corte)

        self.assertIn("Sin ventas en este corte.", texto)
        b = self.bloque_cajones(texto)
        self.assertEqual((b["cajones"], b["especiales"], b["total"]), ({}, {}, CERO))
        self.assertIn("TOTAL $0.00", texto)
        self.assertIn("Sin efectivo en este corte.", texto)

    def test_sucursal_sin_responsable_de_servicios(self):
        Sucursal.objects.filter(pk=self.sucursal.pk).update(dueño_servicios=None)
        ventas = self.ventas_con_servicios() + [
            self.crear_venta([self.renglon(self.prod_sin_dueno, 10)], efectivo=10),
        ]
        corte = self.crear_corte(ventas)
        response, texto = self.pagina(corte)
        ctx = response.context
        filas = ctx["filas_duenos"]
        self.assertEqual([f["nombre"] for f in filas],
                         ["Anais", "Rosa", "Yareli", NOMBRE_SIN_DUENO, NOMBRE_SERVICIOS_SIN_RESPONSABLE])

        # Recuadro especial con los conceptos, sin "Sus productos" y con aviso.
        rec = self.recuadros(texto, filas)
        especial = rec[NOMBRE_SERVICIOS_SIN_RESPONSABLE]
        for s in (AVISO_WEB, "🧾 Productos sin registro (x14) $105.00", "🛠 Servicios $15.00",
                  "· Copias (x30) $15.00", "Servicios agregados (incl. sin registro) $120.00"):
            self.assertIn(s, especial)
        self.assertNotIn("Sus productos", especial)
        self.assertIn(AVISO_WEB, rec[NOMBRE_SIN_DUENO])
        self.assertNotIn("Servicios agregados", rec["Rosa"])
        self.assertNotIn(AVISO_WEB, rec["Rosa"])

        # En el bloque por cajón van como líneas especiales; todo cuadra.
        b = self.bloque_cajones(texto)
        por_nombre = {f["nombre"]: f for f in filas}
        self.assertEqual(b["especiales"], {
            NOMBRE_SIN_DUENO: D(10),
            NOMBRE_SERVICIOS_SIN_RESPONSABLE: por_nombre[NOMBRE_SERVICIOS_SIN_RESPONSABLE]["efectivo"],
        })
        self.assertEqual(b["cajones"], {n: (por_nombre[n]["efectivo"], False) for n in ("Anais", "Rosa", "Yareli")})
        self.assertNotIn("(incluye servicios)", texto)
        self.assertEqual(b["total"], ctx["total_efectivo"])
        self.assertEqual(sum((m for m, _ in b["cajones"].values()), CERO) + sum(b["especiales"].values(), CERO),
                         b["total"])
        self.assertEqual(len(b["montos"]), len(b["cajones"]) + len(b["especiales"]) + 1)

        # Térmico: el nombre largo no cabe con el monto → el monto baja; luego el aviso.
        lineas = generar_texto_ticket(corte).splitlines()
        cajon_lineas, total = self.bloque_cajones_termico(lineas)
        i = cajon_lineas.index(NOMBRE_SERVICIOS_SIN_RESPONSABLE)
        monto = por_nombre[NOMBRE_SERVICIOS_SIN_RESPONSABLE]["efectivo"]
        self.assertEqual(cajon_lineas[i + 1:i + 3], [f"${monto:.2f}".rjust(ANCHO), AVISO_TERMICO])
        self.assertIn(renglon(NOMBRE_SIN_DUENO, 10), cajon_lineas)
        self.assertEqual(sum((D(m) for l in cajon_lineas for m in MONTO.findall(l)), CERO), ctx["total_efectivo"])
        self.assertEqual(total, renglon("TOTAL", ctx["total_efectivo"]))
        for linea in lineas[lineas.index(next(l for l in lineas if l.strip() == "VENTAS POR DUENO")):]:
            self.assertLessEqual(len(linea), ANCHO, repr(linea))

    def test_caja_borrada_ya_no_truena(self):
        caja_x = Caja.objects.create(sucursal=self.sucursal, nombre="Caja X")
        ventas = [
            self.crear_venta([self.renglon(self.prod_anais, 100), self.servicio("Copias", 20)],
                             efectivo=200, caja=caja_x),
        ]
        corte = self.crear_corte(ventas, caja=caja_x, caja_nombre="Caja X")
        caja_x.delete()  # FK SET_NULL en CorteCaja.caja y en Venta.caja
        corte.refresh_from_db()
        self.assertIsNone(corte.caja)

        response, texto = self.pagina(corte)  # antes: 500 NoReverseMatch

        self.assertIn("Caja: Caja X", texto)
        self.assertNotIn("Ver todos los cortes", texto)
        b = self.bloque_cajones(texto)
        self.assertEqual(b["total"], D(120))
        # Sin caja no hay sucursal → los servicios no tienen responsable.
        self.assertEqual(set(b["especiales"]), {NOMBRE_SERVICIOS_SIN_RESPONSABLE})
        self.assertEqual(sum((m for m, _ in b["cajones"].values()), CERO) + sum(b["especiales"].values(), CERO),
                         b["total"])

    def test_caja_borrada_sin_snapshot(self):
        caja_x = Caja.objects.create(sucursal=self.sucursal, nombre="Caja X")
        corte = self.crear_corte([], caja=caja_x, caja_nombre=None)
        caja_x.delete()
        corte.refresh_from_db()

        _, texto = self.pagina(corte)
        self.assertIn("Caja: Caja eliminada", texto)

    def test_con_caja_sigue_el_link_a_los_cortes(self):
        corte = self.crear_corte([])
        response, texto = self.pagina(corte)
        self.assertIn("Ver todos los cortes", texto)
        self.assertContains(response, reverse("ventas:tickets_cortes_caja", args=[self.sucursal.id]))
        self.assertIn("Caja: Caja Anais", texto)


# ---------------------------------------------------------------------------
# Ticket térmico
# ---------------------------------------------------------------------------

class TicketCorteTermicoFormatoTest(FormatoCorteTestCase):

    def test_ticket_termico(self):
        corte = self.crear_corte(self.ventas_con_servicios())
        tot = totales_caja(corte.ventas.all())
        filas = desglose_por_dueno(ventas_para_desglose(corte.ventas.all()))
        texto = generar_texto_ticket(corte)
        lineas = texto.splitlines()

        # Ninguna línea del bloque (VENTAS POR DUENO … CUENTA BIEN.) excede el ancho.
        ini = next(i for i, l in enumerate(lineas) if l.strip() == "VENTAS POR DUENO")
        fin = next(i for i, l in enumerate(lineas) if l.strip() == "CUENTA BIEN.")
        self.assertLess(ini, fin)
        for linea in lineas[ini:]:
            self.assertLessEqual(len(linea), ANCHO, repr(linea))

        # Servicios dentro del bloque de Rosa (entre "  Rosa" y "  Yareli").
        bloque_rosa = lineas[lineas.index("  Rosa"):lineas.index("  Yareli")]
        # Mismos montos que el recuadro web (ver test_servicios_dentro_...).
        self.assertIn(renglon("  Vendio:", 380), bloque_rosa)
        self.assertIn(renglon("  En su caja:", 160), bloque_rosa)
        self.assertIn(renglon("  En su Clip:", 230), bloque_rosa)
        # Rosa debe 10, pero eso ya no se imprime: tras "En su Clip" viene el
        # separador de servicios.
        i_clip = bloque_rosa.index(renglon("  En su Clip:", 230))
        self.assertTrue(bloque_rosa[i_clip + 1].strip(" -.") == "", repr(bloque_rosa[i_clip + 1]))
        self.assert_sin_deudas_termico(texto)
        self.assertIn(renglon("  Sus productos:", 260), bloque_rosa)
        # Sin registro aparte; los servicios de verdad por concepto.
        self.assertIn(renglon("  Sin registro x14:", 105), bloque_rosa)
        self.assertIn(renglon("  Servicios:", 15), bloque_rosa)
        self.assertIn(renglon("  - Copias x30", 15), bloque_rosa)
        self.assertFalse([l for l in bloque_rosa if l.startswith("  - Prod. sin reg")])
        self.assertIn(renglon("  Total agregado:", 120), bloque_rosa)
        self.assertEqual(texto.count("Total agregado"), 1)

        # DETALLE DEL CORTE con 2 decimales.
        i = lineas.index("TOTAL EFECTIVO EN CAJA:")
        self.assertEqual(lineas[i + 1], "$520.00".rjust(ANCHO))
        i = lineas.index("TOTAL TARJETA EN CAJA:")
        self.assertEqual(lineas[i + 1], "$230.00".rjust(ANCHO))

        # Una línea por cajón (con la nota de servicios en el de Rosa) y el TOTAL.
        cajon_lineas, total = self.bloque_cajones_termico(lineas)
        esperado = []
        for f in filas:
            esperado.append(renglon(f"Cajon {f['nombre']}", f["efectivo"]))
            if f["servicios"]:
                esperado.append("  (incluye servicios)")
        self.assertEqual(cajon_lineas[:-1], esperado)  # la última es el separador punteado
        self.assertEqual(sum((D(m) for l in cajon_lineas for m in MONTO.findall(l)), CERO), tot["efectivo"])
        self.assertEqual(total, renglon("TOTAL", tot["efectivo"]))
        self.assertEqual(lineas[fin].strip(), "CUENTA BIEN.")
        self.assertIn("DEBE HABER EN EFECTIVO", [l.strip() for l in lineas])
        self.assertNotIn("EN CAJA ANAIS DEBE HABER", texto)

    def test_ticket_termico_sin_ventas(self):
        corte = self.crear_corte([])
        lineas = generar_texto_ticket(corte).splitlines()
        cajon_lineas, total = self.bloque_cajones_termico(lineas)
        self.assertEqual([l.strip() for l in cajon_lineas if l.strip("- ")], ["(sin efectivo)"])
        self.assertEqual(total, renglon("TOTAL", 0))

    def test_caja_con_nombre_largo_no_excede_el_ancho(self):
        caja = Caja.objects.create(sucursal=self.sucursal, nombre="Caja Mostrador Principal")
        ventas = [self.crear_venta([self.renglon(self.prod_anais, 50)], efectivo=50, caja=caja)]
        corte = self.crear_corte(ventas, caja=caja, caja_nombre=caja.nombre)
        lineas = generar_texto_ticket(corte).splitlines()
        # El encabezado del total ya cabe partido en líneas: se revisa TODO
        # el ticket salvo "Caja: <nombre>" (nombre libre, se centra tal cual).
        for linea in lineas:
            if linea.strip().startswith("Caja:"):
                continue
            self.assertLessEqual(len(linea), ANCHO, repr(linea))
        self.assertIn("DEBE HABER EN EFECTIVO", [l.strip() for l in lineas])


# ---------------------------------------------------------------------------
# La venta con la que el dueño explicó la regla: quién vendió qué, cuánto hay
# en cada caja y en cada Clip. Quién le debe a quién ya NO va en el corte (es
# sensible: lo ve e imprime la cajera); solo sale en el dashboard de la dueña.
# ---------------------------------------------------------------------------

class CuentasEntreDuenasCorteTest(FormatoCorteTestCase):
    """
    Gelish $100 (Anais) + tinte $50 (Yareli) + $10 (Rosa) = $160. Anais es
    la que más vendió en la cuenta → recibe el billete, da el cambio y cobra
    TODA la tarjeta en SU Clip; a Yareli y Rosa se les pasa lo suyo en
    efectivo y, si no alcanza, Anais queda debiendo (fuera del corte).
    """

    def venta_del_dueno(self, efectivo, tarjeta):
        return self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 50),
                                 self.renglon(self.prod_rosa, 10)], efectivo=efectivo, tarjeta=tarjeta)

    def clips(self, texto):
        """(nombre → monto, TOTAL) del bloque "EN LOS CLIPS"."""
        ini = texto.index("EN LOS CLIPS")
        bloque = texto[ini:texto.index("GRACIAS POR SU TRABAJO", ini)]
        lineas = {n: D(m) for n, m in re.findall(r"Clip (\S+) \$(-?\d+\.\d{2})", bloque)}
        return lineas, D(re.search(r"TOTAL EN CLIPS \$(-?\d+\.\d{2})", bloque).group(1))

    def test_mixto_70_tarjeta_90_efectivo_nadie_debe(self):
        # 70 tarjeta + 90 efectivo = 160, sin cambio. Los 70 entran al Clip de
        # Anais; de los 90 en efectivo se le pasan 50 a Yareli y 10 a Rosa y
        # a Anais le quedan 30. 30 + 70 = 100 = lo que vendió → nadie debe.
        corte = self.crear_corte([self.venta_del_dueno(efectivo=90, tarjeta=70)])
        response, texto = self.pagina(corte)
        rec = self.recuadros(texto, response.context["filas_duenos"])

        self.assertIn("Anais 🛍 Vendió $100.00 💵 En su caja $30.00 💳 En su Clip $70.00", rec["Anais"])
        self.assertIn("Yareli 🛍 Vendió $50.00 💵 En su caja $50.00 💳 En su Clip $0.00", rec["Yareli"])
        self.assertIn("Rosa 🛍 Vendió $10.00 💵 En su caja $10.00 💳 En su Clip $0.00", rec["Rosa"])
        self.assert_sin_deudas_web(texto)

        b = self.bloque_cajones(texto)
        self.assertEqual({n: m for n, (m, _) in b["cajones"].items()},
                         {"Anais": D(30), "Rosa": D(10), "Yareli": D(50)})
        self.assertEqual(b["total"], D(90))

        clips, total = self.clips(texto)
        self.assertEqual(clips, {"Anais": D(70)})
        self.assertEqual(total, response.context["total_tarjeta"])
        self.assertEqual(total, D(70))

    def test_todo_con_tarjeta_anais_queda_debiendo(self):
        # 160 con tarjeta: todo entra al Clip de Anais y no hay efectivo para
        # pasarle a nadie → Anais tiene 160 en su Clip pero vendió 100: debe
        # 60 (50 a Yareli, 10 a Rosa). Nada de eso aparece en el corte.
        corte = self.crear_corte([self.venta_del_dueno(efectivo=0, tarjeta=160)])
        response, texto = self.pagina(corte)
        ctx = response.context
        rec = self.recuadros(texto, ctx["filas_duenos"])

        self.assertIn("Anais 🛍 Vendió $100.00 💵 En su caja $0.00 💳 En su Clip $160.00", rec["Anais"])
        self.assertIn("Yareli 🛍 Vendió $50.00 💵 En su caja $0.00 💳 En su Clip $0.00", rec["Yareli"])
        self.assertIn("Rosa 🛍 Vendió $10.00 💵 En su caja $0.00 💳 En su Clip $0.00", rec["Rosa"])
        self.assert_sin_deudas_web(texto)
        html = response.content.decode()
        for s in ("$60.00", "CUENTAS ENTRE DUEÑAS", "le debe"):
            self.assertNotIn(s, html, s)

        clips, total = self.clips(texto)
        self.assertEqual(clips, {"Anais": D(160)})
        self.assertEqual(sum(clips.values(), CERO), ctx["total_tarjeta"])
        self.assertEqual(total, ctx["total_tarjeta"])

        # El bloque negro no cambia: no hay efectivo en ningún cajón.
        b = self.bloque_cajones(texto)
        self.assertEqual((b["cajones"], b["total"]), ({}, CERO))
        self.assertIn("Sin efectivo en este corte.", texto)

    def test_deudas_netas_tampoco_salen(self):
        # Venta 1 (todo tarjeta): Anais 100 + Yareli 60 → Anais le debe 60 a Yareli.
        # Venta 2 (todo tarjeta): Yareli 100 + Anais 20 → Yareli le debe 20 a Anais.
        # Neto 40, pero el corte no lo dice; solo los Clips.
        ventas = [
            self.crear_venta([self.renglon(self.prod_anais, 100), self.renglon(self.prod_yareli, 60)],
                             tarjeta=160),
            self.crear_venta([self.renglon(self.prod_yareli, 100), self.renglon(self.prod_anais, 20)],
                             tarjeta=120),
        ]
        response, texto = self.pagina(self.crear_corte(ventas))
        self.assert_sin_deudas_web(texto)
        self.assertNotIn("$40.00", texto)

        clips, total = self.clips(texto)
        self.assertEqual(clips, {"Anais": D(160), "Yareli": D(120)})
        self.assertEqual(total, D(280))

    def test_termico_todo_tarjeta(self):
        corte = self.crear_corte([self.venta_del_dueno(efectivo=0, tarjeta=160)])
        texto = generar_texto_ticket(corte)
        lineas = texto.splitlines()

        for linea in lineas:
            if linea.strip().startswith("Caja:"):
                continue
            self.assertLessEqual(len(linea), ANCHO, repr(linea))

        bloque_anais = lineas[lineas.index("  Anais"):lineas.index("  Rosa")]
        # Tras "En su Clip" viene el separador del siguiente recuadro: sin "Debe:".
        self.assertEqual(bloque_anais[1:5], [renglon("  Vendio:", 100), renglon("  En su caja:", 0),
                                             renglon("  En su Clip:", 160), "-" * ANCHO])
        self.assert_sin_deudas_termico(texto)
        self.assertNotIn("$60.00", texto)

        # Tras el detalle del corte sigue directo el efectivo por cajón.
        i = lineas.index("TOTAL TARJETA EN CAJA:")
        self.assertEqual(lineas[i + 3].strip(), "DEBE HABER EN EFECTIVO")

        i = next(i for i, l in enumerate(lineas) if l.strip() == "EN LOS CLIPS")
        self.assertEqual(lineas[i + 1], renglon("Clip Anais", 160))
        self.assertIn(renglon("TOTAL CLIPS", 160), lineas[i:])
        # El bloque de efectivo por cajón sigue ahí, en 0.
        _, total = self.bloque_cajones_termico(lineas)
        self.assertEqual(total, renglon("TOTAL", 0))

    def test_termico_sin_deudas(self):
        corte = self.crear_corte([self.venta_del_dueno(efectivo=90, tarjeta=70)])
        texto = generar_texto_ticket(corte)
        lineas = texto.splitlines()
        self.assert_sin_deudas_termico(texto)
        i = next(i for i, l in enumerate(lineas) if l.strip() == "EN LOS CLIPS")
        self.assertEqual(lineas[i + 1], renglon("Clip Anais", 70))

    def test_termico_nombre_largo_no_excede_el_ancho(self):
        from inventario.models import Producto
        from ventas.tests.base import crear_empleado
        larga = crear_empleado("guadalupe", "Maria Guadalupe Fernanda", prioridad=4)
        collar = Producto.objects.create(nombre="Collar", precio_mayoreo=10, precio_menudeo=10, dueño=larga)
        corte = self.crear_corte([
            self.crear_venta([self.renglon(collar, 100), self.renglon(self.prod_yareli, 50)], tarjeta=150),
        ])
        texto = generar_texto_ticket(corte)
        for linea in texto.splitlines():
            if linea.strip().startswith("Caja:"):
                continue
            self.assertLessEqual(len(linea), ANCHO, repr(linea))
        self.assert_sin_deudas_termico(texto)
