"""
Borra IdempotencyKey viejos para que la tabla no crezca sin control.

Cada operación (venta POS, registrar producto, agregar inventario) crea
una fila. Las llaves más viejas que --dias-de-vida ya cumplieron su
propósito y solo ocupan espacio.

Uso:
    python manage.py limpiar_idempotency_keys
    python manage.py limpiar_idempotency_keys --dry-run
    python manage.py limpiar_idempotency_keys --dias 7
"""

from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from ventas.models import IdempotencyKey


class Command(BaseCommand):
    help = "Borra IdempotencyKey con más de N días de antigüedad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=30,
            help="Antigüedad mínima en días para borrar (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo cuenta lo que se borraría, sin tocar nada.",
        )

    def handle(self, *args, **opts):
        dias = opts["dias"]
        dry  = opts["dry_run"]

        corte = timezone.now() - timedelta(days=dias)
        qs    = IdempotencyKey.objects.filter(created_at__lt=corte)
        total = qs.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS(
                f"Nada que limpiar — no hay llaves con más de {dias} días."
            ))
            return

        self.stdout.write(f"{total} llaves con más de {dias} días por borrar.")

        if dry:
            self.stdout.write(self.style.WARNING("DRY RUN — no se ejecuta el delete."))
            from django.db.models import Count
            for fila in qs.values("operacion").annotate(c=Count("key")):
                self.stdout.write(f"  • {fila['operacion']}: {fila['c']}")
            return

        eliminados, _ = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f"Borradas {eliminados} llaves idempotentes."
        ))
