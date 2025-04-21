from django.db import migrations

def create_default_store_and_assign(apps, schema_editor):
    Store = apps.get_model('auth_app', 'Store')
    Activity = apps.get_model('auth_app', 'Activity')

    default_store = Store.objects.create(
        name='Default Store',
        code='DEFSTR001',
        location_street='Default Street',
        location_latitude='0.0',
        location_longitude='0.0',
        store_pin='1234',
        is_active=False,
    )

    Activity.objects.update(store=default_store)

class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0013_create_store_and_storeuseraccess_tables'),
    ]

    operations = [
        migrations.RunPython(create_default_store_and_assign),
    ]
