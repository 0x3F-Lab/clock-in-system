import pytest
from django.urls import reverse

from auth_app.models import RepeatingShift


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
