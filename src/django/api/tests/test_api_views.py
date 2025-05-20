import pytest
from datetime import date, timedelta
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
    manager, logged_in_manager, store, store_associate_manager, employee
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
    logged_in_manager, store, store_associate_manager, employee
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
    logged_in_manager, store, store_associate_manager, employee
):
    """
    Test that a manager can update shift details for an associated store.
    """
    api_client = logged_in_manager
    login_time = localtime(now() - timedelta(hours=2))
    logout_time = localtime(now() - timedelta(hours=1))

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
    logged_in_manager, store, store_associate_manager, employee
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
def test_create_new_employee_success(logged_in_manager, store, store_associate_manager):
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
    logged_in_manager, store, store_associate_manager, employee
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


@pytest.mark.django_db
def test_employee_can_update_own_account(
    logged_in_employee, employee, store_associate_employee
):
    """
    Test that an employee can update their own basic account information (first name, last name, and phone number).
    This verifies that authenticated users can modify permitted fields and that changes persist in the database.
    """
    api_client = logged_in_employee

    payload = {
        "first_name": "UpdatedFirst",
        "last_name": "EmployeeLast",
        "phone": "+447123456789",
    }

    response = api_client.patch(
        reverse("api:modify_account_information"),
        data=payload,
        format="json",
    )

    assert response.status_code == 202
    assert response.json()["message"] == "Account information updated successfully."

    # Refresh and assert values persisted (assuming .title() is applied to names)
    employee.refresh_from_db()
    assert employee.first_name == "Updatedfirst"
    assert employee.last_name == "Employeelast"
    assert employee.phone_number == "+447123456789"


@pytest.mark.django_db
def test_employee_cannot_update_own_dob(
    logged_in_employee, employee, store_associate_employee
):
    """
    Test that an employee cannot update their own date of birth.
    The API should return a 403 error with an appropriate message.
    """
    api_client = logged_in_employee

    response = api_client.patch(
        reverse("api:modify_account_information"),
        data={"dob": "1990-01-01"},
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to modify your account date of birth."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_manager_can_update_employee_in_their_store(
    logged_in_manager, store_associate_manager, employee, store_associate_employee
):
    """
    Test that a manager can update an employee's information if the employee is in the same store.
    This includes changing name, phone number, and date of birth.
    The test ensures the values persist after the update.
    """
    api_client = logged_in_manager

    payload = {
        "first_name": "UpdatedByManager",
        "last_name": "ManagedLast",
        "phone": "+441234567890",
        "dob": "1990-05-05",
    }

    response = api_client.patch(
        reverse("api:modify_other_account_information", args=[employee.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 202
    assert response.json()["message"] == "Account information updated successfully."

    # Refresh and assert values persisted (assuming .title() is applied to names)
    employee.refresh_from_db()
    assert employee.first_name == "Updatedbymanager"
    assert employee.last_name == "Managedlast"
    assert employee.phone_number == "+441234567890"
    assert str(employee.birth_date) == "1990-05-05"


@pytest.mark.django_db
def test_password_change_success(logged_in_employee, employee):
    """
    Ensure an employee can successfully change their password when all inputs are valid.
    """
    api_client = logged_in_employee
    old_pass = "TestPass123"
    new_pass = "NewPass456"

    employee.set_password(old_pass)
    employee.save()

    response = api_client.put(
        reverse("api:modify_account_password"),
        data={"old_pass": old_pass, "new_pass": new_pass},
        format="json",
    )

    assert response.status_code == 202
    assert "message" in response.json()
    employee.refresh_from_db()
    assert employee.check_password(new_pass)


@pytest.mark.django_db
def test_password_change_invalid_old_password(logged_in_employee, employee):
    """
    Ensure the API returns an error when the old password provided is incorrect.
    """
    api_client = logged_in_employee
    employee.set_password("CorrectOld123")
    employee.is_setup = True
    employee.save()

    response = api_client.put(
        reverse("api:modify_account_password"),
        data={"old_pass": "WrongOld", "new_pass": "NewValid123"},
        format="json",
    )

    assert response.status_code == 403
    assert "Invalid old account password." in response.json()["Error"]


@pytest.mark.django_db
def test_password_change_invalid_new_password(logged_in_employee, employee):
    """
    Ensure the API returns an error when the new password does not meet complexity requirements.
    """
    api_client = logged_in_employee
    old_pass = "CorrectOld123"
    bad_new_pass = "short"

    employee.set_password(old_pass)
    employee.is_setup = True
    employee.save()

    response = api_client.put(
        reverse("api:modify_account_password"),
        data={"old_pass": old_pass, "new_pass": bad_new_pass},
        format="json",
    )

    assert response.status_code == 417
    assert "Invalid new account password." in response.json()["Error"]
    assert any(
        "Password must be at least" in e
        for e in response.json()["field_errors"]["new_pass"]
    )


@pytest.mark.django_db
def test_clocked_state_view_success(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test that an authenticated employee can successfully retrieve their clocked-in state
    for a store they are associated with, and with an active clock-in record present.
    """
    api_client = logged_in_clocked_in_employee

    url = reverse("api:clocked_state")
    response = api_client.get(f"{url}?store_id={store.id}")

    data = response.json()

    assert response.status_code == 200
    assert "clocked_in" in data
    assert data["clocked_in"] == True
    assert data["store_id"] == store.id
    assert data["employee_id"] == clocked_in_employee.id


@pytest.mark.django_db
def test_employee_list_associated_stores(
    logged_in_employee, employee, store, store_associate_employee
):
    """
    Test that a regular employee can retrieve a list of their active associated stores.
    """
    api_client = logged_in_employee

    url = reverse("api:list_associated_stores")
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()

    # The employee should see only active stores
    assert str(store.id) in data
    assert data[str(store.id)] == store.code


@pytest.mark.django_db
def test_list_recent_shifts_success(
    logged_in_clocked_in_employee, clocked_in_employee, store
):
    """
    Test that an authenticated employee can successfully fetch recent shifts
    for a store they are associated with.
    """
    # Use authenticated client
    api_client = logged_in_clocked_in_employee

    url = reverse("api:list_recent_shifts")
    response = api_client.get(url, {"store_id": str(store.id), "limit_days": 7})

    assert response.status_code == 200

    data = response.json()

    # The result should be a list of shift dictionaries
    assert isinstance(data, list)
    assert "login_time" in data[0]
    assert "logout_time" in data[0]
    assert "store_id" in data[0]
    assert "employee_id" in data[0]
    assert "store_code" in data[0]
    assert "deliveries" in data[0]
    assert "is_public_holiday" in data[0]
    assert "is_modified" in data[0]


@pytest.mark.django_db
def test_list_account_summaries_success(
    logged_in_manager, store, store_associate_manager, clocked_in_employee
):
    """
    Test that an associated manager can successfully retrieve account summaries for their store.
    DOES NOT TEST THE HOUR CALCULATIONS IS CORRECT.
    """
    api_client = logged_in_manager

    url = reverse("api:list_account_summaries")
    start = (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
    end = date.today().strftime("%Y-%m-%d")

    response = api_client.get(
        url,
        {
            "store_id": str(store.id),
            "start": start,
            "end": end,
            "sort": "name",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert data["total"] == 1

    emp = data["results"][0]
    assert emp["employee_id"] == clocked_in_employee.id


@pytest.mark.django_db
def test_list_account_summaries_full_hour_breakdown(
    logged_in_manager,
    store,
    store_associate_manager,
    employee,
    store_associate_employee,
):
    """
    Test that the account summaries accurately calculate weekday, weekend, and public holiday hours.
    """
    api_client = logged_in_manager
    today = now()

    # Setup reference times
    weekday = today - timedelta(days=(today.weekday() - 0) % 7)  # Last Monday
    weekend = today - timedelta(days=(today.weekday() - 5) % 7)  # Last Saturday
    holiday = today - timedelta(
        days=(today.weekday() - 4) % 7
    )  # Last Friday which will be counted as a "public holiday"

    activities = [
        # Weekday activity 3HRS
        Activity.objects.create(
            employee=employee,
            store=store,
            login_time=weekday.replace(hour=9, minute=0),
            logout_time=weekday.replace(hour=12, minute=0),
            login_timestamp=weekday.replace(hour=9, minute=0),
            logout_timestamp=weekday.replace(hour=12, minute=0),
            shift_length_mins=180,
            deliveries=2,
            is_public_holiday=False,
        ),
        # Weekend activity 3HRS
        Activity.objects.create(
            employee=employee,
            store=store,
            login_time=weekend.replace(hour=10, minute=0),
            logout_time=weekend.replace(hour=13, minute=0),
            login_timestamp=weekend.replace(hour=10, minute=0),
            logout_timestamp=weekend.replace(hour=13, minute=0),
            shift_length_mins=180,
            deliveries=1,
            is_public_holiday=False,
        ),
        # Public holiday weekday
        Activity.objects.create(
            employee=employee,
            store=store,
            login_time=holiday.replace(hour=8, minute=0),
            logout_time=holiday.replace(hour=10, minute=30),
            login_timestamp=holiday.replace(hour=8, minute=0),
            logout_timestamp=holiday.replace(hour=10, minute=30),
            shift_length_mins=150,
            deliveries=3,
            is_public_holiday=True,
        ),
    ]

    # Expected totals:
    # Weekday: 180 (normal) + 150 (public) = 330 mins → 5.5 hours
    # Weekend: 180 mins → 3.0 hours
    # Public holiday: 150 mins → 2.5 hours
    # Total: 180 + 180 + 150 = 510 mins → 8.5 hours
    # Deliveries: 2 + 1 + 3 = 6

    url = reverse("api:list_account_summaries")
    start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    end = today.strftime("%Y-%m-%d")

    response = api_client.get(
        url,
        {
            "store_id": str(store.id),
            "start": start,
            "end": end,
            "sort": "name",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["total"] == 1

    emp = data["results"][0]
    assert emp is not None

    assert emp["hours_total"] == 8.5
    assert emp["hours_weekday"] == 5.5
    assert emp["hours_weekend"] == 3.0
    assert emp["hours_public_holiday"] == 2.5
    assert emp["deliveries"] == 6
    assert emp["acc_resigned"] is False
    assert emp["acc_active"] is True
    assert emp["acc_manager"] is False
