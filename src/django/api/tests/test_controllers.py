import pytest
import api.controllers as controllers
import api.utils as util
import api.exceptions as err
from datetime import timedelta
from django.utils.timezone import now
from unittest.mock import patch
from auth_app.models import User, Activity, KeyValueStore


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
@patch("api.controllers.now")  # Mock 'now()' to control the timestamp
def test_handle_clock_in_success(mock_now, employee):
    """
    Test successful clock-in for an employee.
    """
    mock_now.return_value = now()  # Return the current time

    # Call the controller function to clock in
    activity = controllers.handle_clock_in(employee.id)

    # Validate that the returned object is an Activity instance
    assert isinstance(activity, Activity)

    # Check that the activity belongs to the employee
    assert activity.employee_id == employee
    assert activity.logout_time is None

    # Calculate the difference between the timestamps and assert it is within the allowed tolerance (1 second)
    delta = abs(activity.login_timestamp - mock_now.return_value)
    assert delta <= timedelta(seconds=1), f"Timestamp difference is too large: {delta}"


@pytest.mark.django_db
@patch("api.controllers.now")
def test_handle_clock_in_already_clocked_in(mock_now, clocked_in_employee):
    """
    Test attempting to clock in an employee who is already clocked in.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Attempt to clock in a user who is already clocked in
    with pytest.raises(err.AlreadyClockedInError) as excinfo:
        controllers.handle_clock_in(clocked_in_employee.id)

    # Check the exception message
    assert str(excinfo.value) == "Employee is already clocked in."


@pytest.mark.django_db
@patch("api.controllers.now")
def test_handle_clock_in_employee_not_found(mock_now):
    """
    Test attempting to clock in with an invalid employee ID.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Attempt to clock in a non-existent employee
    with pytest.raises(User.DoesNotExist) as excinfo:
        controllers.handle_clock_in(999)

    # Check the exception message
    assert str(excinfo.value) == "User matching query does not exist."


@pytest.mark.django_db
@patch("api.controllers.now")
@patch("api.utils.round_datetime_minute")
def test_handle_clock_out_success(mock_round, mock_now, clocked_in_employee):
    """
    Test successful clock-out for an employee.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time
    mock_round.return_value = mock_now.return_value  # Mock rounding function

    # Call the controller function to clock out
    activity = controllers.handle_clock_out(clocked_in_employee.id, deliveries=5)

    # Validate the returned Activity instance
    assert isinstance(activity, Activity)
    assert activity.employee_id == clocked_in_employee
    assert activity.deliveries == 5

    # Allow for a small tolerance when comparing timestamps
    timestamp_difference = abs(activity.logout_timestamp - mock_now.return_value)
    assert timestamp_difference <= timedelta(
        seconds=1
    ), f"Timestamp difference is too large: {timestamp_difference}"

    # Ensure the logout_time is correctly rounded
    assert activity.logout_time == mock_round.return_value


@pytest.mark.django_db
@patch("api.controllers.now")
def test_handle_clock_out_not_clocked_in(mock_now, employee):
    """
    Test attempting to clock out an employee who is not clocked in.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Attempt to clock out an employee who is not clocked in
    with pytest.raises(err.AlreadyClockedOutError) as excinfo:
        controllers.handle_clock_out(employee.id, deliveries=5)

    # Check the exception message
    assert str(excinfo.value) == "Employee is already clocked out."


@pytest.mark.django_db
@patch("api.controllers.now")
def test_handle_clock_out_no_active_record(mock_now, clocked_in_employee):
    """
    Test attempting to clock out an employee without an active clock-in record.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Simulate the scenario where no active clock-in record exists
    Activity.objects.filter(
        employee_id=clocked_in_employee, logout_time__isnull=True
    ).delete()

    # Attempt to clock out
    with pytest.raises(err.NoActiveClockingRecordError) as excinfo:
        controllers.handle_clock_out(clocked_in_employee.id, deliveries=5)

    # Check the exception message
    assert (
        str(excinfo.value)
        == "No active clock-in activity found. Resetting user's clocked state."
    )


@pytest.mark.django_db
@patch("api.controllers.now")
def test_handle_clock_out_employee_not_found(mock_now):
    """
    Test attempting to clock out with an invalid employee ID.
    """
    mock_now.return_value = now()  # Mock 'now()' to return the current time

    # Attempt to clock out a non-existent employee
    with pytest.raises(User.DoesNotExist) as excinfo:
        controllers.handle_clock_out(999, deliveries=5)

    # Check the exception message
    assert str(excinfo.value) == "User matching query does not exist."


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
        err.NoActiveClockingRecordError,
        match="No active clock-in activity found. Resetting user's clocked state.",
    ):
        controllers.get_employee_clocked_info(employee_id=employee.id)


@pytest.mark.django_db
def test_get_store_location_success(store_location):
    """
    Test fetching store location successfully.
    """
    store_lat, store_lon = controllers.get_store_location()
    assert store_lat == 1.0
    assert store_lon == 1.0


@pytest.mark.django_db
def test_get_store_location_missing_key():
    """
    Test fetching store location when keys are missing.
    """
    KeyValueStore.objects.all().delete()  # Remove all entries
    with pytest.raises(KeyValueStore.DoesNotExist):
        controllers.get_store_location()


@pytest.mark.django_db
def test_get_clocking_range_limit_success(store_location):
    """
    Test fetching the allowable clocking distance successfully.
    """
    allowable_dist = controllers.get_clocking_range_limit()
    assert allowable_dist == 5.0


@pytest.mark.django_db
def test_get_clocking_range_limit_invalid_value():
    """
    Test fetching the allowable clocking distance with invalid value.
    """
    KeyValueStore.objects.create(key="allowable_clocking_dist_m", value="invalid")
    with pytest.raises(ValueError):
        controllers.get_clocking_range_limit()


@pytest.mark.django_db
def test_check_new_shift_too_soon(employee):
    """
    Test that an employee can't start a new shift too soon after their last clock-out.
    """
    # First, clock the employee out with a gap
    last_activity = Activity.objects.create(
        employee_id=employee,
        login_time=now() - timedelta(hours=2),
        login_timestamp=now() - timedelta(hours=2),
        logout_time=now() - timedelta(hours=1),  # 1 hour ago
        logout_timestamp=now()
        - timedelta(hours=1),  # NEED TIMESTAMP AS IT CHECKS TIMESTAMP NOT TIME
    )

    result = controllers.check_new_shift_too_soon(employee.id, limit_mins=30)
    assert result is False  # Should be False as the shift is not too soon

    # Now, simulate trying to clock in too soon
    last_activity.logout_timestamp = now() - timedelta(minutes=5)  # 5 mins ago
    last_activity.save()

    result = controllers.check_new_shift_too_soon(employee.id, limit_mins=30)
    assert result is True  # Should be True as the shift is too soon


@pytest.mark.django_db
def test_check_clocking_out_too_soon(employee):
    """
    Test that an employee can't clock out too soon after clocking in.
    """
    # Create a clock-in activity for the employee
    activity = Activity.objects.create(
        employee_id=employee,
        login_time=now() - timedelta(minutes=5),  # Clocked in 5 minutes ago
        login_timestamp=now() - timedelta(minutes=5),
    )

    result = controllers.check_clocking_out_too_soon(employee.id, limit_mins=10)
    assert result is True  # Clocking out too soon, should return True

    # Move the clock in time outside the limits
    activity.login_timestamp = now() - timedelta(minutes=35)  # 35 mins ago
    activity.save()

    # Re-check the controller
    result = controllers.check_clocking_out_too_soon(employee.id, limit_mins=10)
    assert result is False  # Clocking out after adequate time
