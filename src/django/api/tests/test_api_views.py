import pytest
from django.urls import reverse
from django.utils.timezone import timedelta, now, localtime
from auth_app.models import Activity


@pytest.mark.django_db
def test_list_store_employee_names_success(
    logged_in_manager,
    manager,
    store,
    store_associate_employee,
    store_associate_manager,
    inactive_employee,
    employee,
):
    """
    Test successful retrieval of employee names for a store by an associated manager.
    """
    api_client = logged_in_manager
    url = reverse("api:list_store_employee_names")  # Ensure your URL name matches this

    response = api_client.get(
        url,
        {
            "store_id": store.id,
            "only_active": "false",
            "ignore_managers": "true",
            "order": "true",
            "order_by_first_name": "true",
            "ignore_clocked_in": "false",
        },
    )

    assert response.status_code == 200
    data = {int(k): v for k, v in response.json().items()}

    # The result should be a dict mapping user IDs to full names
    assert isinstance(data, dict)
    assert employee.id in data
    assert data[employee.id] == f"{employee.first_name} {employee.last_name}"
    assert manager.id not in data  # Because ignore_managers=True
    assert inactive_employee.id not in data


@pytest.mark.django_db
def test_list_all_shift_details_success(
    api_client, manager, logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that shift details are returned correctly for a store the user is associated with.
    """
    api_client = logged_in_manager

    # Create a shift (Activity) for employee
    login_time = now() - timedelta(hours=3)
    logout_time = now()

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=login_time,
        logout_time=logout_time,
        login_timestamp=login_time,
        logout_timestamp=logout_time,
        shift_length_mins=180,
        deliveries=4,
        is_public_holiday=False,
    )

    url = reverse("api:list_all_shift_details")
    response = api_client.get(
        url,
        {
            "store_id": store.id,
            "offset": 0,
            "limit": 10,
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 1
    assert data["offset"] == 0
    assert data["limit"] == 10
    assert len(data["results"]) == 1

    shift = data["results"][0]
    assert shift["id"] == activity.id
    assert shift["employee_first_name"] == employee.first_name
    assert shift["employee_last_name"] == employee.last_name
    assert shift["deliveries"] == 4
    assert shift["hours_worked"] == "3.00"


@pytest.mark.django_db
def test_list_singular_shift_details_success(
    api_client, logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that a manager can retrieve shift details for a store they are associated with.
    """
    api_client = logged_in_manager

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=now() - timedelta(hours=2),
        login_timestamp=now() - timedelta(hours=2),
        logout_time=now(),
        logout_timestamp=now(),
        is_public_holiday=False,
        deliveries=2,
    )

    url = reverse("api:list_singular_shift_details", args=[activity.id])
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == activity.id
    assert data["is_public_holiday"] is False
    assert data["deliveries"] == 2
    assert data["login_timestamp"] is not None
    assert data["logout_timestamp"] is not None


@pytest.mark.django_db
def test_update_shift_details_success(
    api_client, logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that a manager can update shift details for an associated store.
    """
    api_client = logged_in_manager
    login_time = localtime(now() - timedelta(hours=2))
    logout_time = localtime(now() - timedelta(hours=1))
    print(logout_time)

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_timestamp=login_time,
        logout_timestamp=logout_time,
        login_time=login_time,
        logout_time=logout_time,
        deliveries=3,
        is_public_holiday=False,
    )

    new_logout_time = localtime(now() - timedelta(minutes=30)).replace(
        second=0, microsecond=0
    )
    print(new_logout_time)
    response = api_client.patch(
        reverse("api:update_shift_details", args=[activity.id]),
        data={
            "login_timestamp": login_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "logout_timestamp": new_logout_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "deliveries": 4,
            "is_public_holiday": True,
        },
        format="json",
    )

    assert response.status_code == 202
    activity.refresh_from_db()
    assert activity.deliveries == 4
    assert activity.is_public_holiday is True
    assert (
        localtime(activity.logout_timestamp).isoformat() == new_logout_time.isoformat()
    )


@pytest.mark.django_db
def test_delete_shift_details_success(
    api_client, logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that a manager can delete a shift for an associated store.
    """
    api_client = logged_in_manager

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_timestamp=now() - timedelta(hours=2),
        login_time=now() - timedelta(hours=2),
        logout_time=now(),
        logout_timestamp=now(),
    )

    response = api_client.delete(
        reverse("api:update_shift_details", args=[activity.id])
    )
    assert response.status_code == 200
    assert not Activity.objects.filter(id=activity.id).exists()


@pytest.mark.django_db
def test_create_new_shift_success(
    api_client,
    manager,
    logged_in_manager,
    store_associate_manager,
    store,
    employee,
    store_associate_employee,
):
    login_time = (now() - timedelta(hours=2)).replace(second=0, microsecond=0)
    logout_time = (now() - timedelta(hours=1)).replace(second=0, microsecond=0)

    response = logged_in_manager.put(
        reverse("api:create_new_shift"),
        data={
            "employee_id": str(employee.id),
            "store_id": store.id,
            "login_timestamp": login_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "logout_timestamp": logout_time.strftime("%Y-%m-%dT%H:%M:%S"),
            "deliveries": 5,
            "is_public_holiday": True,
        },
        format="json",
    )

    assert response.status_code == 201
    response_data = response.json()
    activity = Activity.objects.get(id=response_data["id"])
    assert activity.employee == employee
    assert activity.store == store
    assert activity.deliveries == 5
    assert activity.is_public_holiday is True


@pytest.mark.django_db
def test_create_new_shift_missing_fields(
    api_client,
    logged_in_manager,
    manager,
    store_associate_manager,
    store,
    employee,
    store_associate_employee,
):
    response = logged_in_manager.put(
        reverse("api:create_new_shift"),
        data={
            "store_id": store.id,
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            # Missing employee_id and login_timestamp
        },
        format="json",
    )

    assert response.status_code == 417
    assert "Required fields are missing" in response.json()["Error"]


@pytest.mark.django_db
def test_list_all_employee_details_success(
    api_client,
    logged_in_manager,
    store,
    store_associate_manager,
    store_associate_employee,
    employee,
):
    """
    Test that a manager can successfully retrieve employee details for an associated store.
    """
    api_client = logged_in_manager

    response = api_client.get(
        reverse("api:list_all_employee_details"),
        data={"store_id": store.id},
        format="json",
    )

    assert response.status_code == 200
    assert "results" in response.json()
    assert any(emp["id"] == employee.id for emp in response.json()["results"])


@pytest.mark.django_db
def test_list_singular_employee_details_success(
    api_client,
    logged_in_manager,
    store,
    store_associate_manager,
    store_associate_employee,
    employee,
):
    """
    Test that a manager can successfully retrieve details of an employee associated with their store.
    """
    api_client = logged_in_manager

    response = api_client.get(
        reverse("api:list_singular_employee_details", args=[employee.id]),
        format="json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == employee.id
    assert data["first_name"] == employee.first_name
    assert data["last_name"] == employee.last_name


@pytest.mark.django_db
def test_create_new_employee_success(
    api_client, logged_in_manager, store, store_associate_manager
):
    """
    Test that a manager can successfully create a new employee and associate them to their store.
    """
    api_client = logged_in_manager

    response = api_client.put(
        reverse("api:create_new_employee"),
        data={
            "first_name": "Alice",
            "last_name": "Johnson",
            "email": "alice@example.com",
            "phone": "+1234567890",
            "dob": "1990-01-01",
            "store_id": str(store.id),
        },
        format="json",
    )

    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["message"].startswith("New employee created successfully")


@pytest.mark.django_db
def test_create_new_employee_assign_existing(
    api_client, logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that a manager can assign an existing employee to their store if not already associated.
    """
    api_client = logged_in_manager

    # Ensure the employee is not already associated with the store
    assert not employee.is_associated_with_store(store)

    response = api_client.put(
        reverse("api:create_new_employee"),
        data={
            "email": employee.email,
            "store_id": str(store.id),
        },
        format="json",
    )

    assert response.status_code == 202
    data = response.json()
    assert data["message"].startswith("Existing employee assigned to store")
    assert data["id"] == employee.id
