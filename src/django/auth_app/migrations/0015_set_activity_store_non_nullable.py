# Generated by Django 5.2 on 2025-04-21 13:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("auth_app", "0014_set_default_store_for_activities"),
    ]

    operations = [
        migrations.AlterField(
            model_name="activity",
            name="store",
            field=models.ForeignKey(
                default=1,
                on_delete=django.db.models.deletion.CASCADE,
                to="auth_app.store",
            ),
        ),
    ]
