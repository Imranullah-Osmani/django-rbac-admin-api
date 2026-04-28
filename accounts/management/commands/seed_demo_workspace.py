from django.core.management.base import BaseCommand

from config.bootstrap import ensure_demo_workspace


class Command(BaseCommand):
    help = "Seed a small demo organization and operator set for portfolio walkthroughs."

    def handle(self, *args, **options):
        summary = ensure_demo_workspace()
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {summary['org_units']} organization units and {summary['demo_users']} demo users."
            )
        )
