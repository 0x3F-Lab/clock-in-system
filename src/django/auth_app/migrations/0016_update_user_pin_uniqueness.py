from django.db import migrations
import random


def set_unique_pins(apps, schema_editor):
    User = apps.get_model('auth_app', 'User')
    users = User.objects.all()

    for user in users:
        pin = f"{random.randint(0, 999999):06}"  # Format to always generate a 6-digit string
        while User.objects.filter(pin=pin).exists():  # Check if the pin already exists
            pin = f"{random.randint(0, 999999):06}"  # If it does, generate a new one
        user.pin = pin  # Directly assign the pin
        user.save()  # Save the user after setting the pin


def reset_pins(apps, schema_editor):
    User = apps.get_model('auth_app', 'User')
    users = User.objects.all()

    for user in users:
        user.pin = '1234'  # Reset all pins to '1234'
        user.save()


class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0015_set_activity_store_non_nullable'),
    ]

    operations = [
        migrations.RunPython(set_unique_pins, reverse_code=reset_pins),
    ]
