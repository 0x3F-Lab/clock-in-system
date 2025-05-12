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


def delete_default_store_and_unassign(apps, schema_editor):
    Store = apps.get_model('auth_app', 'Store')
    Activity = apps.get_model('auth_app', 'Activity')

    try:
        # Find the Default Store
        default_store = Store.objects.get(code='DEFSTR001')

        # Remove store reference from Activities that pointed to the Default Store
        Activity.objects.filter(store=default_store).update(store=None)

        # Now delete the Default Store
        default_store.delete()

    except Store.DoesNotExist:
        # If the store somehow doesn't exist, just skip
        pass

class Migration(migrations.Migration):

    dependencies = [
        ('auth_app', '0013_create_store_and_storeuseraccess_tables'),
    ]

    operations = [
        migrations.RunPython(create_default_store_and_assign, reverse_code=delete_default_store_and_unassign),
    ]
