from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0008_ubicacion_activa_ubicacion_sucursal_ubicacion_tipo_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='producto',
            name='embedding',
        ),
        migrations.AddField(
            model_name='producto',
            name='embedding',
            field=models.JSONField(blank=True, null=True),
        ),
    ]