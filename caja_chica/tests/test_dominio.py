"""Reglas del dominio: Python puro, sin base de datos."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from caja_chica.domain.cajita import CajitaConSalidas
from caja_chica.domain.errores import DescripcionInvalida, MontoInvalido, NombreInvalido, SinPermiso
from caja_chica.domain.movimientos import descripcion_valida, monto_valido
from caja_chica.domain.nombres import NombrePersona, clave_de, parecidos
from caja_chica.domain.permisos import Actor, exigir_puede_corregir, exigir_puede_registrar
from caja_chica.domain.semanas import semana_de


class NombresTest(SimpleTestCase):

    def test_normaliza_lo_que_escriben(self):
        for crudo, texto in (
            ("  pablo   PEREZ ", "Pablo Perez"),
            ("josé", "José"),
            ("maria-jose o'neil", "Maria-Jose O'Neil"),
            ("Ana3 #López!", "Ana López"),
        ):
            with self.subTest(crudo=crudo):
                self.assertEqual(NombrePersona.desde(crudo).texto, texto)

    def test_misma_persona_con_mayusculas_o_acentos(self):
        self.assertEqual(clave_de("José Pérez"), clave_de("  JOSE   perez "))
        self.assertEqual(NombrePersona.desde("PABLO").clave, "pablo")

    def test_nombre_vacio_o_sin_letras(self):
        for crudo in ("", "   ", "123", "!!", None):
            with self.subTest(crudo=crudo), self.assertRaises(NombreInvalido):
                NombrePersona.desde(crudo)

    def test_nombre_muy_largo(self):
        with self.assertRaises(NombreInvalido):
            NombrePersona.desde("a" * 61)

    def test_parecidos(self):
        registradas = [(1, "Pablo", "pablo"), (2, "Pablo Pérez", "pablo perez"), (3, "Luis", "luis")]
        self.assertEqual([s["nombre"] for s in parecidos("pabblo", registradas)], ["Pablo", "Pablo Pérez"])
        self.assertEqual([s["nombre"] for s in parecidos("paasloblo", registradas)][:1], ["Pablo"])
        self.assertEqual(parecidos("ana", registradas), [])
        # La misma clave no es "parecida": es la misma persona.
        self.assertNotIn("Pablo", [s["nombre"] for s in parecidos("pablo", registradas)])


class MovimientosTest(SimpleTestCase):

    def test_monto(self):
        self.assertEqual(monto_valido("1,200.5"), Decimal("1200.50"))
        self.assertEqual(monto_valido("$ 80"), Decimal("80.00"))
        self.assertEqual(monto_valido(99.999), Decimal("100.00"))
        for malo in ("", "abc", "0", "-5", "NaN", "Infinity", "50000.01", None):
            with self.subTest(malo=malo), self.assertRaises(MontoInvalido):
                monto_valido(malo)

    def test_descripcion(self):
        self.assertEqual(descripcion_valida("  garrafón   de agua "), "Garrafón de agua")
        with self.assertRaises(DescripcionInvalida):
            descripcion_valida("   ")
        with self.assertRaises(DescripcionInvalida):
            descripcion_valida("x" * 151)


class CajitaTest(SimpleTestCase):

    def test_nunca_negativa(self):
        c = CajitaConSalidas(Decimal("100"), vales=Decimal("30"), gastos=Decimal("20"))
        self.assertEqual((c.salidas, c.debe_haber, c.del_fondo), (Decimal("50"), Decimal("50"), Decimal("0.00")))
        c = CajitaConSalidas(Decimal("40"), vales=Decimal("100"))
        self.assertEqual((c.debe_haber, c.del_fondo), (Decimal("0.00"), Decimal("60")))


class SemanasTest(SimpleTestCase):

    def test_lunes_a_domingo(self):
        miercoles = date(2026, 10, 21)
        self.assertEqual(semana_de(miercoles), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(semana_de(date(2026, 10, 25)), (date(2026, 10, 19), date(2026, 10, 25)))
        self.assertEqual(semana_de(miercoles, atras=1), (date(2026, 10, 12), date(2026, 10, 18)))


class PermisosTest(SimpleTestCase):

    def test_registrar_cualquiera_en_caja(self):
        exigir_puede_registrar(Actor(1, "Caro", "cajero"), caja_id=3)
        exigir_puede_registrar(Actor(2, "Ana", "dueño"), caja_id=3)
        with self.assertRaises(SinPermiso):
            exigir_puede_registrar(Actor(3, "Beto", "almacenista"), caja_id=3)
        with self.assertRaises(SinPermiso):
            exigir_puede_registrar(Actor(1, "Caro", "cajero"), caja_id=None)

    def test_corregir_solo_duenas(self):
        exigir_puede_corregir(Actor(2, "Ana", "dueño"))
        with self.assertRaises(SinPermiso):
            exigir_puede_corregir(Actor(1, "Caro", "cajero"))
