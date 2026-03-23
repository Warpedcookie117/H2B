from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0006_alter_producto_embedding'),
    ]

    operations = [
        migrations.RunSQL(
            """
            ALTER TABLE inventario_producto
            ALTER COLUMN embedding
            TYPE jsonb
            USING to_jsonb(embedding);
            """,
            reverse_sql="""
            ALTER TABLE inventario_producto
            ALTER COLUMN embedding
            TYPE double precision[];
            """
        )
    ]
