from unittest import mock
from django.test import TestCase
from django.urls import reverse


class LoginPageTest(TestCase):

    @mock.patch("django.contrib.auth.models.User.objects.get")  # Mock DB call
    def test_login_page_accessible(self, mock_get_user):
        # Define a mock return value when objects.get() is called
        mock_get_user.return_value = mock.MagicMock(id=1, username="testuser")

        # Simulate a GET request to the login page
        response = self.client.get(reverse("login"))

        # Assert that the login page is accessible
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Login")
