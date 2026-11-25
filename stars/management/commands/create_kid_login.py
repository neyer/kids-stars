import getpass

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from stars.models import Kid


class Command(BaseCommand):
    help = "Create (or reset) a login for a kid so they can request stars."

    def add_arguments(self, parser):
        parser.add_argument("kid_name", help="Name of the kid (as stored in Kid.name)")
        parser.add_argument("username", help="Username the kid will log in with")
        parser.add_argument("--password", help="Password (prompted for if omitted)")

    def handle(self, *args, **options):
        try:
            kid = Kid.objects.get(name__iexact=options["kid_name"])
        except Kid.DoesNotExist:
            raise CommandError(f"No kid named {options['kid_name']!r}.")

        username = options["username"]
        existing = User.objects.filter(username=username).first()
        if existing is not None and kid.user_id != existing.id:
            raise CommandError(f"Username {username!r} is already taken by another account.")

        password = options["password"]
        if not password:
            password = getpass.getpass(f"Password for {username}: ")
            if password != getpass.getpass("Again: "):
                raise CommandError("Passwords didn't match.")
        if not password:
            raise CommandError("Password can't be empty.")

        with transaction.atomic():
            if kid.user is not None and kid.user.username != username:
                # Rename the kid's existing account rather than leaving an orphan.
                user = kid.user
                user.username = username
            else:
                user = existing or User(username=username)
            user.is_staff = False
            user.is_superuser = False
            user.set_password(password)
            user.save()
            kid.user = user
            kid.save(update_fields=["user"])

        self.stdout.write(self.style.SUCCESS(f"{kid.name} can now log in as {username!r}."))
