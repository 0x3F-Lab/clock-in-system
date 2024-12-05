import pytest
from django.urls import reverse
from auth_app.models import Activity


@pytest.mark.django_db
def test_clock_in_success(api_client, employee):
    """
    Test successful clock-in for an employee.
    """
    url = reverse("clock_in", args=[employee.id])
    response = api_client.post(url)

    assert response.status_code == 201  # HTTP 201 Created
    data = response.json()
    assert data["employee_id"] == employee.id
    assert Activity.objects.filter(
        employee_id=employee, logout_time__isnull=True
    ).exists()


@pytest.mark.django_db
def test_clock_in_already_clocked_in(api_client, clocked_in_employee):
    """
    Test attempting to clock in an employee who is already clocked in.
    """
    url = reverse("clock_in", args=[clocked_in_employee.id])
    response = api_client.post(url)

    assert response.status_code == 400  # HTTP 400 Bad Request
    data = response.json()
    assert "Error" in data
    assert data["Error"] == "Employee is already clocked in."


@pytest.mark.django_db
def test_clock_out_success(api_client, clocked_in_employee):
    """
    Test successful clock-out for an employee.
    """
    url = reverse("clock_out", args=[clocked_in_employee.id])
    response = api_client.post(url, {"deliveries": 5})

    assert response.status_code == 200  # HTTP 200 OK
    data = response.json()
    assert data["employee_id"] == clocked_in_employee.id
    assert data["deliveries"] == 5
    assert Activity.objects.filter(
        employee_id=clocked_in_employee, logout_time__isnull=False
    ).exists()


@pytest.mark.django_db
def test_clock_out_not_clocked_in(api_client, employee):
    """
    Test attempting to clock out an employee who is not clocked in.
    """
    url = reverse("clock_out", args=[employee.id])
    response = api_client.post(url, {"deliveries": 5})

    assert response.status_code == 400  # HTTP 400 Bad Request
    data = response.json()
    assert "Error" in data
    assert data["Error"] == "Employee is not clocked in."


@pytest.mark.django_db
def test_invalid_employee_id(api_client):
    """
    Test using an invalid employee ID for clock in/out.
    """
    url = reverse("clock_in", args=[999])  # Nonexistent employee ID
    response = api_client.post(url)

    assert response.status_code == 404  # HTTP 404 Not Found
    data = response.json()
    assert "Error" in data
    assert data["Error"] == "Employee not found with the ID 999."
