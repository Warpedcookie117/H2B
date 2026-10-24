"""
Datos compartidos para los tests de ventas. SOLO LECTURA para los tests:
cada archivo test_*.py hereda de VentasBaseTestCase y arma sus ventas con
crear_venta().

Escenario: una sucursal con 3 dueñas, cada una con su cajón físico.
  - Rosa   (la suegra)  prioridad_cambio=1  → además es responsable de servicios
  - Anais               prioridad_cambio=2
  - Yareli              prioridad_cambio=3
Dos cajas del sistema (computadoras): "Caja Anais" y "Caja Fabiola".
"""
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone

from inventario.models import Producto, Ubicacion
from sucursales.models import Caja, Sucursal
from tienda_temp.models import Empleado, Usuario
from ventas.models import Venta, VentaDetalle

CENT = Decimal("0.01")


def D(x):
    return Decimal(str(x)).quantize(CENT, rounding=ROUND_HALF_UP)


def crear_empleado(username, first_name, rol="dueño", prioridad=None):
    user = Usuario.objects.create_user(
        username=username,
        email=f"{username}@test.local",
        password="x",
        first_name=first_name,
    )
    emp = Empleado.objects.create(
        user=user,
        rol=rol,
        direccion="x",
        numero_contacto="1",
        contacto_emergencia="x",
        descripcion_contacto_emergencia="x",
    )
    # prioridad_cambio lo agrega la Fase 2; si el campo aún no existe se ignora.
    if prioridad is not None and hasattr(emp, "prioridad_cambio"):
        emp.prioridad_cambio = prioridad
        emp.save(update_fields=["prioridad_cambio"])
    return emp


# El hasher real tarda ~1.4 s por usuario; en tests no importa la seguridad.
@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class VentasBaseTestCase(TestCase):

    def _pre_setup(self):
        super()._pre_setup()
        # Los días del mes del dashboard van en caché (corte_service.
        # resumen_mes_dueno): que no se cuelen de una prueba a otra.
        cache.clear()

    @classmethod
    def setUpTestData(cls):
        cls.rosa = crear_empleado("rosa", "Rosa", prioridad=1)
        cls.anais = crear_empleado("anais", "Anais", prioridad=2)
        cls.yareli = crear_empleado("yareli", "Yareli", prioridad=3)
        cls.cajero = crear_empleado("cajero", "Cajero", rol="cajero")

        cls.sucursal = Sucursal.objects.create(nombre="Sucursal Centro", dueño_servicios=cls.rosa)
        cls.caja_anais = Caja.objects.create(sucursal=cls.sucursal, nombre="Caja Anais")
        cls.caja_fabiola = Caja.objects.create(sucursal=cls.sucursal, nombre="Caja Fabiola")
        cls.piso = Ubicacion.objects.create(
            nombre="Piso", direccion="x", sucursal=cls.sucursal, tipo="piso"
        )

        cls.prod_rosa = Producto.objects.create(
            nombre="Bolsa Rosa", precio_mayoreo=10, precio_menudeo=10, dueño=cls.rosa
        )
        cls.prod_anais = Producto.objects.create(
            nombre="Aretes Anais", precio_mayoreo=10, precio_menudeo=10, dueño=cls.anais
        )
        cls.prod_yareli = Producto.objects.create(
            nombre="Pulsera Yareli", precio_mayoreo=10, precio_menudeo=10, dueño=cls.yareli
        )
        cls.prod_sin_dueno = Producto.objects.create(
            nombre="Huerfano", precio_mayoreo=10, precio_menudeo=10, dueño=None
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def renglon(self, producto, subtotal, cantidad=1):
        """Renglón normal de producto. subtotal = precio_unitario * cantidad."""
        return {"producto": producto, "cantidad": cantidad, "subtotal": D(subtotal), "tipo": "normal"}

    def servicio(self, concepto, subtotal, cantidad=1):
        """Renglón de servicio, igual que lo guarda POSService ("Servicio: X", sin producto)."""
        return {"producto": None, "cantidad": cantidad, "subtotal": D(subtotal), "tipo": "servicio",
                "concepto": concepto}

    def regalo(self, producto, cantidad=1):
        return {"producto": producto, "cantidad": cantidad, "subtotal": D(0), "tipo": "regalo"}

    def crear_venta(self, renglones, efectivo=0, tarjeta=0, descuento_pct=0, caja=None, fecha=None,
                    subtotal=None, pago_en_seco=False):
        """
        Crea Venta + VentaDetalle directo en BD con la MISMA aritmética que
        POSService.crear_venta (descuento sobre el subtotal, cambio =
        efectivo - max(0, total - tarjeta)). `subtotal` permite forzar un
        Venta.subtotal distinto de la suma de renglones (caso ofertas nxprecio).
        pago_en_seco=False por default: venta con la regla de antes (deuda);
        POSService marca True todas las ventas nuevas.
        """
        caja = caja or self.caja_anais
        suma = sum((r["subtotal"] for r in renglones), Decimal("0"))
        sub = D(subtotal) if subtotal is not None else suma
        descuento = D(sub * Decimal(descuento_pct) / 100)
        total = sub - descuento
        efectivo = D(efectivo)
        tarjeta = D(tarjeta)
        cambio = max(Decimal("0"), efectivo - max(Decimal("0"), total - tarjeta))
        if efectivo > 0 and tarjeta > 0:
            metodo = "mixto"
        elif tarjeta > 0:
            metodo = "tarjeta"
        else:
            metodo = "efectivo"

        venta = Venta.objects.create(
            empleado=self.cajero,
            ubicacion=self.piso,
            caja=caja,
            caja_nombre=caja.nombre if caja else None,
            subtotal=sub,
            descuento=descuento,
            total=total,
            metodo_pago=metodo,
            pagado_efectivo=efectivo,
            pagado_tarjeta=tarjeta,
            cambio=cambio,
            pago_en_seco=pago_en_seco,
        )
        for r in renglones:
            if r["tipo"] == "servicio":
                nombre = f"Servicio: {r['concepto']}"
                snap = {"tipo": "servicio"}
            elif r["tipo"] == "regalo":
                nombre = r["producto"].nombre
                snap = {"tipo": "regalo", "promo": "test"}
            else:
                nombre = r["producto"].nombre if r["producto"] else "Producto borrado"
                snap = {}
            VentaDetalle.objects.create(
                venta=venta,
                producto=r["producto"],
                nombre_snapshot=nombre,
                atributos_snapshot=snap,
                cantidad=r["cantidad"],
                precio_unitario=D(r["subtotal"] / r["cantidad"]) if r["cantidad"] else D(0),
                subtotal=r["subtotal"],
            )
        if fecha is not None:
            if isinstance(fecha, datetime) and timezone.is_naive(fecha):
                fecha = timezone.make_aware(fecha)
            Venta.objects.filter(pk=venta.pk).update(fecha=fecha)
        venta.refresh_from_db()
        return venta

    def login(self, empleado):
        self.client.force_login(empleado.user)
