from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0014_producto_costo'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='producto',
            name='embedding',
        ),
        migrations.AddField(
            model_name='producto',
            name='phash',
            field=models.CharField(blank=True, max_length=16, null=True),
        ),
    ]
