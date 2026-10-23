"""
Persistencia de la caja chica (Django). Las reglas no viven aquí: viven en
domain/ y application/; infrastructure/repositorios.py traduce entre estos
modelos y las entidades del dominio.
"""
from django.db import models
from django.db.models import Q
from django.utils import timezone

from caja_chica.domain.movimientos import TipoMovimiento


class PersonaVale(models.Model):
    """
    A quién se le da vale. No es un usuario del sistema: no todos los
    empleados tienen cuenta. La clave (sin mayúsculas ni acentos) es única,
    así no se repite la misma persona escrita de dos formas.
    """
    nombre = models.CharField(max_length=60)
    clave = models.CharField(max_length=60, unique=True)
    creada_por = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="+")
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["clave"]
        verbose_name = "Persona con vale"
        verbose_name_plural = "Personas con vale"

    def __str__(self):
        return self.nombre


class MovimientoCaja(models.Model):
    """
    Un vale o un gasto: dinero que salió de la cajita de `descontado_a` (la
    responsable de servicios cuando se registró) en la caja `caja`. Al cerrar
    el corte de esa caja queda ligado a él (`corte`). Eliminarlo no lo borra:
    queda marcado y deja de contar en todos lados.
    """
    TIPOS = [(TipoMovimiento.VALE.value, "Vale"), (TipoMovimiento.GASTO.value, "Gasto")]

    tipo = models.CharField(max_length=10, choices=TIPOS)
    monto = models.DecimalField(max_digits=10, decimal_places=2)
    persona = models.ForeignKey(PersonaVale, on_delete=models.PROTECT, null=True, blank=True,
                                related_name="vales")
    descripcion = models.CharField(max_length=150, blank=True)

    caja = models.ForeignKey("sucursales.Caja", on_delete=models.SET_NULL, null=True, related_name="+")
    caja_nombre = models.CharField(max_length=100, blank=True)   # snapshot
    descontado_a = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True,
                                     related_name="+")
    descontado_a_nombre = models.CharField(max_length=150)       # snapshot
    registrado_por = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True,
                                       related_name="+")
    registrado_por_nombre = models.CharField(max_length=150)     # snapshot
    fecha = models.DateTimeField(default=timezone.now)
    corte = models.ForeignKey("ventas.CorteCaja", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="movimientos_caja_chica")

    # Correcciones de una dueña.
    monto_original = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    editado_por = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="+")
    editado_en = models.DateTimeField(null=True, blank=True)
    eliminado_por = models.ForeignKey("tienda_temp.Empleado", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="+")
    eliminado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-fecha", "-id"]
        indexes = [
            models.Index(fields=["caja", "corte"], name="cajachica_caja_corte"),
            models.Index(fields=["fecha"], name="cajachica_fecha"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(monto__gt=0), name="cajachica_monto_positivo"),
            models.CheckConstraint(
                condition=(Q(tipo=TipoMovimiento.VALE.value, persona__isnull=False)
                           | Q(tipo=TipoMovimiento.GASTO.value, persona__isnull=True)),
                name="cajachica_vale_con_persona",
            ),
        ]
        verbose_name = "Movimiento de caja chica"
        verbose_name_plural = "Movimientos de caja chica"

    def __str__(self):
        return f"{self.get_tipo_display()} ${self.monto} ({self.caja_nombre})"
