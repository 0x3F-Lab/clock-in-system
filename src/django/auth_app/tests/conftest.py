import pytest
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


# @pytest.fixture
# def authenticated_client(client, create_user):
#     """Fixture to provide an authenticated client"""
#     client.login(username="testuser", password="password123")
#     return client
