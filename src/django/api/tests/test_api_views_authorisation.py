import pytest
from django.urls import reverse
from django.utils.timezone import timedelta, now, make_aware
from auth_app.models import Activity


@pytest.mark.django_db
def test_list_store_employee_names_not_authorised(
    logged_in_employee,
    manager,
    store,
    store_associate_employee,
    store_associate_manager,
    inactive_employee,
    employee,
):
    """
    Test attempt to list store employees from a unauthorised account.
    """
    api_client = logged_in_employee
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
    api_client, manager, logged_in_employee, store, store_associate_manager, employee
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
    api_client, manager, logged_in_manager, store, employee
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
    api_client, logged_in_employee, store, store_associate_employee, employee
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
def test_list_singular_shift_details_not_associated(
    api_client, logged_in_manager, employee, store
):
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
def test_update_shift_details_unauthorised_user(
    api_client, logged_in_employee, store, employee
):
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
def test_update_shift_details_not_associated_store(
    api_client, logged_in_manager, store, employee
):
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
def test_create_new_shift_unauthorised_user(
    api_client, logged_in_employee, store, employee
):
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
    api_client, logged_in_manager, store_associate_employee, employee, store
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
        "Not authorised to create a new shift for an unassociated store."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_create_new_shift_unassociated_employee(
    api_client, logged_in_manager, store_associate_manager, employee, store
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
    api_client, logged_in_employee, store
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
def test_list_all_employee_details_not_associated_store(
    api_client, logged_in_manager, store
):
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
    api_client, logged_in_employee, employee
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
    api_client, logged_in_manager, manager, store, store_associate_manager, employee
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
def test_create_new_employee_unauthorised(api_client, logged_in_employee, store):
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
def test_create_new_employee_not_associated(api_client, logged_in_manager, store):
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
    assert (
        "Not authorised to update another store's employee list."
        in response.json()["Error"]
    )
