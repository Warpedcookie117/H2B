from django.db import models

from django.db import models
from tienda_temp.models import Empleado
from inventario.models import Producto, Ubicacion
from sucursales.models import Caja
from inventario.models import Categoria



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


class Promocion(models.Model):
    TIPO_CONDICION = [
        ('categoria',       'Categoría de producto'),
        ('monto',           'Monto mínimo de compra'),
        ('monto_categoria', 'Monto mínimo por categoría'),
    ]
    TIPO_RESULTADO = [
        ('regalo_fijo',     'Producto de regalo fijo'),
        ('regalo_variante', 'El cliente escoge de una categoría'),
    ]

    nombre      = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    activo      = models.BooleanField(default=True)

    # — Condición —
    tipo_condicion       = models.CharField(max_length=20, choices=TIPO_CONDICION)
    categoria_disparadora = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='promociones_disparadoras',
    )
    monto_minimo = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # — Resultado —
    tipo_resultado   = models.CharField(max_length=20, choices=TIPO_RESULTADO)
    producto_regalo  = models.ForeignKey(
        Producto, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='promociones_como_regalo',
    )
    categoria_regalo = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='promociones_categoria_regalo',
    )
    filtros_atributos = models.JSONField(default=list, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    def descripcion_corta(self):
        if self.tipo_condicion == 'categoria' and self.categoria_disparadora:
            dispara = f"producto de «{self.categoria_disparadora.nombre}»"
        elif self.tipo_condicion == 'monto' and self.monto_minimo:
            dispara = f"compra ≥ ${self.monto_minimo}"
        elif self.tipo_condicion == 'monto_categoria' and self.categoria_disparadora and self.monto_minimo:
            dispara = f"compra ≥ ${self.monto_minimo} de «{self.categoria_disparadora.nombre}»"
        else:
            dispara = "?"

        if self.tipo_resultado == 'regalo_fijo' and self.producto_regalo:
            resultado = f"regalar «{self.producto_regalo.nombre}»"
        elif self.tipo_resultado == 'regalo_variante' and self.categoria_regalo:
            resultado = f"cliente escoge regalo de «{self.categoria_regalo.nombre}»"
        else:
            resultado = "?"

        return f"Cuando {dispara} → {resultado}"

    class Meta:
        ordering = ['-activo', 'nombre']


class Oferta(models.Model):
    TIPO = [
        ('porcentaje', 'Descuento porcentual (%)'),
        ('fijo',       'Descuento fijo ($)'),
        ('2x1',        '2x1 — lleva 2, paga 1'),
        ('nxprecio',   'N piezas por $X'),
    ]
    APLICA_A = [
        ('producto',  'Producto específico'),
        ('categoria', 'Categoría completa'),
    ]

    nombre      = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True)
    activo      = models.BooleanField(default=True)

    aplica_a  = models.CharField(max_length=20, choices=APLICA_A)
    producto  = models.ForeignKey(
        Producto, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ofertas',
    )
    categoria = models.ForeignKey(
        Categoria, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ofertas',
    )

    tipo       = models.CharField(max_length=20, choices=TIPO)
    valor      = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad_n = models.PositiveIntegerField(null=True, blank=True)

    filtros_atributos = models.JSONField(default=list, blank=True)

    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin    = models.DateField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-activo', 'nombre']

    def __str__(self):
        return self.nombre