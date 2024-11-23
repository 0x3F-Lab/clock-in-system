from django.test import TestCase
from django.urls import reverse


class TestLoginView(TestCase):
    def test_login_view(self):
        """
        Test the login view of the Django application.
        """
        url = reverse("login")  # Resolve the URL for the login view
        response = self.client.get(url)  # Make a GET request using TestCase's client

        # Check the response
        self.assertEqual(
            response.status_code, 200
        )  # Ensure the response is HTTP 200 OK
        self.assertIn(b"Login", response.content)  # Check if "Login" is in the response
