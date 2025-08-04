import pytest
from unittest.mock import patch
from freezegun import freeze_time
from datetime import date, timedelta, time
from django.urls import reverse
from django.utils.timezone import timedelta, now, localtime
from rest_framework import status
from auth_app.models import (
    Shift,
    Role,
    Store,
    User,
    ShiftException,
    Activity,
    StoreUserAccess,
)


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

    names_data = response.json().get("names", [])
    assert isinstance(names_data, list)

    # Extract IDs from the returned list
    returned_ids = {entry["id"] for entry in names_data}
    returned_map = {entry["id"]: entry["name"] for entry in names_data}

    # Should contain active non-manager employee
    assert employee.id in returned_ids
    assert returned_map[employee.id] == f"{employee.first_name} {employee.last_name}"

    # Should not contain manager (ignore_managers=True)
    assert manager.id not in returned_ids

    # Should not contain inactive employee
    assert inactive_employee.id not in returned_ids


@freeze_time("2025-01-01 15:00:00")
@pytest.mark.django_db
def test_list_all_shift_details_success(
    manager,
    logged_in_manager,
    store,
    store_associate_manager,
    employee,
    store_associate_employee,
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
            "start": login_time.date(),
            "end": logout_time.date(),
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
    assert shift["emp_first_name"] == employee.first_name
    assert shift["emp_last_name"] == employee.last_name
    assert shift["emp_active"] == True
    assert shift["emp_resigned"] == False
    assert shift["deliveries"] == 4
    assert shift["hours_worked"] == "3.00"


@freeze_time("2025-01-01 15:00:00")
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


@freeze_time("2025-01-01 15:00:00")
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


@freeze_time("2025-01-01 15:00:00")
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


@freeze_time("2025-01-01 15:00:00")
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


@freeze_time("2025-01-01 15:00:00")
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
@patch("auth_app.tasks.notify_managers_and_employee_account_assigned.delay")
def test_create_new_employee_success(
    mock_delay, logged_in_manager, store, store_associate_manager
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
    mock_delay.assert_called_once()


@pytest.mark.django_db
@patch("auth_app.tasks.notify_managers_and_employee_account_assigned.delay")
def test_create_new_employee_assign_existing(
    mock_delay, logged_in_manager, store, store_associate_manager, employee
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
    mock_delay.assert_called_once()


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
        "Not authorised to modify your own account date of birth."
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

    url = reverse("api:list_user_activities")
    response = api_client.get(url, {"store_id": str(store.id), "week": now().date()})

    assert response.status_code == 200

    data = response.json()
    assert "activities" in data
    assert localtime(now()).date().isoformat() in data["activities"]

    act = data["activities"][localtime(now()).date().isoformat()][0]
    assert "login_time_str" in act
    assert "logout_time_str" in act
    assert "store_id" in act
    assert "employee_id" in act
    assert "store_code" in act
    assert "deliveries" in act
    assert "is_public_holiday" in act
    assert "is_modified" in act


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
    assert data["total"] == 2  # INCLUDES MANAGER

    emp = data["results"][0]
    assert emp["employee_id"] == clocked_in_employee.id


@freeze_time("2025-01-01 15:00:00")
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
    # Weekday: 180 (normal) → 5.5 hours
    # Weekend: 180 mins → 3.0 hours
    # Public holiday: 150 mins → 2.5 hours (MUTUALLY EXCLUSIVE)
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
            "ignore_no_hours": "true",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert data["total"] == 1

    emp = data["results"][0]
    assert emp is not None

    assert emp["hours_total"] == 8.5
    assert emp["hours_weekday"] == 3.0
    assert emp["hours_weekend"] == 3.0
    assert emp["hours_public_holiday"] == 2.5
    assert emp["deliveries"] == 6
    assert emp["acc_resigned"] is False
    assert emp["acc_active"] is True
    assert emp["acc_store_manager"] is False


@pytest.mark.django_db
@patch("auth_app.tasks.notify_managers_store_information_updated.delay")
def test_update_store_info(
    mock_notify, logged_in_manager, manager, store, store_associate_manager
):
    """
    Test that a manager can update an associated store's info.
    """
    # Ensure store has default info
    assert store.name == "Test Store"
    assert store.code == "TST001"
    assert store.location_street == "123 Main St"
    assert store.allowable_clocking_dist_m == 500

    # Change the store's info
    api_client = logged_in_manager
    url = reverse("api:update_store_info", args=[store.id])
    send_data = {
        "name": "edit name",
        "loc_street": "edit street",
        "code": "NEWCODE",
        "clocking_dist": 450,
    }
    response = api_client.patch(url, data=send_data)

    assert response.status_code == 202
    data = response.json()

    # Ensure store object is updated
    store.refresh_from_db()
    assert store.name == send_data["name"]
    assert store.code == send_data["code"]
    assert store.location_street == send_data["loc_street"]
    assert store.allowable_clocking_dist_m == send_data["clocking_dist"]


# Helper to get the start of the current week (Monday)
def get_monday_of_week(dt=None):
    if dt is None:
        dt = now().date()
    return dt - timedelta(days=dt.weekday())


# Mark all tests in this class to use the database
@pytest.mark.django_db
class TestScheduleAndRoleAPIs:
    """
    Test suite for API views related to schedule and role management.
    """

    # --- Fixture for test-specific setup ---
    @pytest.fixture(autouse=True)
    def setup_class(
        self,
        db,
        store,
        manager,
        employee,
        clocked_in_employee,
        store_associate_manager,
        store_associate_employee,
    ):
        """
        Creates a common setup for all tests in this class, including roles, shifts, and exceptions.
        This fixture runs automatically for every test in this class.
        """
        self.manager = manager
        self.employee = employee
        self.store = store
        self.week_start = get_monday_of_week()

        # Create roles for the store
        self.cook_role = Role.objects.create(
            store=self.store, name="Cook", colour_hex="#3498db"
        )
        self.cashier_role = Role.objects.create(
            store=self.store, name="Cashier", colour_hex="#e74c3c"
        )

        # Create shifts for testing
        self.shift1 = Shift.objects.create(
            store=self.store,
            employee=self.employee,
            role=self.cook_role,
            date=self.week_start,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        # Create a shift exception for testing
        self.activity = Activity.objects.create(
            employee=self.employee,
            store=self.store,
            login_time=now() - timedelta(hours=1),
            logout_time=now(),
        )
        self.exception = ShiftException.objects.create(
            activity=self.activity, reason=ShiftException.Reason.INCORRECTLY_CLOCKED
        )

    # ===============================================
    # == Tests for list_store_shifts
    # ===============================================
    def test_list_store_shifts_legacy_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager
        WHEN they request shifts for a specific week
        THEN they should receive a 200 OK and a schedule object.
        """

        url = (
            reverse("api:list_store_shifts", kwargs={"id": self.store.id})
            + f"?get_all=true&legacy=true&week={self.week_start.isoformat()}"
        )
        response = api_client.get(url)
        data = response.json()  # Parse the JSON response
        assert response.status_code == status.HTTP_200_OK
        assert "schedule" in data
        assert str(self.week_start) in data["schedule"]

    def test_list_store_shifts_unauthorized(self, api_client):
        """
        GIVEN an unauthenticated user
        WHEN they request shifts
        THEN they should receive a 401 Unauthorized error.
        """

        url = reverse("api:list_store_shifts", kwargs={"id": self.store.id})
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ===============================================
    # == Tests for create_store_shift
    # ===============================================
    def test_create_shift_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager
        WHEN they send valid data for a new shift
        THEN a new shift should be created and a 201 status returned.
        """
        url = reverse("api:create_shift", kwargs={"store_id": self.store.id})
        shift_count_before = Shift.objects.count()

        future_date = (now() + timedelta(days=9)).date()

        data = {
            "employee_id": self.employee.id,
            "role_id": self.cook_role.id,
            "date": future_date.isoformat(),
            "start_time": "10:00",
            "end_time": "18:00",
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Shift.objects.count() == shift_count_before + 1

    def test_create_shift_in_past_fails(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager
        WHEN they attempt to create a shift in the past
        THEN the request should fail with a 412 error.
        """
        url = reverse("api:create_shift", kwargs={"store_id": self.store.id})
        data = {
            "employee_id": self.employee.id,
            "date": (self.week_start - timedelta(days=10)).isoformat(),  # A past date
            "start_time": "10:00",
            "end_time": "18:00",
        }
        response = api_client.put(url, data, format="json")
        assert response.status_code == status.HTTP_412_PRECONDITION_FAILED

    # ===============================================
    # == Tests for manage_store_shift (Update/Delete)
    # ===============================================
    def test_update_shift_role(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager and an existing shift
        WHEN they change the role of the shift
        THEN the shift's role should be updated in the database.
        """

        future_shift = Shift.objects.create(
            store=self.store,
            employee=self.employee,
            role=self.cook_role,
            date=(now() + timedelta(days=10)).date(),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        url = reverse("api:manage_shift", kwargs={"id": future_shift.id})
        data = {
            "employee_id": future_shift.employee.id,
            "role_id": self.cashier_role.id,  # Change from Cook to Cashier
            "date": future_shift.date.isoformat(),
            "start_time": "09:30",  # Change start time
            "end_time": "17:30",
        }
        response = api_client.post(
            url, data, format="json"
        )  # Your view uses POST for updates
        assert response.status_code == status.HTTP_202_ACCEPTED
        future_shift.refresh_from_db()
        assert future_shift.role == self.cashier_role
        assert future_shift.start_time == time(9, 30)

    def test_delete_future_shift_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager and a future shift
        WHEN they send a DELETE request
        THEN the shift should be deleted.
        """
        future_shift = Shift.objects.create(
            store=self.store,
            employee=self.employee,
            date=now().date() + timedelta(days=30),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        shift_count_before = Shift.objects.count()
        url = reverse("api:manage_shift", kwargs={"id": future_shift.id})
        response = api_client.delete(url)
        assert (
            response.status_code == status.HTTP_200_OK
        )  # Your view returns 200 OK on delete
        assert Shift.objects.count() == shift_count_before - 1

    def test_delete_past_shift_fails(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager and a past shift
        WHEN they send a DELETE request
        THEN the request should fail with a 410 Gone error.
        """

        past_shift = self.shift1
        url = reverse("api:manage_shift", kwargs={"id": past_shift.id})
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_410_GONE

    # ===============================================
    # == Tests for list_store_roles
    # ===============================================
    def test_list_store_roles_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager
        WHEN they request the list of roles for their store
        THEN they should receive a 200 OK and a list containing the roles.
        """
        url = reverse("api:list_store_roles", kwargs={"id": self.store.id})
        response = api_client.get(url)

        data = response.json()
        assert response.status_code == status.HTTP_200_OK
        assert len(data["data"]) == 2
        assert data["data"][0]["name"] == "Cashier"  # It's ordered by name

    # ===============================================
    # == Tests for manage_store_role
    # ===============================================
    def test_role_crud_lifecycle(self, logged_in_manager, api_client):
        """
        Tests the full Create, Update (PATCH), and Delete lifecycle for roles.
        """
        role_count_before = Role.objects.filter(store=self.store).count()

        # 1. CREATE a new role

        create_url = reverse("api:create_store_role")
        create_data = {
            "name": "Driver",
            "store_id": self.store.id,
            "colour_hex": "#2ecc71",
        }
        response = api_client.post(create_url, create_data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert Role.objects.filter(store=self.store).count() == role_count_before + 1
        new_role_id = response.json()["id"]

        # 2. UPDATE (PATCH) the new role
        update_url = reverse("api:manage_store_role", kwargs={"role_id": new_role_id})
        update_data = {"name": "Lead Driver", "colour_hex": "#27ae60"}
        response = api_client.patch(update_url, update_data, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED
        updated_role = Role.objects.get(id=new_role_id)
        assert updated_role.name == "Lead Driver"
        assert updated_role.colour_hex == "#27ae60"

        # 3. DELETE the new role
        delete_url = reverse("api:manage_store_role", kwargs={"role_id": new_role_id})
        response = api_client.delete(delete_url)
        assert response.status_code == status.HTTP_200_OK
        assert Role.objects.filter(store=self.store).count() == role_count_before

    # ===============================================
    # == Tests for manage_store_exception
    # ===============================================
    def test_approve_exception_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager and an unapproved exception
        WHEN they send a POST request to approve it
        THEN the exception should be marked as approved.
        """
        assert not self.exception.is_approved
        url = reverse(
            "api:manage_store_exception", kwargs={"exception_id": self.exception.id}
        )
        response = api_client.post(url, {}, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED
        self.exception.refresh_from_db()
        assert self.exception.is_approved

    def test_approve_exception_with_patch_success(self, logged_in_manager, api_client):
        """
        GIVEN a logged-in manager
        WHEN they send a PATCH request to approve an exception with new times
        THEN the associated activity should be updated and the exception approved.
        """
        url = reverse(
            "api:manage_store_exception", kwargs={"exception_id": self.exception.id}
        )
        original_logout_time = self.activity.logout_time
        data = {"login_time": "08:00:00", "logout_time": "16:30:00"}
        response = api_client.patch(url, data, format="json")
        assert response.status_code == status.HTTP_202_ACCEPTED
        self.activity.refresh_from_db()
        assert self.activity.logout_time != original_logout_time
        assert localtime(self.activity.logout_time).strftime("%H:%M:%S") == "16:30:00"

    # ===============================================
    # == Tests for copy_week_schedule
    # ===============================================
    def test_copy_week_schedule_non_override(
        self, logged_in_manager, api_client, store
    ):
        """
        GIVEN a manager
        WHEN they copy a week with one conflicting and one non-conflicting shift
        THEN only the non-conflicting shift should be created.
        """

        Shift.objects.all().delete()

        emp_a = User.objects.create(email="emp_a@test.com", first_name="Copied")
        emp_b = User.objects.create(email="emp_b@test.com", first_name="Skipped")
        StoreUserAccess.objects.create(user=emp_a, store=store)
        StoreUserAccess.objects.create(user=emp_b, store=store)

        source_week = get_monday_of_week()
        target_week = source_week + timedelta(days=7)

        # SHIFT A (Non-conflicting): This shift should be copied successfully.
        Shift.objects.create(
            store=store,
            employee=emp_a,
            date=source_week,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        # SHIFT B (Conflicting): This shift should be skipped.
        Shift.objects.create(
            store=store,
            employee=emp_b,
            date=source_week,
            start_time=time(10, 0),
            end_time=time(18, 0),
        )
        # Create the conflicting shift in the target week
        Shift.objects.create(
            store=store,
            employee=emp_b,
            date=target_week,
            start_time=time(11, 0),
            end_time=time(19, 0),
        )

        url = reverse("api:copy_week_schedule", kwargs={"store_id": store.id})
        data = {
            "source_week": source_week.isoformat(),
            "target_week": target_week.isoformat(),
            "override_shifts": False,
        }
        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_202_ACCEPTED
        results = response.json()["results"]
        assert results["created"] == 1, "Should have created the non-conflicting shift."
        assert results["skipped"] == 1, "Should have skipped the conflicting shift."
