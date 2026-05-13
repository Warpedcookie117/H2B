from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0016_producto_foto_thumbnail_alter_producto_descripcion'),
    ]

    operations = [
        migrations.AlterField(
            model_name='producto',
            name='codigo_barras',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    'Código de barras escaneado o generado automáticamente. '
                    'Puede repetirse entre variantes del mismo producto físico; '
                    'la unicidad real la garantiza firma_unica.'
                ),
                max_length=50,
                null=True,
            ),
        ),
    ]
