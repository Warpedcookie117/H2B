from django.db import models

from django.db import models
from tienda_temp.models import Empleado
from inventario.models import Producto, Ubicacion
from sucursales.models import Caja



class Venta(models.Model):
    METODO_PAGO = [
        ("efectivo", "Efectivo"),
        ("tarjeta", "Tarjeta (Clip)"),
        ("mixto", "Mixto"),
    ]

    caja_nombre = models.CharField(max_length=100, blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True)

    # 🔥 NUEVO: caja donde se hizo la venta
    caja = models.ForeignKey(Caja, on_delete=models.SET_NULL, null=True)

    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    descuento = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)

    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO)

    pagado_efectivo = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pagado_tarjeta = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    cambio = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"Venta #{self.id} - ${self.total}"


    
    
class VentaDetalle(models.Model):
    venta = models.ForeignKey(Venta, related_name="detalles", on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.SET_NULL, null=True)

    # ⭐ Snapshots
    nombre_snapshot = models.CharField(max_length=150, blank=True, null=True)
    atributos_snapshot = models.JSONField(blank=True, null=True)

    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        nombre = self.nombre_snapshot or (self.producto.nombre if self.producto else "PRODUCTO ELIMINADO")
        return f"{nombre} x{self.cantidad}"
    
    
    
class CorteCaja(models.Model):
    caja = models.ForeignKey(Caja, on_delete=models.SET_NULL, null=True, blank=True)
    caja_nombre = models.CharField(max_length=100, blank=True, null=True)  # snapshot
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    total_general = models.DecimalField(max_digits=10, decimal_places=2)
    total_por_dueno = models.JSONField()

    ventas = models.ManyToManyField(Venta, blank=True, related_name="cortes")

    def __str__(self):
        nombre = self.caja_nombre or "Caja eliminada"
        return f"Corte de {nombre} – {self.fecha.date()}"