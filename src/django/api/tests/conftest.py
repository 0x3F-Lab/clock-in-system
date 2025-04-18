import pytest
from datetime import timedelta
from django.utils.timezone import now
from auth_app.models import User, Activity, KeyValueStore

# Default scope if functional (i.e. after every single test the database resets)


@pytest.fixture
def employee(db):
    """
    Create a basic employee fixture.
    """
    employee = User.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone_number="1234567890",
        clocked_in=False,
        is_active=True,
        is_manager=False,
    )
    employee.set_pin("1234")  # Set the hashed pin
    employee.save()
    return employee


@pytest.fixture
def inactive_employee(db):
    """
    Create a basic employee fixture that is INACTIVE.
    """
    employee = User.objects.create(
        first_name="Mary",
        last_name="Jane",
        email="mary.jane@example.com",
        phone_number="1234567555",
        clocked_in=False,
        is_active=False,
        is_manager=False,
    )
    employee.set_pin("1234")  # Set the hashed pin
    employee.save()
    return employee


@pytest.fixture
def clocked_in_employee(db):
    """
    Create an employee who is already clocked in.
    """
    employee = User.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone_number="0987654321",
        clocked_in=True,
        is_active=True,
        is_manager=False,
    )
    employee.set_pin("1234")  # Set the hashed pin
    employee.save()

    login_time = now() - timedelta(hours=2)

    activity = Activity.objects.create(
        employee_id=employee,
        login_time=login_time,
    )

    # Update login_timestamp (cant be passed when creating object)
    Activity.objects.filter(id=activity.id).update(
        login_timestamp=now() - timedelta(hours=2)
    )

    return employee


@pytest.fixture
def manager(db):
    """
    Creates a manager user for testing.
    """
    manager = User.objects.create(
        first_name="Manager",
        last_name="Test",
        email="manager.test@example.com",
        phone_number="1234567522",
        clocked_in=False,
        is_active=True,
        is_manager=True,
    )
    manager.set_pin("1234")  # Set the hashed pin
    manager.save()
    return manager


@pytest.fixture
def store_location(db):
    """
    Creates the required keys in the KeyValueStore table for clocking
    """
    store_lat = KeyValueStore.objects.create(
        key="store_latitude",
        value="1.0",
    )

    store_lon = KeyValueStore.objects.create(
        key="store_longitude",
        value="1.0",
    )

    allowable_dist = KeyValueStore.objects.create(
        key="allowable_clocking_dist_m",
        value="5",
    )

    return store_lat, store_lon, allowable_dist


@pytest.fixture
def api_client():
    """
    Return an instance of Django's test client.
    """
    from rest_framework.test import APIClient

    return APIClient()
