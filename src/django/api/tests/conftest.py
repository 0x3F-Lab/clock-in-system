import pytest

from datetime import timedelta
from django.urls import reverse
from django.utils.timezone import now, localtime
from rest_framework.test import APIClient
from auth_app.models import User, Activity, Store, StoreUserAccess, Notification

# Default scope if functional (i.e. after every single test the database resets)


@pytest.fixture
def store(db):
    """
    Create an active store.
    """
    return Store.objects.create(
        name="Test Store",
        code="TST001",
        location_street="123 Main St",
        location_latitude=1.0,
        location_longitude=1.0,
        allowable_clocking_dist_m=500,
        store_pin="000",
        is_active=True,
    )


@pytest.fixture
def employee(db, store):
    """
    Create a basic active employee associated with a store.
    """
    employee = User.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone_number="1234567890",
        is_active=True,
        is_manager=False,
        is_setup=True,
    )
    employee.set_password("testpassword")
    employee.set_unique_pin()
    employee.save()

    return employee


@pytest.fixture
def inactive_employee(db, store):
    """
    Create a basic employee fixture that is INACTIVE.
    """
    employee = User.objects.create(
        first_name="Mary",
        last_name="Jane",
        email="mary.jane@example.com",
        phone_number="1234567555",
        is_active=False,
        is_manager=False,
        is_setup=True,
    )
    employee.set_password("testpassword")
    employee.set_unique_pin()
    employee.save()

    return employee


@pytest.fixture
def clocked_in_employee(db, store):
    """
    Create an employee who is already clocked in at a store.
    """
    employee = User.objects.create(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone_number="0987654321",
        is_active=True,
        is_manager=False,
        is_setup=True,
    )
    employee.set_password("testpassword")
    employee.set_unique_pin()
    employee.save()

    StoreUserAccess.objects.create(user=employee, store=store)

    login_time = localtime(now()) - timedelta(hours=2)

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=login_time,
        login_timestamp=login_time,
    )

    return employee


@pytest.fixture
def manager(db, store):
    """
    Creates a manager user for testing.
    """
    manager = User.objects.create(
        first_name="Manager",
        last_name="Test",
        email="manager.test@example.com",
        phone_number="1234567522",
        is_active=True,
        is_manager=True,
        is_setup=True,
    )
    manager.set_password("testpassword")
    manager.set_unique_pin()
    manager.save()

    return manager


@pytest.fixture
def notification_all(employee, inactive_employee, clocked_in_employee, manager):
    """
    Creates a notification and sends it to all users in the DB with respective receipts
    """
    # Make a notification with no sender (from system)
    notif = Notification.send_system_notification_to_all(
        title="System Notification",
        message="This is a system notification to all users.",
    )

    return notif


@pytest.fixture
def store_associate_employee(db, store, employee):
    """
    Creates an association link between store and the employee.
    """
    StoreUserAccess.objects.create(user=employee, store=store)


@pytest.fixture
def store_associate_manager(db, store, manager):
    """
    Creates an association link between store and the manager.
    """
    StoreUserAccess.objects.create(user=manager, store=store)


@pytest.fixture
def store_associate_inactive_employee(db, store, inactive_employee):
    """
    Creates an association link between store and the inactive employee.
    """
    StoreUserAccess.objects.create(user=inactive_employee, store=store)


@pytest.fixture
def logged_in_employee(api_client, employee):
    """
    Fixture to log in the employee through the login page, using the Django session system.
    """
    # Define login URL and credentials for the user
    url = reverse("login")
    data = {
        "email": employee.email,  # Assuming `user` has an `email` field
        "password": "testpassword",  # Password for ALL test accounts
    }

    # Send a POST request to log the user in
    response = api_client.post(url, data)

    # Assert login was successful (check for a redirect after login)
    assert response.status_code == 302

    # Ensure the session is set correctly
    assert "user_id" in api_client.session

    return api_client


@pytest.fixture
def logged_in_manager(api_client, manager):
    """
    Fixture to log in the manager through the login page, using the Django session system.
    """
    url = reverse("login")
    data = {
        "email": manager.email,
        "password": "testpassword",
    }

    response = api_client.post(url, data)
    assert response.status_code == 302
    assert "user_id" in api_client.session
    return api_client


@pytest.fixture
def logged_in_clocked_in_employee(api_client, clocked_in_employee):
    """
    Fixture to log in the clocked in employee through the login page, using the Django session system.
    """
    url = reverse("login")
    data = {
        "email": clocked_in_employee.email,
        "password": "testpassword",
    }

    response = api_client.post(url, data)
    assert response.status_code == 302
    assert "user_id" in api_client.session
    return api_client


@pytest.fixture
def api_client():
    """
    Return an instance of Django's test client.
    """
    return APIClient()
