import pytest
from django.urls import reverse
from django.utils.timezone import timedelta, now, make_aware
from auth_app.models import (
    Shift,
    Role,
    Store,
    User,
    ShiftException,
    Activity,
    StoreUserAccess,
)
from datetime import date, time, timedelta
from rest_framework import status


@pytest.mark.django_db
def test_list_store_employee_names_not_associated(
    logged_in_manager,
    manager,
    store,
    store_associate_employee,
    inactive_employee,
    employee,
):
    """
    Test attempt to list store employees from a unassociated manager account.
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

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_all_shift_details_not_autorised(
    manager, logged_in_employee, store, store_associate_manager, employee
):
    """
    Test that shift details aren't returned when requesting from an unauthorised account.
    """
    api_client = logged_in_employee

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

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_all_shift_details_not_associated(
    manager, logged_in_manager, store, employee
):
    """
    Test that shift details aren't returned when requesting for an unassociated store.
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

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_singular_shift_details_unauthorised(
    logged_in_employee, store, store_associate_employee, employee
):
    """
    Test that a non-manager cannot retrieve shift details.
    """
    api_client = logged_in_employee

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=now() - timedelta(hours=4),
        login_timestamp=now() - timedelta(hours=4),
        logout_time=now(),
        logout_timestamp=now(),
        is_public_holiday=True,
        deliveries=1,
    )

    url = reverse("api:list_singular_shift_details", args=[activity.id])
    response = api_client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_singular_shift_details_not_associated(logged_in_manager, employee, store):
    """
    Test that a manager cannot retrieve shift details for an unassociated store.
    """
    api_client = logged_in_manager

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=now() - timedelta(hours=4),
        login_timestamp=now() - timedelta(hours=4),
        logout_time=now(),
        logout_timestamp=now(),
        is_public_holiday=False,
        deliveries=3,
    )

    # NOTE: No store_associate_manager created → manager not associated with this store
    url = reverse("api:list_singular_shift_details", args=[activity.id])
    response = api_client.get(url)

    assert response.status_code == 403


@pytest.mark.django_db
def test_update_shift_details_unauthorised_user(logged_in_employee, store, employee):
    """
    Test that a non-manager (unauthorised) user cannot update shift details.
    """
    api_client = logged_in_employee

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_timestamp=now() - timedelta(hours=2),
        login_time=now() - timedelta(hours=2),
        logout_timestamp=now(),
        logout_time=now(),
    )

    response = api_client.patch(
        reverse("api:update_shift_details", args=[activity.id]),
        data={
            "login_timestamp": (now() - timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_update_shift_details_not_associated_store(logged_in_manager, store, employee):
    """
    Test that a manager cannot update shift details for a store they are not associated with.
    """
    api_client = logged_in_manager

    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_timestamp=now() - timedelta(hours=2),
        login_time=now() - timedelta(hours=2),
        logout_timestamp=now(),
        logout_time=now(),
    )

    # no store_associate_manager, so manager isn't linked to store
    response = api_client.patch(
        reverse("api:update_shift_details", args=[activity.id]),
        data={
            "login_timestamp": (now() - timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_new_shift_unauthorised_user(logged_in_employee, store, employee):
    """
    Test that a non-manager (unauthorised) user cannot create a new shift.
    """
    api_client = logged_in_employee

    response = api_client.put(
        reverse("api:create_new_shift"),
        data={
            "employee_id": str(employee.id),
            "store_id": store.id,
            "login_timestamp": (now() - timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "deliveries": 2,
            "is_public_holiday": False,
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_new_shift_not_associated_store(
    logged_in_manager, store_associate_employee, employee, store
):
    """
    Test that a manager cannot create a shift for a store they are not associated with.
    """
    api_client = logged_in_manager

    # Assume store_associate_manager fixture NOT applied — manager isn't linked to store
    response = api_client.put(
        reverse("api:create_new_shift"),
        data={
            "employee_id": str(employee.id),
            "store_id": store.id,
            "login_timestamp": (now() - timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "deliveries": 2,
            "is_public_holiday": False,
        },
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to create a new shift for the store."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_create_new_shift_unassociated_employee(
    logged_in_manager, store_associate_manager, employee, store
):
    """
    Test that a manager cannot create a shift for a store they are not associated with.
    """
    api_client = logged_in_manager

    # Assume store_associate_manager fixture NOT applied — manager isn't linked to store
    response = api_client.put(
        reverse("api:create_new_shift"),
        data={
            "employee_id": str(employee.id),
            "store_id": store.id,
            "login_timestamp": (now() - timedelta(hours=2)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "logout_timestamp": (now() - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
            "deliveries": 2,
            "is_public_holiday": False,
        },
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to create a new shift with another store's employee."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_list_all_employee_details_unauthorised_user(
    logged_in_employee, store, store_associate_employee
):
    """
    Test that a non-manager (unauthorised) user cannot retrieve employee details.
    """
    api_client = logged_in_employee

    response = api_client.get(
        reverse("api:list_all_employee_details"),
        data={"store_id": store.id},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_all_employee_details_not_associated_store(logged_in_manager, store):
    """
    Test that a manager cannot retrieve employee details for a store they are not associated with.
    """
    api_client = logged_in_manager

    # No store_associate_manager fixture applied

    response = api_client.get(
        reverse("api:list_all_employee_details"),
        data={"store_id": store.id},
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to view employee data for this store."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_list_singular_employee_details_unauthorised_user(
    logged_in_employee, employee, store_associate_employee
):
    """
    Test that a non-manager (unauthorised) user cannot retrieve employee details.
    """
    api_client = logged_in_employee

    response = api_client.get(
        reverse("api:list_singular_employee_details", args=[employee.id]),
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_list_singular_employee_details_not_associated(
    logged_in_manager, manager, store, store_associate_manager, employee
):
    """
    Test that a manager cannot access details of an employee not associated with their store.
    """
    api_client = logged_in_manager

    # No store_associate_manager fixture → manager not associated with employee's store

    response = api_client.get(
        reverse("api:list_singular_employee_details", args=[employee.id]),
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to get employee information of an employee associated to a different store."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_create_new_employee_unauthorised(
    logged_in_employee, store, store_associate_employee
):
    """
    Test that a non-manager user cannot create a new employee.
    """
    api_client = logged_in_employee

    response = api_client.put(
        reverse("api:create_new_employee"),
        data={
            "first_name": "Bob",
            "last_name": "Smith",
            "email": "bob@example.com",
            "store_id": str(store.id),
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_new_employee_not_associated(logged_in_manager, store):
    """
    Test that a manager cannot create a new employee for a store they are not associated with.
    """
    api_client = logged_in_manager

    # No store_associate_manager → not linked to store

    response = api_client.put(
        reverse("api:create_new_employee"),
        data={
            "first_name": "Carol",
            "last_name": "White",
            "email": "carol@example.com",
            "store_id": str(store.id),
        },
        format="json",
    )

    assert response.status_code == 403
    assert "Not authorised to this store's employee list." in response.json()["Error"]


@pytest.mark.django_db
def test_manager_cannot_update_employee_in_other_store(
    logged_in_manager, store_associate_manager, employee
):
    api_client = logged_in_manager

    response = api_client.patch(
        reverse("api:modify_other_account_information", args=[employee.id]),
        data={"first_name": "BlockedUpdate"},
        format="json",
    )

    assert response.status_code == 403
    assert (
        "Not authorised to update this employee's account information."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_list_account_summaries_denied_for_employee(
    logged_in_employee, store, store_associate_employee
):
    """
    Test that an employee cannot access the list_account_summaries endpoint.
    """
    api_client = logged_in_employee

    url = reverse("api:list_account_summaries")
    response = api_client.get(
        url,
        {
            "store_id": store.id,
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
    )

    assert response.status_code == 403
    assert "Error" in response.json()


@pytest.mark.django_db
def test_list_account_summaries_manager_not_associated(logged_in_manager, store):
    """
    Test that a manager not associated with a store cannot access account summaries for it.
    """
    api_client = logged_in_manager

    url = reverse("api:list_account_summaries")
    response = api_client.get(
        url,
        {
            "store_id": store.id,
            "start": "2024-01-01",
            "end": "2024-01-31",
        },
    )

    assert response.status_code == 403
    assert "Not authorised to get summaries for this store." in response.json()["Error"]


@pytest.mark.django_db
def test_update_store_info(logged_in_manager, manager, store):
    """
    Test that a unassociated manager CANNOT update an unassociated store's info.
    """
    # Change the store's info
    api_client = logged_in_manager
    url = reverse("api:update_store_info", args=[store.id])
    data = {
        "name": "edit name",
        "loc_street": "edit street",
        "code": "NEWCODE",
        "clocking_dist": 450,
    }
    response = api_client.patch(url, data=data)

    assert response.status_code == 403
    assert "Not authorised to update an unassociated store." in response.json()["Error"]


@pytest.mark.django_db
def test_update_store_info(logged_in_employee, store, store_associate_employee):
    """
    Test that a unassociated manager CANNOT update an unassociated store's info.
    """
    # Change the store's info
    api_client = logged_in_employee
    url = reverse("api:update_store_info", args=[store.id])
    data = {
        "name": "edit name",
        "loc_street": "edit street",
        "code": "NEWCODE",
        "clocking_dist": 450,
    }
    response = api_client.patch(url, data=data)

    assert response.status_code == 403
    assert "Error" in response.json()


@pytest.mark.django_db
class TestScheduleAuthorisation:
    """
    Test suite specifically for authorisation rules on the schedule-related API views.
    """

    @pytest.fixture
    def other_store(self, db):
        """Creates a second, fully-formed store for testing."""
        return Store.objects.create(
            name="Other Store",
            code="OTH001",
            is_active=True,
            location_latitude=2.0,
            location_longitude=2.0,
            store_pin="111",
            is_scheduling_enabled=True,
        )

    # --- Tests for create_store_shift ---
    def test_create_shift_unauthorised_employee(self, logged_in_employee, store):
        """
        GIVEN a logged-in non-manager employee
        WHEN they attempt to create a shift
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_employee
        url = reverse("api:create_shift", kwargs={"store_id": store.id})
        data = {
            "employee_id": 1,
            "date": "2025-12-25",
            "start_time": "09:00",
            "end_time": "17:00",
        }

        response = api_client.put(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Tests for manage_store_shift (e.g., DELETE) ---
    def test_manage_shift_not_associated_manager(
        self, logged_in_manager, employee, other_store
    ):
        """
        GIVEN a manager who is NOT associated with a store
        WHEN they attempt to delete a shift from that store
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_manager

        shift_in_other_store = Shift.objects.create(
            store=other_store,
            employee=employee,
            date=now().date() + timedelta(days=30),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        url = reverse("api:manage_shift", kwargs={"id": shift_in_other_store.id})
        response = api_client.delete(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Tests for list_store_roles ---
    def test_list_store_roles_not_associated_manager(
        self, logged_in_manager, other_store
    ):
        """
        GIVEN a manager who is NOT associated with a store
        WHEN they attempt to list the roles of that store
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_manager
        url = reverse("api:list_store_roles", kwargs={"id": other_store.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Tests for manage_store_role (e.g., Create) ---
    def test_create_role_not_associated_manager(self, logged_in_manager, other_store):
        """
        GIVEN a manager who is NOT associated with a store
        WHEN they attempt to create a role for that store
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_manager
        url = reverse("api:create_store_role")
        data = {
            "name": "Intruder Role",
            "store_id": other_store.id,
            "colour_hex": "#000000",
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # --- Tests for copy_week_schedule ---
    def test_copy_week_unauthorised_employee(self, logged_in_employee, store):
        """
        GIVEN a logged-in non-manager employee
        WHEN they attempt to copy a week's schedule
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_employee
        url = reverse("api:copy_week_schedule", kwargs={"store_id": store.id})
        data = {
            "source_week": "2025-01-06",
            "target_week": "2025-01-13",
            "override_shifts": False,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_copy_week_not_associated_manager(self, logged_in_manager, other_store):
        """
        GIVEN a manager who is NOT associated with a store
        WHEN they attempt to copy a schedule for that store
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_manager
        url = reverse("api:copy_week_schedule", kwargs={"store_id": other_store.id})
        data = {
            "source_week": "2025-01-06",
            "target_week": "2025-01-13",
            "override_shifts": False,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manage_exception_unauthorised_employee(
        self, logged_in_employee, employee, store
    ):
        """
        GIVEN a logged-in non-manager employee
        WHEN they attempt to approve an exception
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_employee
        activity = Activity.objects.create(
            employee=employee, store=store, login_time=now(), logout_time=now()
        )
        exception = ShiftException.objects.create(
            activity=activity, reason=ShiftException.Reason.INCORRECTLY_CLOCKED
        )

        url = reverse(
            "api:manage_store_exception", kwargs={"exception_id": exception.id}
        )
        response = api_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_manage_exception_not_associated_manager(
        self, logged_in_manager, employee, other_store
    ):
        """
        GIVEN a manager who is NOT associated with a store
        WHEN they attempt to approve an exception from that store
        THEN they should be denied with a 403 Forbidden error.
        """
        api_client = logged_in_manager
        # Create an employee and an activity associated with the other_store
        StoreUserAccess.objects.create(user=employee, store=other_store)
        activity_in_other_store = Activity.objects.create(
            employee=employee, store=other_store, login_time=now(), logout_time=now()
        )
        exception_in_other_store = ShiftException.objects.create(
            activity=activity_in_other_store,
            reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
        )

        url = reverse(
            "api:manage_store_exception",
            kwargs={"exception_id": exception_in_other_store.id},
        )
        response = api_client.post(url, {}, format="json")

        assert response.status_code == status.HTTP_403_FORBIDDEN
