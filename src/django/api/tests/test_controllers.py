import pytest
from datetime import timedelta
from django.utils.timezone import now
from unittest.mock import patch
from auth_app.models import User, Activity
import api.controllers as controllers
import api.utils as util


@pytest.mark.django_db
@patch("api.utils.now")  # Mock 'now()' to control the timestamp
def test_handle_clock_in_success(mock_now, employee):
    """
    Test successful clock-in for an employee.
    """
    mock_now.return_value = now()  # Return the current time

    # Call the controller function to clock in
    response = controllers.handle_clock_in(employee.id)

    assert response.status_code == 201  # HTTP 201 Created
    data = response.data
    assert data["employee_id"] == employee.id

    # Check if Activity record is created
    activity = Activity.objects.filter(
        employee_id=employee, logout_time__isnull=True
    ).first()
    assert activity is not None

    # Calculate the difference between the timestamps and assert it is within the allowed tolerance (1 second)
    delta = abs(activity.login_timestamp - mock_now.return_value)
    assert delta <= timedelta(seconds=1), f"Timestamp difference is too large: {delta}"


@pytest.mark.django_db
@patch("api.utils.now")
def test_handle_clock_in_already_clocked_in(mock_now, clocked_in_employee):
    """
    Test attempting to clock in an employee who is already clocked in.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Call the controller function to clock in (should fail)
    response = controllers.handle_clock_in(clocked_in_employee.id)

    assert response.status_code == 400  # HTTP 400 Bad Request
    data = response.data
    assert data["Error"] == "Employee is already clocked in."


@pytest.mark.django_db
@patch("api.utils.now")
def test_handle_clock_in_employee_not_found(mock_now):
    """
    Test attempting to clock in with an invalid employee ID.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Call the controller function with an invalid employee ID
    response = controllers.handle_clock_in(999)

    assert response.status_code == 404  # HTTP 404 Not Found
    data = response.data
    assert data["Error"] == "Employee not found with the ID 999."


@pytest.mark.django_db
@patch("api.utils.now")
@patch("api.utils.round_datetime_minute")
def test_handle_clock_out_success(mock_round, mock_now, clocked_in_employee):
    """
    Test successful clock-out for an employee.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time
    mock_round.return_value = mock_now.return_value  # Mock rounding function

    # Call the controller function to clock out
    response = controllers.handle_clock_out(clocked_in_employee.id, deliveries=5)

    assert response.status_code == 200  # HTTP 200 OK
    data = response.data
    assert data["employee_id"] == clocked_in_employee.id
    assert data["deliveries"] == 5

    # Check if Activity record is updated
    activity = Activity.objects.filter(
        employee_id=clocked_in_employee, logout_time__isnull=False
    ).first()
    assert activity is not None
    assert activity.deliveries == 5
    assert activity.logout_time == mock_now.return_value


@pytest.mark.django_db
@patch("api.utils.now")
def test_handle_clock_out_not_clocked_in(mock_now, employee):
    """
    Test attempting to clock out an employee who is not clocked in.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Call the controller function to clock out (should fail)
    response = controllers.handle_clock_out(employee.id, deliveries=5)

    assert response.status_code == 400  # HTTP 400 Bad Request
    data = response.data
    assert data["Error"] == "Employee is not clocked in."


@pytest.mark.django_db
@patch("api.utils.now")
def test_handle_clock_out_employee_not_found(mock_now):
    """
    Test attempting to clock out with an invalid employee ID.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Call the controller function with an invalid employee ID
    response = controllers.handle_clock_out(999, deliveries=5)

    assert response.status_code == 404  # HTTP 404 Not Found
    data = response.data
    assert data["Error"] == "Employee not found with the ID 999."
