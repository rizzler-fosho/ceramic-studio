"""
Management command: seed_kilns
==============================
Populates the database with three fictitious kilns so the kiln status strip
in the navbar has something to display before real IoT data arrives.

Usage:
    python manage.py seed_kilns            # idempotent — safe to run again
    python manage.py seed_kilns --reset    # wipe existing kilns first
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from ceramics.models import Kiln


SEED_DATA = [
    {
        "number": 1,
        "name": "Ol' Reliable",
        "temp": 2287.0,
        "cone_fire": "Cone 10",
        "status": "firing",
        "notes": "Stoneware reduction load — 42 pieces. Expected finish ~11 pm.",
    },
    {
        "number": 2,
        "name": "The Bisque Oven",
        "temp": 712.0,
        "cone_fire": "Cone 06",
        "status": "cooling",
        "notes": "Post-bisque cooldown. Do not open before 200°F.",
    },
    {
        "number": 3,
        "name": "The Baby",
        "temp": 74.0,
        "cone_fire": "",
        "status": "idle",
        "notes": "Empty — next load scheduled for Thursday.",
    },
]


class Command(BaseCommand):
    help = "Seed fictitious kiln data for development / demo purposes"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing kilns before seeding",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = Kiln.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Deleted {deleted} existing kiln(s)."))

        created_count = 0
        for data in SEED_DATA:
            kiln, created = Kiln.objects.update_or_create(
                number=data["number"],
                defaults={k: v for k, v in data.items() if k != "number"},
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Created: {kiln}"))
            else:
                self.stdout.write(f"  Updated: {kiln}")

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. {created_count} kiln(s) created, "
            f"{len(SEED_DATA) - created_count} updated."
        ))
