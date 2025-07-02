import pytest
from django.urls import reverse
from auth_app.models import Activity


@pytest.mark.django_db
def test_clock_in_success(
    logged_in_employee, employee, store, store_associate_employee
):
    """
    Test successful clock-in.
    """
    # Log in the user
    api_client = logged_in_employee

    url = reverse("api:clock_in")
    payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
    }
    response = api_client.post(url, payload)
    assert response.status_code == 201

    # Basic field validation
    data = response.json()
    assert data["employee_id"] == employee.id
    assert data["store_id"] == store.id
    assert "login_time" in data
    assert "login_timestamp" in data
    assert "is_public_holiday" in data

    assert Activity.objects.filter(
        employee_id=employee, logout_time__isnull=True
    ).exists()


@pytest.mark.django_db
def test_clock_in_missing_store_id(logged_in_employee, employee, store):
    """
    Test clock-in endpoint with a missing store_id.
    """
    # Log in the user
    api_client = logged_in_employee

    url = reverse("api:clock_in")
    payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        # store_id missing
    }

    response = api_client.post(url, payload)

    assert response.status_code == 400
    assert "Error" in response.json()
    assert "store_id" in response.json().get("Error")


@pytest.mark.django_db
def test_clock_in_unassociated_store(logged_in_employee, employee, store):
    """
    Test clock-in endpoint with a user not related to the store.
    """
    # Log in the user
    api_client = logged_in_employee

    url = reverse("api:clock_in")
    payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
    }
    response = api_client.post(url, payload)
    assert response.status_code == 403

    assert "Error" in response.json()


@pytest.mark.django_db
def test_clock_in_already_clocked_in(
    logged_in_employee, employee, store, store_associate_employee
):
    """
    Test attempting to clock in an employee who is already clocked in.
    """
    api_client = logged_in_employee
    url = reverse("api:clock_in")
    payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
    }

    # First clock-in
    response = api_client.post(url, payload)
    assert response.status_code == 201

    # Attempt to clock in again
    response = api_client.post(url, payload)
    assert response.status_code == 400
    data = response.json()
    assert "Error" in data
    assert data["Error"] == "Employee is already clocked in."


@pytest.mark.django_db
def test_clock_out_success_within_range(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test successful clock-out for an employee within the allowable distance.
    """
    api_client = logged_in_clocked_in_employee
    clock_out_url = reverse("api:clock_out")

    # Clock out
    clock_out_payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "deliveries": 5,
        "store_id": store.id,
    }
    clock_out_resp = api_client.post(clock_out_url, clock_out_payload)

    assert clock_out_resp.status_code == 200
    data = clock_out_resp.json()
    assert data["employee_id"] == clocked_in_employee.id
    assert data["deliveries"] == 5
    assert Activity.objects.filter(
        employee_id=clocked_in_employee, logout_time__isnull=False
    ).exists()


@pytest.mark.django_db
def test_clock_out_not_clocked_in(
    logged_in_employee, employee, store, store_associate_employee
):
    """
    Test attempting to clock out without a prior clock-in.
    """
    api_client = logged_in_employee
    url = reverse("api:clock_out")
    payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
        "deliveries": 0,
    }
    response = api_client.post(url, payload)

    assert response.status_code == 400
    assert response.json()["Error"] == "Employee is not clocked in."


@pytest.mark.django_db
def test_clock_in_out_of_range(logged_in_employee, store, store_associate_employee):
    """
    Test clock-in attempt out of store range.
    """
    api_client = logged_in_employee
    url = reverse("api:clock_in")
    payload = {
        "location_latitude": 100.0,  # Far away
        "location_longitude": 100.0,
        "store_id": store.id,
    }
    response = api_client.post(url, payload)

    assert response.status_code == 412
    assert (
        response.json()["Error"]
        == "Cannot clock in too far from the store's allowed range."
    )


@pytest.mark.django_db
def test_clock_out_out_of_range(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test clock-out attempt out of store range.
    """
    api_client = logged_in_clocked_in_employee
    clock_out_url = reverse("api:clock_out")

    # Try clocking out far away
    clock_out_payload = {
        "location_latitude": 10000.0,
        "location_longitude": 100000.0,
        "store_id": store.id,
        "deliveries": 5,
    }
    clock_out_resp = api_client.post(clock_out_url, clock_out_payload)

    assert clock_out_resp.status_code == 412
    assert (
        clock_out_resp.json()["Error"]
        == "Cannot clock out too far from the store's allowed range."
    )


@pytest.mark.django_db
def test_clock_in_missing_location_data(logged_in_employee, store):
    """
    Test clock-in attempt missing required location fields.
    """
    api_client = logged_in_employee
    url = reverse("api:clock_in")
    response = api_client.post(url, {"store_id": store.id})

    assert response.status_code == 400
    assert response.json()["Error"] == "Missing location data in request."


@pytest.mark.django_db
def test_clock_out_missing_location_data(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test clock-out attempt missing location fields.
    """
    api_client = logged_in_clocked_in_employee

    # Now clock out without location
    clock_out_url = reverse("api:clock_out")
    response = api_client.post(clock_out_url, {"store_id": store.id, "deliveries": 3})

    assert response.status_code == 400
    assert response.json()["Error"] == "Missing location data in request."


@pytest.mark.django_db
def test_clock_out_too_soon_after_clock_in(
    logged_in_employee, store, store_associate_employee
):
    """
    Test that an employee cannot clock out immediately after clocking in.
    """
    api_client = logged_in_employee
    clock_in_url = reverse("api:clock_in")
    clock_out_url = reverse("api:clock_out")

    # Clock in properly
    clock_in_payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
    }
    clock_in_response = api_client.post(clock_in_url, clock_in_payload)
    assert clock_in_response.status_code == 201

    # Immediately clock out
    clock_out_payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
        "deliveries": 2,
    }
    clock_out_response = api_client.post(clock_out_url, clock_out_payload)

    assert clock_out_response.status_code == 409
    assert (
        clock_out_response.json()["Error"]
        == "Can't clock out too soon after clocking in."
    )


@pytest.mark.django_db
def test_clock_in_too_soon_after_clock_out(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test that an employee cannot clock in immediately after clocking out.
    """
    api_client = logged_in_clocked_in_employee
    clock_in_url = reverse("api:clock_in")
    clock_out_url = reverse("api:clock_out")

    clock_out_payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
        "deliveries": 2,
    }
    clock_out_response = api_client.post(clock_out_url, clock_out_payload)
    assert clock_out_response.status_code == 200

    # Immediately clock in
    clock_in_payload = {
        "location_latitude": store.location_latitude,
        "location_longitude": store.location_longitude,
        "store_id": store.id,
    }
    clock_in_response = api_client.post(clock_in_url, clock_in_payload)

    assert clock_in_response.status_code == 409
    assert (
        clock_in_response.json()["Error"]
        == "Can't start a shift too soon after your last shift."
    )
