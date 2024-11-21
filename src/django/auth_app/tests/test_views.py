import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_login_view(client):
    """
    This test checks if the login view of the Django application is accessible and returns the expected response.
    """
    url = reverse("login")  # Get the URL for the `login` view
    response = client.get(url)  # Use Django's test client to send a GET request

    # Check response
    assert response.status_code == 200  # Verify it returns a 200 OK
    assert (
        b"Login" in response.content
    )  # Check if the word "Login" is in the response body
