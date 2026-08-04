from django.db import migrations

DEFAULT_KIDS = ["Allie", "Paul", "Charlotte"]

DEFAULT_QUICK_ACTIONS = [
    ("Dinner on time", 1),
    ("Bedtime routine", 1),
    ("Helped without being asked", 1),
    ("Screen time violation", -10),
]


def seed_defaults(apps, schema_editor):
    Kid = apps.get_model("stars", "Kid")
    QuickAction = apps.get_model("stars", "QuickAction")

    for order, name in enumerate(DEFAULT_KIDS):
        Kid.objects.get_or_create(name=name, defaults={"order": order})

    for order, (label, delta) in enumerate(DEFAULT_QUICK_ACTIONS):
        QuickAction.objects.get_or_create(
            label=label, delta=delta, defaults={"order": order}
        )


def remove_defaults(apps, schema_editor):
    Kid = apps.get_model("stars", "Kid")
    QuickAction = apps.get_model("stars", "QuickAction")
    Kid.objects.filter(name__in=DEFAULT_KIDS).delete()
    for label, delta in DEFAULT_QUICK_ACTIONS:
        QuickAction.objects.filter(label=label, delta=delta).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("stars", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_defaults, remove_defaults),
    ]
