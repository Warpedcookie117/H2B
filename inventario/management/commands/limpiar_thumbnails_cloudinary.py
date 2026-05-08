"""
Borra los thumbnails huérfanos que se subieron a Cloudinary por error
y limpia el campo foto_thumbnail en la DB.

NUNCA toca foto_url (los originales).

Uso:
    python manage.py limpiar_thumbnails_cloudinary
    python manage.py limpiar_thumbnails_cloudinary --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from inventario.models import Producto


class Command(BaseCommand):
    help = "Borra los thumbnails huérfanos de Cloudinary y limpia foto_thumbnail."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo lista lo que se borraría, sin tocar nada.",
        )

    def handle(self, *args, **opts):
        dry = opts["dry_run"]

        qs = (
            Producto.objects
            .exclude(Q(foto_thumbnail__isnull=True) | Q(foto_thumbnail=""))
        )
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                "Nada que limpiar — no hay productos con foto_thumbnail."
            ))
            return

        self.stdout.write(f"{total} productos con thumbnail por limpiar.")
        if dry:
            self.stdout.write(self.style.WARNING("DRY RUN — no se ejecuta nada."))
            for p in qs.iterator():
                self.stdout.write(f"  • #{p.id} {p.nombre} → {p.foto_thumbnail.name}")
            return

        ok = 0
        errores = []

        for p in qs.iterator():
            try:
                # field.delete(save=False) usa el storage backend (Cloudinary
                # en producción, FileSystem en local) para borrar el archivo.
                # No guarda el modelo — eso lo hacemos con update() para
                # esquivar señales y posibles efectos secundarios.
                p.foto_thumbnail.delete(save=False)
                Producto.objects.filter(pk=p.pk).update(foto_thumbnail="")
                ok += 1
                if ok % 25 == 0 or ok == total:
                    self.stdout.write(f"  {ok}/{total}…")
            except Exception as e:
                errores.append((p.id, p.nombre, str(e)))

        self.stdout.write(self.style.SUCCESS(
            f"Limpiados {ok}/{total}."
        ))
        if errores:
            self.stdout.write(self.style.WARNING(f"Errores: {len(errores)}"))
            for pid, nombre, err in errores[:20]:
                self.stdout.write(f"  • #{pid} {nombre}: {err}")
            if len(errores) > 20:
                self.stdout.write(f"  … y {len(errores) - 20} más")
