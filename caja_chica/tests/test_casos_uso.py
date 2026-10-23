"""
Casos de uso con repositorios EN MEMORIA: prueban la lógica sin Django ni
base de datos (si un caso de uso necesitara el ORM, estos tests no correrían).
"""
from dataclasses import replace
from datetime import date, datetime, timezone as tz
from decimal import Decimal

from django.test import SimpleTestCase

from caja_chica.application import casos_uso as cu
from caja_chica.application.puertos import Duena, Persona
from caja_chica.domain.errores import NoEncontrado, NombreParecido, SinCajita, SinPermiso
from caja_chica.domain.movimientos import Movimiento, TipoMovimiento
from caja_chica.domain.permisos import Actor

CAJERA = Actor(10, "Caro", "cajero")
DUENA = Actor(20, "Anais", "dueño")
FABIOLA = Duena(5, "Ana Fabiola")


class PersonasEnMemoria:
    def __init__(self, *nombres):
        self.lista = [Persona(i + 1, n, n.lower()) for i, n in enumerate(nombres)]

    def todas(self):
        return list(self.lista)

    def por_id(self, persona_id):
        return next((p for p in self.lista if p.id == persona_id), None)

    def por_clave(self, clave):
        return next((p for p in self.lista if p.clave == clave), None)

    def crear(self, nombre, creada_por_id):
        p = Persona(len(self.lista) + 1, nombre.texto, nombre.clave)
        self.lista.append(p)
        return p


class MovimientosEnMemoria:
    def __init__(self):
        self.todos = {}

    def registrar(self, nuevo, fecha=None):
        mid = len(self.todos) + 1
        persona = nuevo.persona_id
        self.todos[mid] = Movimiento(
            id=mid, tipo=nuevo.tipo, monto=nuevo.monto, fecha=fecha or datetime(2026, 10, 22, 12, tzinfo=tz.utc),
            caja_id=nuevo.caja_id, caja_nombre=f"Caja {nuevo.caja_id}",
            descontado_a_id=nuevo.descontado_a.id, descontado_a_nombre=nuevo.descontado_a.nombre,
            registrado_por_nombre="Caro", persona_id=persona, persona_nombre=f"P{persona}" if persona else "",
            descripcion=nuevo.descripcion,
        )
        return self.todos[mid]

    def obtener(self, movimiento_id):
        if movimiento_id not in self.todos:
            raise NoEncontrado("Ese vale o gasto")
        return self.todos[movimiento_id]

    def cambiar_monto(self, movimiento_id, monto, actor_id):
        m = self.todos[movimiento_id]
        self.todos[movimiento_id] = replace(m, monto=monto, monto_original=m.monto_original or m.monto)
        return self.todos[movimiento_id]

    def eliminar(self, movimiento_id, actor_id):
        del self.todos[movimiento_id]

    def sin_corte_de_caja(self, caja_id):
        return [m for m in self.todos.values() if m.caja_id == caja_id and m.corte_id is None]

    def del_corte(self, corte_id):
        return [m for m in self.todos.values() if m.corte_id == corte_id]

    def asignar_corte(self, caja_id, corte_id, hasta, dia=None):
        n = 0
        for mid, m in list(self.todos.items()):
            if m.caja_id == caja_id and m.corte_id is None and m.fecha <= hasta:
                self.todos[mid] = replace(m, corte_id=corte_id)
                n += 1
        return n

    def entre_dias(self, desde, hasta):
        return [m for m in self.todos.values() if desde <= m.fecha.date() <= hasta]

    def del_dia(self, descontado_a_id, dia):
        return [m for m in self.todos.values() if m.descontado_a_id == descontado_a_id and m.fecha.date() == dia]


class CajitasEnMemoria:
    def __init__(self, duena=FABIOLA):
        self.duena = duena

    def duena_de(self, caja_id):
        return self.duena


class RegistrarValeTest(SimpleTestCase):

    def setUp(self):
        self.personas = PersonasEnMemoria("Pablo", "Luis")
        self.movs = MovimientosEnMemoria()
        self.registrar = cu.RegistrarVale(self.personas, self.movs, CajitasEnMemoria())

    def test_nombre_registrado_se_reusa(self):
        m = self.registrar(CAJERA, 1, "200", nombre="  PABLO ")
        self.assertEqual((m.persona_id, m.monto, m.tipo), (1, Decimal("200.00"), TipoMovimiento.VALE))
        self.assertEqual(len(self.personas.lista), 2)
        self.assertEqual((m.descontado_a_id, m.descontado_a_nombre), (5, "Ana Fabiola"))

    def test_parecido_no_guarda_y_sugiere(self):
        with self.assertRaises(NombreParecido) as ctx:
            self.registrar(CAJERA, 1, "200", nombre="pabblo")
        self.assertEqual(ctx.exception.sugerencias, [{"id": 1, "nombre": "Pablo"}])
        self.assertEqual(self.movs.todos, {})
        self.assertEqual(len(self.personas.lista), 2)

    def test_otra_persona_confirmada_se_crea(self):
        m = self.registrar(CAJERA, 1, "50", nombre="pabblo", es_otra_persona=True)
        self.assertEqual(self.personas.por_id(m.persona_id).nombre, "Pabblo")

    def test_nombre_nuevo_sin_parecidos_se_crea(self):
        m = self.registrar(CAJERA, 1, "50", nombre="ximena")
        self.assertEqual(self.personas.por_id(m.persona_id).nombre, "Ximena")

    def test_por_persona_id(self):
        self.assertEqual(self.registrar(CAJERA, 1, "10", persona_id=2).persona_id, 2)
        with self.assertRaises(NoEncontrado):
            self.registrar(CAJERA, 1, "10", persona_id=99)

    def test_sin_responsable_de_servicios(self):
        registrar = cu.RegistrarVale(self.personas, self.movs, CajitasEnMemoria(duena=None))
        with self.assertRaises(SinCajita):
            registrar(CAJERA, 1, "10", nombre="Pablo")

    def test_fuera_de_caja(self):
        with self.assertRaises(SinPermiso):
            self.registrar(CAJERA, None, "10", nombre="Pablo")


class GastoYCorreccionesTest(SimpleTestCase):

    def setUp(self):
        self.movs = MovimientosEnMemoria()
        self.gasto = cu.RegistrarGasto(self.movs, CajitasEnMemoria())(CAJERA, 1, "35.5", "  garrafón ")

    def test_gasto(self):
        self.assertEqual((self.gasto.descripcion, self.gasto.monto), ("Garrafón", Decimal("35.50")))
        self.assertEqual(self.gasto.concepto, "Garrafón")

    def test_cajera_no_corrige(self):
        with self.assertRaises(SinPermiso):
            cu.CambiarMonto(self.movs)(CAJERA, self.gasto.id, "10")
        with self.assertRaises(SinPermiso):
            cu.EliminarMovimiento(self.movs)(CAJERA, self.gasto.id)

    def test_duena_cambia_y_borra(self):
        m = cu.CambiarMonto(self.movs)(DUENA, self.gasto.id, "30")
        self.assertEqual((m.monto, m.monto_original), (Decimal("30.00"), Decimal("35.50")))
        cu.EliminarMovimiento(self.movs)(DUENA, self.gasto.id)
        with self.assertRaises(NoEncontrado):
            cu.EliminarMovimiento(self.movs)(DUENA, self.gasto.id)


class ConsultasTest(SimpleTestCase):

    def setUp(self):
        self.movs = MovimientosEnMemoria()
        vale = cu.RegistrarVale(PersonasEnMemoria("Pablo", "Luis"), self.movs, CajitasEnMemoria())
        vale(CAJERA, 1, "100", persona_id=1)
        vale(CAJERA, 2, "300", persona_id=2)
        vale(CAJERA, 1, "50", persona_id=1)
        cu.RegistrarGasto(self.movs, CajitasEnMemoria())(CAJERA, 1, "20", "Agua")

    def test_resumen_de_semana(self):
        r = cu.ResumenDeSemana(self.movs)(date(2026, 10, 19), date(2026, 10, 25))
        self.assertEqual([(p.persona, p.total) for p in r.personas], [("P2", Decimal("300.00")), ("P1", Decimal("150.00"))])
        self.assertEqual((r.total_vales, r.total_gastos), (Decimal("450.00"), Decimal("20.00")))
        vacia = cu.ResumenDeSemana(self.movs)(date(2026, 10, 12), date(2026, 10, 18))
        self.assertEqual((vacia.personas, vacia.gastos), ([], []))

    def test_corte_y_dia(self):
        hasta = datetime(2026, 10, 22, 23, tzinfo=tz.utc)
        self.assertEqual(cu.AsignarACorte(self.movs)(1, 77, hasta), 3)
        salidas = cu.SalidasDelCorte(self.movs)(77)
        self.assertEqual(list(salidas), [5])
        s = salidas[5]
        self.assertEqual((s.total_vales, s.total_gastos, s.total), (Decimal("150.00"), Decimal("20.00"), Decimal("170.00")))
        self.assertEqual(cu.SalidasDelDia(self.movs)(5, date(2026, 10, 22)),
                         {1: Decimal("170.00"), 2: Decimal("300.00")})
        self.assertEqual(cu.LoSinCorteDeCaja(self.movs)(1), [])
