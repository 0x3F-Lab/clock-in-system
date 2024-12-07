import pytest
from datetime import timedelta
from django.utils.timezone import now
from unittest.mock import patch
from auth_app.models import User, Activity
import api.controllers as controllers
import api.utils as util


@pytest.mark.django_db
def test_get_users_name_only_active(employee, inactive_employee):
    """
    Test filtering users by only active status (only active users should be returned).
    """
    users = controllers.get_users_name(only_active=True)

    # Only the active user should be returned
    assert len(users) == 1
    assert users[0][0] == employee.id
    assert users[0][1] == "John Doe"


@pytest.mark.django_db
def test_get_users_name_ignore_managers(employee, manager):
    """
    Test filtering users by ignoring managers (should exclude managers).
    """
    users = controllers.get_users_name(only_active=True, ignore_managers=True)

    # The manager should be excluded
    assert len(users) == 1
    assert users[0][0] == employee.id
    assert users[0][1] == "John Doe"


@pytest.mark.django_db
def test_get_users_name_order_by_first_name(employee, clocked_in_employee):
    """
    Test ordering users by first name.
    """
    users = controllers.get_users_name(order=True, order_by_first_name=True)

    # The users should be ordered by first name
    assert len(users) == 2
    assert users[0][0] == clocked_in_employee.id
    assert users[0][1] == "Jane Doe"
    assert users[1][0] == employee.id
    assert users[1][1] == "John Doe"


@pytest.mark.django_db
def test_get_users_name_order_by_last_name(employee, manager):
    """
    Test ordering users by last name.
    """
    users = controllers.get_users_name(order=True, order_by_first_name=False)

    # The users should be ordered by last name
    assert len(users) == 2
    assert users[0][0] == employee.id
    assert users[0][1] == "John Doe"
    assert users[1][0] == manager.id
    assert users[1][1] == "Manager Test"


@pytest.mark.django_db
def test_get_users_name_no_results(inactive_employee):
    """
    Test the scenario where no users match the given criteria (should return None).
    """
    with pytest.raises(User.DoesNotExist, match="No active clock-in activity found."):
        controllers.get_users_name(only_active=True)


@pytest.mark.django_db
def test_get_users_name_empty_query(employee, manager):
    """
    Test the scenario when no filters are applied (default behavior).
    """

    users = controllers.get_users_name()

    # All active users should be returned
    assert len(users) == 2
    assert users[0][0] == employee.id
    assert users[1][0] == manager.id


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


@pytest.mark.django_db
def test_get_employee_clocked_info_success(employee):
    """
    Test fetching clocked info for an employee who is not clocked in.
    """
    info = controllers.get_employee_clocked_info(employee_id=employee.id)

    assert info["employee_id"] == employee.id
    assert info["name"] == f"{employee.first_name} {employee.last_name}"
    assert info["clocked_in"] is False


@pytest.mark.django_db
def test_get_employee_clocked_info_clocked_in_success(clocked_in_employee):
    """
    Test fetching clocked info for an employee who is clocked in.
    """
    info = controllers.get_employee_clocked_info(employee_id=clocked_in_employee.id)

    assert info["employee_id"] == clocked_in_employee.id
    assert (
        info["name"]
        == f"{clocked_in_employee.first_name} {clocked_in_employee.last_name}"
    )
    assert info["clocked_in"] is True
    assert "login_time" in info
    assert "login_timestamp" in info


@pytest.mark.django_db
def test_get_employee_clocked_info_user_not_found():
    """
    Test fetching clocked info for a non-existent employee.
    """
    with pytest.raises(User.DoesNotExist):
        controllers.get_employee_clocked_info(employee_id=999)


@pytest.mark.django_db
def test_get_employee_clocked_info_bugged_state(employee):
    """
    Test fetching clocked info for an employee with a bugged state (no activity record).
    """
    # Mark employee as clocked in without an activity record
    employee.clocked_in = True
    employee.save()

    with pytest.raises(
        Activity.DoesNotExist, match="No active clock-in activity found."
    ):
        controllers.get_employee_clocked_info(employee_id=employee.id)
