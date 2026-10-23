import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tienda_temp", "0002_empleado_prioridad_cambio"),
        ("ventas", "0018_deuda_pago_en_corto"),
    ]

    operations = [
        # default=False: las ventas que ya existen se quedan con la regla
        # anterior (deuda); solo POSService.crear_venta marca las nuevas.
        migrations.AddField(
            model_name="venta",
            name="pago_en_seco",
            field=models.BooleanField(default=False),
        ),
        # Vacío en las ventas que ya existen: su receptora sigue siendo la
        # que más vendió, así que los cortes viejos no cambian.
        migrations.AddField(
            model_name="venta",
            name="clip_de",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                related_name="+", to="tienda_temp.empleado",
            ),
        ),
    ]
