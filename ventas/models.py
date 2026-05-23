from django.db import models

from django.db import models
from tienda_temp.models import Empleado
from inventario.models import Producto, Ubicacion
from sucursales.models import Caja
from inventario.models import Categoria


class IdempotencyKey(models.Model):
    """
    Token único por operación para prevenir reintentos accidentales que
    crearían registros duplicados (ej. doble-tap en 'Cobrar', reenvío de
    formulario al volver con flecha del browser, retry de red).
    """

    OPERACION_CHOICES = [
        ("venta", "Venta POS"),
        ("nuevo_producto", "Registro de producto"),
        ("agregar_inventario", "Agregar inventario"),
    ]

    key            = models.CharField(max_length=64, primary_key=True)
    operacion      = models.CharField(max_length=32, choices=OPERACION_CHOICES)
    empleado       = models.ForeignKey(Empleado, on_delete=models.SET_NULL, null=True, blank=True)
    status_code    = models.IntegerField(default=200)
    response_json  = models.JSONField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["operacion", "-created_at"]),
        ]

    @classmethod
    def claim(cls, key, operacion, empleado=None):
        """
        Intenta reservar la llave. Devuelve (objeto, respuesta_cacheada):
          - (obj, None) → llave nueva, procede a ejecutar la operación
          - (None, dict) → ya existía; el dict es la respuesta a devolver
                          (cacheada con éxito previo, o "en curso" con 409)
        """
        from django.db import IntegrityError, transaction
        if not key:
            return None, None
        try:
            with transaction.atomic():
                obj = cls.objects.create(key=key, operacion=operacion, empleado=empleado)
            return obj, None
        except IntegrityError:
            existing = cls.objects.filter(key=key).first()
            if not existing or existing.response_json is None:
                # En curso (otro request acaba de claim sin terminar todavía)
                return None, {
                    "__status": 409,
                    "success": False,
                    "errors": ["Operación duplicada en curso. Espera un momento."],
                }
            cached = dict(existing.response_json)
            cached["__status"] = existing.status_code
            return None, cached

    def commit(self, response_data, status_code=200):
        """Guarda la respuesta para devolverla en reintentos futuros."""
        self.status_code = status_code
        self.response_json = response_data
        self.save(update_fields=["status_code", "response_json"])

    def release(self):
        """Borra la llave si la operación falló — permite reintento."""
        self.delete()


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
    # Filtros sobre el producto que DISPARA la promoción (ej. tamaño=350g).
    # Solo aplica cuando tipo_condicion == 'categoria'. Misma forma:
    # [{"nombre": ..., "valor": ...}]
    filtros_disparador = models.JSONField(default=list, blank=True)
    # Nombres de atributos que deben COINCIDIR entre disparador y regalo
    # (ej. ["marca"] = el regalo debe ser de la misma marca del disparador).
    # Solo aplica con tipo_condicion='categoria' + tipo_resultado='regalo_variante'.
    atributos_enlazados = models.JSONField(default=list, blank=True)

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


class ConfigTicket(models.Model):
    """
    Singleton — siempre acceder con ConfigTicket.get().
    Guarda todos los textos y opciones que aparecen en el ticket impreso.
    """
    # ---- ENCABEZADO ----
    nombre_empresa  = models.CharField(max_length=30, default="COMERCIALIZADORA MODELO")
    telefono        = models.CharField(max_length=30, blank=True, default="")
    direccion       = models.CharField(max_length=30, blank=True, default="")

    # ---- ARTÍCULOS ----
    mostrar_id_producto  = models.BooleanField(default=True,  help_text="Muestra #123 antes del nombre del producto")
    mostrar_tipo_precio  = models.BooleanField(default=True,  help_text='Muestra la línea "PRECIO MAYOREO APLICADO"')
    texto_mayoreo        = models.CharField(max_length=30, default="PRECIO MAYOREO APLICADO")
    texto_menudeo        = models.CharField(max_length=30, default="PRECIO MENUDEO APLICADO")

    # ---- PIE ----
    mensaje_pie            = models.CharField(max_length=30, default="NO CAMBIOS NI DEVOLUCIONES")
    mensaje_agradecimiento = models.CharField(max_length=30, default="GRACIAS POR TU COMPRA")

    class Meta:
        verbose_name = "Configuración de Ticket"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Config Ticket — {self.nombre_empresa}"


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