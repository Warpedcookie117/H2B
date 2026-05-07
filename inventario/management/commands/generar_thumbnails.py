"""
Genera el campo foto_thumbnail para productos que ya tienen foto_url
pero todavía no tienen su versión pequeña.

Uso:
    python manage.py generar_thumbnails
    python manage.py generar_thumbnails --rehacer   (regenera incluso si ya existe)

NUNCA modifica foto_url (la original).
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from inventario.models import Producto
from inventario.services.imagen_service import generar_thumbnail


class Command(BaseCommand):
    help = "Genera thumbnails para productos que tengan foto_url pero no foto_thumbnail."

    def add_arguments(self, parser):
        parser.add_argument(
            "--rehacer",
            action="store_true",
            help="Regenerar thumbnails incluso si ya existen.",
        )

    def handle(self, *args, **opts):
        rehacer = opts["rehacer"]

        qs = Producto.objects.exclude(foto_url="").exclude(foto_url__isnull=True)
        if not rehacer:
            qs = qs.filter(Q(foto_thumbnail__isnull=True) | Q(foto_thumbnail=""))

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "Nada que hacer — todos los productos con foto ya tienen thumbnail."
            ))
            return

        self.stdout.write(f"Generando thumbnails para {total} productos…")

        ok = 0
        fallaron = []
        for i, p in enumerate(qs.iterator(), 1):
            try:
                content_file, nombre = generar_thumbnail(p.foto_url)
                if content_file is None:
                    fallaron.append((p.id, p.nombre, "no se pudo abrir la imagen"))
                    continue
                # save=False evita doble llamada a Producto.save()
                p.foto_thumbnail.save(nombre, content_file, save=False)
                Producto.objects.filter(pk=p.pk).update(
                    foto_thumbnail=p.foto_thumbnail.name
                )
                ok += 1
                if i % 25 == 0 or i == total:
                    self.stdout.write(f"  {i}/{total}…")
            except Exception as e:
                fallaron.append((p.id, p.nombre, str(e)))

        self.stdout.write(self.style.SUCCESS(f"OK — {ok}/{total} thumbnails generados."))
        if fallaron:
            self.stdout.write(self.style.WARNING(f"Fallaron {len(fallaron)}:"))
            for pid, nombre, err in fallaron[:20]:
                self.stdout.write(f"  • #{pid} {nombre}: {err}")
            if len(fallaron) > 20:
                self.stdout.write(f"  ... y {len(fallaron) - 20} más")
