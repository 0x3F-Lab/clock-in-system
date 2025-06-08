import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_non_manager_redirects_back_to_referer(logged_in_employee):
    """
    Ensure that a non-manager user attempting to access a manager-only page
    is redirected back to the referring page (if provided).
    """
    referer_url = reverse("manual_clocking")
    response = logged_in_employee.get(
        reverse("manager_dashboard"),
        HTTP_REFERER=referer_url,
    )

    # Check that the response is a redirect
    assert response.status_code == 302

    # Ensure it redirects back to the referer (not home)
    assert response.url == referer_url


@pytest.mark.django_db
def test_employee_cannot_access_manager_dashboard(logged_in_employee):
    """
    Ensure that a non-manager user is redirected to the home page when
    attempting to access the manager dashboard.
    """
    response = logged_in_employee.get(reverse("manager_dashboard"))

    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_employee_cannot_access_manage_employee_details(logged_in_employee):
    """
    Ensure that a non-manager user is redirected to the home page when
    attempting to access the manage employee details page.
    """
    response = logged_in_employee.get(reverse("manage_employee_details"))

    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_employee_cannot_access_manage_shift_logs(logged_in_employee):
    """
    Ensure that a non-manager user is redirected to the home page when
    attempting to access the shift logs management page.
    """
    response = logged_in_employee.get(reverse("manage_shift_logs"))

    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_employee_cannot_access_manage_account_summary(logged_in_employee):
    """
    Ensure that a non-manager user is redirected to the home page when
    attempting to access the account summary page.
    """
    response = logged_in_employee.get(reverse("account_summary"))

    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.django_db
def test_employee_cannot_access_manage_stores_page(logged_in_employee):
    """
    Ensure that a non-manager user is redirected to the home page when
    attempting to access the manage stores page.
    """
    response = logged_in_employee.get(reverse("manage_stores"))

    assert response.status_code == 302
    assert response.url == reverse("home")
