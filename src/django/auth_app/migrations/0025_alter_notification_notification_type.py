# Generated by Django 5.2 on 2025-05-17 07:10

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_app", "0024_notification_broadcast_to_store"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="notification_type",
            field=models.CharField(
                choices=[
                    ("system_alert", "System Alert"),
                    ("automatic_alert", "Automatic Alert"),
                    ("manager_note", "Manager Note"),
                    ("schedule_change", "Schedule Change"),
                    ("general", "General"),
                    ("emergency", "Emergency"),
                ],
                default="general",
                help_text="The type of notification",
                max_length=50,
            ),
        ),
    ]
