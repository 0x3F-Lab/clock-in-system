import pytest
from datetime import date
from django.urls import reverse
from django.contrib.messages import get_messages
from django.contrib.auth.hashers import check_password


@pytest.mark.django_db
def test_login_get(web_client):
    """
    Test GET request to login page returns 200 and uses correct template.
    """
    url = reverse("login")
    response = web_client.get(url)

    assert response.status_code == 200
    assert b"Employee Login" in response.content
    assert b"Setup Account" in response.content


@pytest.mark.django_db
def test_login_success_redirects_to_home(web_client, employee):
    """
    Test successful login via POST redirects to 'home'.
    """
    url = reverse("login")
    response = web_client.post(
        url, {"email": employee.email, "password": "testpassword"}, follow=True
    )

    assert response.status_code == 200
    assert web_client.session["user_id"] == employee.id
    assert response.redirect_chain[-1][0].endswith(reverse("home"))


@pytest.mark.django_db
def test_login_invalid_credentials_shows_error(web_client, employee):
    """
    Test login with incorrect password shows error and re-renders form.
    """
    url = reverse("login")
    response = web_client.post(
        url, {"email": employee.email, "password": "wrongpassword"}
    )

    assert response.status_code == 403
    assert b"Invalid Credentials" in response.content
    assert "auth_app/login.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_login_redirects_to_next_url(web_client, employee):
    """
    Test that login with a valid `next` parameter redirects correctly.
    """
    next_url = reverse("dashboard")
    login_url = reverse("login")
    response = web_client.post(
        f"{login_url}?next={next_url}",
        {"email": employee.email, "password": "testpassword"},
        follow=True,
    )

    assert response.status_code == 200
    assert next_url in response.redirect_chain[-1][0]


@pytest.mark.django_db
def test_login_redirects_if_already_logged_in(logged_in_employee, employee):
    """
    If a user is already logged in, accessing the login page should redirect to home.
    """
    # Log in
    web_client = logged_in_employee

    response = web_client.get(reverse("login"))
    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_login_inactive_user(web_client, inactive_employee):
    """
    Ensure that an inactive user cannot log in and sees an appropriate error message.
    """
    url = reverse("login")
    data = {
        "email": inactive_employee.email,
        "password": "testpassword",
    }

    response = web_client.post(url, data)

    assert response.status_code == 409
    assert b"Cannot log into a deactivated account" in response.content

    messages = list(get_messages(response.wsgi_request))
    assert any("deactivated account" in str(m) for m in messages)
    assert "user_id" not in web_client.session


@pytest.mark.django_db
def test_logout_clears_session_and_redirects(logged_in_employee, employee):
    """
    Test that logout flushes the session and redirects to 'home'.
    """
    # Log in
    web_client = logged_in_employee

    assert "user_id" in web_client.session

    response = web_client.get(reverse("logout"), follow=True)

    # Check session was flushed
    assert "user_id" not in web_client.session

    # Check redirection
    assert response.redirect_chain[-1][0].endswith(reverse("home"))
    assert response.status_code == 200

    # Optional: Check that logout message appears
    assert b"Successfully logged out" in response.content


@pytest.mark.django_db
def test_account_setup_success(web_client, unsetup_employee):
    """
    Test that a valid POST to setup_account sets up the account and logs the user in.
    """
    url = reverse("account_setup")

    data = {
        "email": unsetup_employee.email,
        "password": "NewSecurePass123",
        "retype_password": "NewSecurePass123",
        "first_name": "UpdatedFirst",
        "last_name": "UpdatedLast",
        "phone_number": "0400000000",
        "birth_date": date(1995, 5, 5),
    }

    response = web_client.post(url, data, follow=True)

    # Reload user from DB
    unsetup_employee.refresh_from_db()

    # User data should now be updated
    assert (
        unsetup_employee.first_name == "Updatedfirst"
    )  # .title() is applied on DB end.
    assert unsetup_employee.last_name == "Updatedlast"
    assert unsetup_employee.phone_number == "0400000000"
    assert unsetup_employee.birth_date == date(1995, 5, 5)
    assert unsetup_employee.is_setup is True
    assert check_password("NewSecurePass123", unsetup_employee.password)

    # Should be redirected to home
    assert response.redirect_chain[-1][0].endswith(reverse("home"))
    assert response.status_code == 200

    # Session should be initialized
    session = web_client.session
    assert session["user_id"] == unsetup_employee.id
    assert session["name"] == "Updatedfirst"  # .title() is applied on DB end.
