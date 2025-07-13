from django.core.management.base import BaseCommand
from django.utils.timezone import now
from datetime import timedelta
import random

from auth_app.models import User, Store, StoreUserAccess, Activity


class Command(BaseCommand):
    help = "Populate the dev DB with a dummy store, a manager, and several employees"

    def handle(self, *args, **options):
        # 1) Create or get the Dev Store
        store, created = Store.objects.get_or_create(
            code="POOPSTORE",
            defaults={
                "name": "Penis Store",
                "location_street": "123 Poop Lane",
                "location_latitude": 0.0,
                "location_longitude": 0.0,
                "allowable_clocking_dist_m": 500,
                "store_pin": "123456",
                "is_active": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'Created' if created else 'Found'} store: {store}")
        )

        # 2) Create manager
        mgr_email = "manager@poop.com"
        if not User.objects.filter(email=mgr_email).exists():
            mgr = User.objects.create(
                first_name="poopy",
                last_name="booty",
                email=mgr_email,
                phone_number="0000000000",
                is_active=True,
                is_manager=True,
                is_setup=True,
            )
            mgr.set_password("password")
            mgr.set_unique_pin()
            mgr.save()
            StoreUserAccess.objects.create(user=mgr, store=store)
            self.stdout.write(
                self.style.SUCCESS(f"Created manager: {mgr} with the PIN: {mgr.pin}")
            )
        else:
            self.stdout.write(self.style.WARNING(f"Manager {mgr_email} already exists"))

        # 3) Create a handful of employees
        for i in range(1, 6):
            email = f"user{i}@example.com"
            if User.objects.filter(email=email).exists():
                self.stdout.write(self.style.WARNING(f"Skipping existing: {email}"))
                continue

            user = User.objects.create(
                first_name=f"Poopy{i}",
                last_name="Balls",
                email=email,
                phone_number=f"04{random.randint(10000000,99999999)}",
                is_active=True,
                is_manager=False,
                is_setup=True,
            )
            user.set_password("password")
            user.set_unique_pin()
            user.save()
            StoreUserAccess.objects.create(user=user, store=store)
            self.stdout.write(
                self.style.SUCCESS(f"Created employee: {user} with the PIN: {user.pin}")
            )

        # 4) (Optional) Clock one in for testing the clocked-in view
        one = User.objects.filter(email="user1@example.com").first()
        if (
            one
            and not Activity.objects.filter(
                employee=one, logout_time__isnull=True
            ).exists()
        ):
            login = now() - timedelta(hours=1)
            Activity.objects.create(
                employee=one,
                store=store,
                login_time=login,
                login_timestamp=login,
            )
            self.stdout.write(self.style.SUCCESS(f"Clocked in: {one}"))

        self.stdout.write(self.style.SUCCESS("Dev DB seeding complete!"))
