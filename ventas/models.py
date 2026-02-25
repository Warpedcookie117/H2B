from django.db import models

from django.db import models
from tienda_temp.models import Empleado
from inventario.models import Producto, Ubicacion


class Venta(models.Model):
    METODO_PAGO = [
        ("efectivo", "Efectivo"),
        ("tarjeta", "Tarjeta (Clip)"),
        ("mixto", "Mixto"),
    ]

    fecha = models.DateTimeField(auto_now_add=True)
    empleado = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True)

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

    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"