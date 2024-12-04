import pytest
from datetime import timedelta
from django.utils.timezone import now
from auth_app.models import User, Activity

# Default scope if functional (i.e. after every single test the database resets)


@pytest.fixture
def employee(db):
    """
    Create a basic employee fixture.
    """
    return User.objects.create(
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone_number="1234567890",
        clocked_in=False,
        is_active=True,
        is_manager=False,
    )


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
    Activity.objects.create(
        employee_id=employee,
        login_time=now() - timedelta(hours=3),  # Set login_time to 3 hours ago
    )
    return employee


@pytest.fixture
def api_client():
    """
    Return an instance of Django's test client.
    """
    from rest_framework.test import APIClient

    return APIClient()
