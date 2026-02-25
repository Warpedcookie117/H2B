from django.db import models
from django.core.exceptions import ValidationError
from tienda_temp.models import Empleado, Usuario
from django.db.models import Sum


class Categoria(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    padre = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategorias'
    )

    class Meta:
        unique_together = ('nombre', 'padre')
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Temporada(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    # Opcional: rango de fechas (solo para referencia)
    inicio_mes = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–12
    inicio_dia = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–31
    fin_mes = models.PositiveSmallIntegerField(null=True, blank=True)
    fin_dia = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = "Temporada"
        verbose_name_plural = "Temporadas"

    def __str__(self):
        return self.nombre

    def rango(self):
        if self.inicio_mes and self.inicio_dia and self.fin_mes and self.fin_dia:
            return f"{self.inicio_dia}/{self.inicio_mes} → {self.fin_dia}/{self.fin_mes}"
        return "Sin rango definido"
    


class Ubicacion(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    direccion = models.CharField(max_length=255, )

    def __str__(self):
        return self.nombre
    


class Producto(models.Model):
    nombre = models.CharField(max_length=150)
    descripcion = models.TextField()
    precio_mayoreo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_menudeo = models.DecimalField(max_digits=10, decimal_places=2)
    precio_docena = models.DecimalField(max_digits=10, decimal_places=2)
    foto_url = models.ImageField(upload_to='productos/', blank=True, null=True)

    codigo_barras = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Código de barras escaneado o generado automáticamente",
        unique=True
    )

    tipo_codigo = models.CharField(
        max_length=20,
        choices=[
            ('code128', 'Code 128'),
            ('code39', 'Code 39'),
            ('ean13', 'EAN-13'),
            ('ean14', 'EAN-14'),
            ('itf14', 'ITF-14'),
            ('datamatrix', 'DataMatrix'),
        ],
        blank=True,
        null=True,
        help_text="Tipo de código de barras usado",
    )

    categoria_padre = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_padre'
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='productos_hijo'
    )

    temporada = models.ManyToManyField(
        Temporada,
        blank=True,
        related_name='productos'
    )

    dueño = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=False,
        related_name='productos'
    )

    registrado_por = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_registrados'
    )

    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    # ============================================================
    # PROPIEDADES DE INVENTARIO (LAS QUE NECESITAS PARA LOS MODALES)
    # ============================================================

    @property
    def cantidad_total(self):
        """
        Cantidad total del producto en TODAS las ubicaciones.
        """
        return self.inventarios.aggregate(
            total=Sum("cantidad_actual")
        )["total"] or 0

    def cantidad_en_ubicacion(self, ubicacion):
        """
        Cantidad del producto en UNA ubicación específica.
        """
        inv = self.inventarios.filter(ubicacion=ubicacion).first()
        return inv.cantidad_actual if inv else 0

    # ============================================================
    # VALIDACIONES
    # ============================================================
    def clean(self):
        if not self.dueño:
            raise ValidationError({'dueño': 'Todo producto debe tener un dueño asignado.'})

        if self.precio_mayoreo < 0:
            raise ValidationError({'precio_mayoreo': 'El precio de mayoreo no puede ser negativo.'})
        if self.precio_menudeo < 0:
            raise ValidationError({'precio_menudeo': 'El precio de menudeo no puede ser negativo.'})
        if self.precio_docena < 0:
            raise ValidationError({'precio_docena': 'El precio por docena no puede ser negativo.'})
        if self.precio_mayoreo > self.precio_menudeo:
            raise ValidationError({'precio_mayoreo': 'El precio de mayoreo no puede ser mayor que el precio de menudeo.'})
        if self.precio_docena > self.precio_mayoreo:
            raise ValidationError({'precio_docena': 'El precio por docena no puede ser mayor que el precio de mayoreo.'})

    # ============================================================
    # ASIGNACIÓN AUTOMÁTICA
    # ============================================================
    def save(self, *args, **kwargs):
        if self.categoria and self.categoria.padre:
            self.categoria_padre = self.categoria.padre

        super().save(*args, **kwargs)

        

    # Define los atributos que existen para cada subcategoría.
class Atributo(models.Model):
    TIPO_DATOS = [
        ("texto", "Texto"),
        ("numero", "Número"),
    ]

    nombre = models.CharField(max_length=100)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.CASCADE,
        related_name='atributos'
    )
    tipo = models.CharField(max_length=20, choices=TIPO_DATOS, default="texto")

    class Meta:
        unique_together = ('nombre', 'categoria')

    def __str__(self):
        return f"{self.nombre} ({self.categoria.nombre})"


    # Guarda el valor de cada atributo por subcategoría para cada producto
class ValorAtributo(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='valores_atributo')
    atributo = models.ForeignKey(Atributo, on_delete=models.CASCADE)
    valor = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = ('producto', 'atributo')

    def __str__(self):
        return f"{self.atributo.nombre}: {self.valor}"
    


class SolicitudAjuste(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)

    cantidad = models.IntegerField()
    motivo = models.CharField(max_length=200, blank=True)

    estado = models.CharField(
        max_length=20,
        choices=[
            ("pendiente", "Pendiente"),
            ("aprobado", "Aprobado"),
            ("rechazado", "Rechazado"),
        ],
        default="pendiente"
    )

    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Solicitud #{self.id} - {self.producto.nombre}"



    

###CLASES DE INVENTARIO####
class Inventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='inventarios')
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='inventarios')
    cantidad_actual = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('producto', 'ubicacion')

    def __str__(self):
        return f"{self.producto.nombre} en {self.ubicacion.nombre}: {self.cantidad_actual} piezas"
    
    
    
class TransferenciaInventario(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    origen = models.ForeignKey(
        Ubicacion,
        related_name='transferencias_origen',
        on_delete=models.CASCADE
    )
    destino = models.ForeignKey(
        Ubicacion,
        related_name='transferencias_destino',
        on_delete=models.CASCADE
    )
    fecha = models.DateTimeField(auto_now_add=True)
    realizado_por = models.ForeignKey(
        Empleado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Transferencia de Inventario"
        verbose_name_plural = "Transferencias de Inventario"

    def __str__(self):
        return f"Transferencia de {self.cantidad} {self.producto.nombre} ({self.origen} → {self.destino})"

    def clean(self):
        # Validar que origen y destino no sean iguales
        if self.origen == self.destino:
            raise ValidationError("La ubicación de origen y destino no pueden ser iguales.")
        # Validar cantidad positiva
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")


 
 



class MovimientoInventario(models.Model):

    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
        ('ajuste', 'Ajuste'),
    ]

    MOTIVO_MOVIMIENTO = [
        ('devolucion', 'Devolución de cliente'),
        ('compra', 'Compra a proveedor'),
        ('reabastecimiento', 'Reabastecimiento interno'),
        ('nuevo', 'Nuevo producto'),

        ('venta', 'Venta'),
        ('daño', 'Daño'),
        ('perdida', 'Pérdida'),

        ('correccion', 'Corrección de inventario'),
        ('conteo', 'Conteo físico'),

        ('transferencia', 'Transferencia entre ubicaciones'),
    ]

    transferencia = models.ForeignKey(
        "TransferenciaInventario",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="movimientos"
    )

    producto = models.ForeignKey("Producto", on_delete=models.CASCADE, related_name='movimientos')
    tipo = models.CharField(max_length=20, choices=TIPO_MOVIMIENTO)
    motivo = models.CharField(max_length=30, choices=MOTIVO_MOVIMIENTO, null=True, blank=True)
    cantidad = models.PositiveIntegerField()

    origen = models.ForeignKey(
        "Ubicacion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_origen'
    )

    destino = models.ForeignKey(
        "Ubicacion",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos_destino'
    )

    fecha = models.DateTimeField(auto_now_add=True)
    realizado_por = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True)
    class Meta:
        ordering = ['-fecha']
        verbose_name = "Movimiento de Inventario"
        verbose_name_plural = "Movimientos de Inventario"

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.producto.nombre} ({self.cantidad})"

    def clean(self):
        # Cantidad válida
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor que cero.")

        # Validaciones estructurales según tipo
        if self.tipo == 'entrada' and not self.destino:
            raise ValidationError("Las entradas requieren una ubicación destino.")

        if self.tipo == 'salida' and not self.origen:
            raise ValidationError("Las salidas requieren una ubicación origen.")

        if self.tipo == 'ajuste' and not self.destino:
            raise ValidationError("Los ajustes requieren una ubicación destino.")
