from django.core.management.base import BaseCommand

from stars.models import ApiToken


class Command(BaseCommand):
    help = "Create an API token for another app. The key is printed once and not stored."

    def add_arguments(self, parser):
        parser.add_argument("name", help="Which app will use this token, e.g. 'Home Assistant'")

    def handle(self, *args, **options):
        token, key = ApiToken.create(options["name"])
        self.stdout.write(f"Created API token for {token.name!r}. Save this key now; it won't be shown again:\n")
        self.stdout.write(self.style.SUCCESS(key))
