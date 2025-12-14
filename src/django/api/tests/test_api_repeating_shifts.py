from datetime import time
from django.urls import reverse
from auth_app.models import RepeatingShift
import pytest


@pytest.mark.django_db
def test_create_repeating_shift_success(
    logged_in_manager,
    store,
    employee,
    store_associate_manager,
    store_associate_employee,
):
    """
    Manager can successfully create a repeating shift for an employee
    associated with the same store.
    """

    api_client = logged_in_manager

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1, 2],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "09:00",
        "end_time": "17:00",
        "comment": "Morning shift",
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 201
    assert "repeating_shift_id" in response.json()

    shift = RepeatingShift.objects.get(id=response.json()["repeating_shift_id"])

    assert shift.store == store
    assert shift.employee == employee
    assert shift.comment == "Morning shift"
    assert shift.active_weeks == [1, 2]


@pytest.mark.django_db
def test_create_repeating_shift_conflict(
    logged_in_manager,
    store,
    employee,
    store_associate_manager,
    store_associate_employee,
):
    """
    Manager cannot create a repeating shift that conflicts with an existing one.
    """

    api_client = logged_in_manager

    RepeatingShift.objects.create(
        employee=employee,
        store=store,
        start_weekday=1,
        end_weekday=1,
        start_time=time(9, 0),
        end_time=time(17, 0),
        active_weeks=[1, 2],
    )

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1, 2],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "10:00",
        "end_time": "18:00",
        "comment": "Overlapping shift",
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 409
    assert "conflicts" in response.json()["Error"].lower()


@pytest.mark.django_db
def test_create_repeating_shift_unassociated_manager(
    logged_in_manager,
    store,
    employee,
    store_associate_employee,
):
    """
    Manager cannot create a repeating shift for an employee not associated with their store.
    """

    api_client = logged_in_manager

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "09:00",
        "end_time": "17:00",
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_create_repeating_shift_missing_required_field(
    logged_in_manager,
    store,
    employee,
    store_associate_manager,
    store_associate_employee,
):
    """
    Creating a repeating shift fails if a required field is missing.
    """

    api_client = logged_in_manager

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "09:00",
        # end_time missing
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 428
    assert "Missing required fields" in response.json()["Error"]


@pytest.mark.django_db
def test_create_repeating_shift_end_time_before_start_time(
    logged_in_manager,
    store,
    employee,
    store_associate_manager,
    store_associate_employee,
):
    """
    Creating a repeating shift fails if end_time is before start_time.
    """

    api_client = logged_in_manager

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "17:00",
        "end_time": "09:00",
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code in (412, 406)


@pytest.mark.django_db
def test_create_repeating_shift_employee_not_associated_417(
    logged_in_manager,
    store,
    employee,
    store_associate_manager,
):
    """
    Creating a repeating shift fails if the employee is not associated with the required store.
    """

    api_client = logged_in_manager

    payload = {
        "employee_id": str(employee.id),
        "active_weeks": [1],
        "start_weekday": 1,
        "end_weekday": 1,
        "start_time": "09:00",
        "end_time": "17:00",
    }

    response = api_client.post(
        reverse("api:create_repeating_shift", args=[store.id]),
        data=payload,
        format="json",
    )

    assert response.status_code == 417
