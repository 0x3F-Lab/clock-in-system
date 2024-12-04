import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_view(client):
    """
    Test the login view of the Django application without authentication.
    """
    url = reverse("login")  # Resolve the URL for the login view
    response = client.get(url)  # Make a GET request using pytest's client

    # Check the response
    assert response.status_code == 200  # Ensure the response is HTTP 200 OK
    assert b"Login" in response.content  # Check if "Login" is in the response
