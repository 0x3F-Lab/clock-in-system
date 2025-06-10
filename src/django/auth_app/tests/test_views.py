import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_home_view(client):
    """
    Test the login view of the Django application without authentication.
    """
    url = reverse("home")  # Resolve the URL for the login view
    response = client.get(url)  # Make a GET request using pytest's client

    # Check the response
    assert response.status_code == 200  # Ensure the response is HTTP 200 OK
    assert b"Home Directory" in response.content  # Check if "Login" is in the response


@pytest.mark.django_db
def test_employee_dashboard_success(logged_in_employee, employee):
    """
    Test that an authenticated employee can successfully access the employee dashboard view.
    """
    client = logged_in_employee

    url = reverse("dashboard")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    assert employee.first_name in content
    assert employee.last_name in content
    assert employee.email in content

    if employee.birth_date:
        dob_str = employee.birth_date.strftime("%d/%m/%Y")
        assert dob_str in content

    if employee.created_at:
        creation_str = employee.created_at.strftime("%d/%m/%Y")
        assert creation_str in content

    if employee.updated_at:
        updated_str = employee.updated_at.strftime("%d/%m/%Y")
        assert updated_str in content


@pytest.mark.django_db
def test_notification_page_success(logged_in_employee, employee, notification_all):
    """
    Test that an authenticated employee can successfully access the notification page.
    """
    client = logged_in_employee

    url = reverse("notification_page")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()

    assert "Your <u>Unread</u> Notifications" in content
    assert '<span id="notification-page-count">1</span>' in content

    # Assure the buttons exist
    assert "Notifications" in content
    assert "Read Notifications" in content
    assert "Sent Notifications" in content
    assert "Notification Settings" in content
    assert "Send Messages" in content


@pytest.mark.django_db
def test_manual_clocking_successful_clock_in(
    mocker, client, store, employee, store_associate_employee
):
    """
    Test a successful manual clock-in.
    """
    mocker.patch("api.utils.get_distance_from_lat_lon_in_m", return_value=10)

    url = reverse("manual_clocking")
    data = {
        "store_pin": store.store_pin,
        "employee_pin": employee.pin,
        "deliveries": 0,
        "latitude": store.location_latitude,
        "longitude": store.location_longitude,
    }

    assert employee.is_clocked_in(store=store) == False

    response = client.post(url, data)
    assert response.status_code == 202
    assert b"Successfully clocked in." in response.content

    employee.refresh_from_db()
    assert employee.is_clocked_in(store=store) == True


@pytest.mark.django_db
def test_manual_clocking_invalid_pin_combination(client, store):
    url = reverse("manual_clocking")
    data = {
        "store_pin": "invalid",
        "employee_pin": "wrong",
        "latitude": 0,
        "longitude": 0,
    }

    response = client.post(url, data)
    assert response.status_code == 401
    assert b"Invalid PIN combination." in response.content


@pytest.mark.django_db
def test_manual_clocking_user_not_associated(mocker, client, store, employee):
    mocker.patch("api.utils.get_distance_from_lat_lon_in_m", return_value=10)

    url = reverse("manual_clocking")
    data = {
        "store_pin": store.store_pin,
        "employee_pin": employee.pin,
        "latitude": store.location_latitude,
        "longitude": store.location_longitude,
    }

    response = client.post(url, data)
    assert b"Cannot clock in/out to a non-associated store." in response.content


@pytest.mark.django_db
def test_manual_clocking_out_of_range(
    mocker, client, store, employee, store_associate_employee
):
    mocker.patch("api.utils.get_distance_from_lat_lon_in_m", return_value=999)

    url = reverse("manual_clocking")
    data = {
        "store_pin": store.store_pin,
        "employee_pin": employee.pin,
        "latitude": 10.0,
        "longitude": 10.0,
    }

    response = client.post(url, data)
    assert b"too far from the store" in response.content


@pytest.mark.django_db
def test_manual_clocking_inactive_user(
    mocker, client, store, inactive_employee, store_associate_inactive_employee
):
    mocker.patch("api.utils.get_distance_from_lat_lon_in_m", return_value=10)

    url = reverse("manual_clocking")
    data = {
        "store_pin": store.store_pin,
        "employee_pin": inactive_employee.pin,
        "latitude": store.location_latitude,
        "longitude": store.location_longitude,
    }

    response = client.post(url, data)
    assert b"inactive account" in response.content


@pytest.mark.django_db
def test_manual_clocking_inactive_store(
    mocker, client, store, employee, store_associate_employee
):
    store.is_active = False
    store.save()

    mocker.patch("api.utils.get_distance_from_lat_lon_in_m", return_value=10)

    url = reverse("manual_clocking")
    data = {
        "store_pin": store.store_pin,
        "employee_pin": employee.pin,
        "latitude": store.location_latitude,
        "longitude": store.location_longitude,
    }

    response = client.post(url, data)
    assert b"inactive store" in response.content


@pytest.mark.django_db
def test_manager_dashboard_access(logged_in_manager):
    """
    Test that manager dashboard page is accessible to a logged-in manager.
    """
    client = logged_in_manager
    url = reverse("manager_dashboard")
    response = client.get(url)

    assert response.status_code == 200
    assert "auth_app/manager_dashboard.html" in [t.name for t in response.templates]
    assert b"Manager Dashboard" in response.content


@pytest.mark.django_db
def test_manage_employee_details_access(logged_in_manager):
    """
    Test that employee details management page is accessible to a logged-in manager.
    """
    client = logged_in_manager
    url = reverse("manage_employee_details")
    response = client.get(url)

    assert response.status_code == 200
    assert "auth_app/manage_employee_details.html" in [
        t.name for t in response.templates
    ]
    assert b"Employee Details" in response.content


@pytest.mark.django_db
def test_manage_shift_logs_access(logged_in_manager):
    """
    Test that shift logs management page is accessible to a logged-in manager.
    """
    client = logged_in_manager
    url = reverse("manage_shift_logs")
    response = client.get(url)

    assert response.status_code == 200
    assert "auth_app/shift_logs.html" in [t.name for t in response.templates]
    assert b"Shift Logs" in response.content


@pytest.mark.django_db
def test_manage_stores_access(logged_in_manager, store, store_associate_manager):
    """
    Test that store management page is accessible to a logged-in manager.
    """
    client = logged_in_manager
    url = reverse("manage_stores")
    response = client.get(url)

    assert response.status_code == 200
    assert "auth_app/manage_stores.html" in [t.name for t in response.templates]
    assert b"Store Information" in response.content
    assert (
        b'<p><span class="fw-semibold">Name:</span> Test Store</p>' in response.content
    )
    assert (
        b'<p><span class="fw-semibold">Allowable Clocking Distance:</span> 500 meters</p>'
        in response.content
    )
    assert (
        b'<p><span class="fw-semibold">Store Latitude:</span> 1.0</p>'
        in response.content
    )


@pytest.mark.django_db
def test_manage_account_summary_access(logged_in_manager):
    """
    Test that account summary page is accessible to a logged-in manager.
    """
    client = logged_in_manager
    url = reverse("account_summary")
    response = client.get(url)

    assert response.status_code == 200
    assert "auth_app/account_summary.html" in [t.name for t in response.templates]
    assert b"Account Summary" in response.content


@pytest.mark.django_db
def test_offline_page_access(client):
    """
    Test that the offline page is accessible without login.
    """
    url = reverse("offline")
    response = client.get(url)
    assert response.status_code == 200
    assert "offline.html" in [t.name for t in response.templates]
    assert b"OFFLINE" in response.content
    assert b"Please check your internet connection." in response.content
    assert b"RETRY" in response.content
