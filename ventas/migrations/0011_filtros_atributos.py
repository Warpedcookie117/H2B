from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ventas', '0010_add_oferta'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='promocion',
            name='filtro_atributo_nombre',
        ),
        migrations.RemoveField(
            model_name='promocion',
            name='filtro_atributo_valor',
        ),
        migrations.AddField(
            model_name='promocion',
            name='filtros_atributos',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='oferta',
            name='filtros_atributos',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
