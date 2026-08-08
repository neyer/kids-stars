from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stars.models import Kid, StarTransaction


class Command(BaseCommand):
    help = "Delete all transactions for a kid and set their balance to a specific value."

    def add_arguments(self, parser):
        parser.add_argument("kid_name", help="Name of the kid (as stored in Kid.name)")
        parser.add_argument("balance", type=int, help="New balance to set")
        parser.add_argument(
            "--reason",
            default="Balance reset",
            help="Reason recorded on the adjustment transaction",
        )

    def handle(self, *args, **options):
        kid_name = options["kid_name"]
        balance = options["balance"]
        reason = options["reason"]

        try:
            kid = Kid.objects.get(name=kid_name)
        except Kid.DoesNotExist:
            raise CommandError(f"No kid named {kid_name!r}")

        with transaction.atomic():
            deleted, _ = kid.transactions.all().delete()
            if balance != 0:
                StarTransaction.objects.create(kid=kid, delta=balance, reason=reason)

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted} transaction(s) for {kid.name}; balance is now {kid.balance}"
            )
        )
