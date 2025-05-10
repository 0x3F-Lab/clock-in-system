import pytest
import api.controllers as controllers
import api.utils as util
import api.exceptions as err
from datetime import timedelta
from django.utils.timezone import now
from unittest.mock import patch
from auth_app.models import User, Activity


@pytest.mark.django_db
def test_get_users_name_only_active(
    employee,
    inactive_employee,
    store_associate_inactive_employee,
    store_associate_employee,
    store,
):
    """
    Test filtering users by only active status (only active users should be returned).
    """
    users = controllers.get_store_employee_names(store_id=store.id, only_active=True)

    # Only the active user should be returned
    assert len(users) == 1
    assert employee.id in users
    assert users[employee.id] == "John Doe"


@pytest.mark.django_db
def test_get_users_name_ignore_managers(
    employee, manager, store, store_associate_manager, store_associate_employee
):
    """
    Test filtering users by ignoring managers (should exclude managers).
    """
    users = controllers.get_store_employee_names(
        store_id=store.id, only_active=True, ignore_managers=True
    )

    # The manager should be excluded
    assert len(users) == 1
    assert employee.id in users
    assert users[employee.id] == "John Doe"


@pytest.mark.django_db
def test_get_users_name_order_by_first_name(
    employee, clocked_in_employee, store, store_associate_employee
):
    """
    Test ordering users by first name.
    """
    users = controllers.get_store_employee_names(
        store_id=store.id, order=True, order_by_first_name=True
    )

    # The users should be ordered by first name
    assert len(users) == 2
    ordered_names = list(users.values())
    assert ordered_names == ["Jane Doe", "John Doe"]


@pytest.mark.django_db
def test_get_users_name_order_by_last_name(
    employee, manager, store, store_associate_employee, store_associate_manager
):
    """
    Test ordering users by last name.
    """
    users = controllers.get_store_employee_names(
        store_id=store.id, order=True, order_by_first_name=False
    )

    # The users should be ordered by last name
    assert len(users) == 2
    ordered_names = list(users.values())
    assert ordered_names == ["John Doe", "Manager Test"]


@pytest.mark.django_db
def test_get_users_name_no_results(
    inactive_employee, store, store_associate_inactive_employee
):
    """
    Test the scenario where no users match the given criteria (should return None).
    """
    users = controllers.get_store_employee_names(store_id=store.id, only_active=True)

    assert len(users) == 0


@pytest.mark.django_db
def test_get_users_name_empty_query(
    employee, manager, store, store_associate_employee, store_associate_manager
):
    """
    Test the scenario when no filters are applied (default behavior).
    """

    users = controllers.get_store_employee_names(store_id=store.id)

    # All active users should be returned
    assert len(users) == 2
    assert employee.id in users
    assert manager.id in users


@pytest.mark.django_db
def test_check_new_shift_too_soon(employee, store):
    """
    Test that an employee can't start a new shift too soon after their last clock-out.
    """
    # First, clock the employee out with a gap
    last_activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=now() - timedelta(hours=2),
        login_timestamp=now() - timedelta(hours=2),
        logout_time=now() - timedelta(hours=1),  # 1 hour ago
        logout_timestamp=now()
        - timedelta(hours=1),  # NEED TIMESTAMP AS IT CHECKS TIMESTAMP NOT TIME
    )

    result = controllers.check_new_shift_too_soon(
        employee=employee, store=store, limit_mins=30
    )
    assert result is False  # Should be False as the shift is not too soon

    # Now, simulate trying to clock in too soon
    last_activity.logout_timestamp = now() - timedelta(minutes=5)  # 5 mins ago
    last_activity.save()

    result = controllers.check_new_shift_too_soon(
        employee=employee, store=store, limit_mins=30
    )
    assert result is True  # Should be True as the shift is too soon


@pytest.mark.django_db
def test_check_clocking_out_too_soon(employee, store):
    """
    Test that an employee can't clock out too soon after clocking in.
    """
    # Create a clock-in activity for the employee
    activity = Activity.objects.create(
        employee=employee,
        store=store,
        login_time=now() - timedelta(minutes=5),  # Clocked in 5 minutes ago
        login_timestamp=now() - timedelta(minutes=5),
    )

    result = controllers.check_clocking_out_too_soon(
        employee=employee, store=store, limit_mins=10
    )
    assert result is True  # Clocking out too soon, should return True

    # Move the clock in time outside the limits
    activity.login_timestamp = now() - timedelta(minutes=35)  # 35 mins ago
    activity.save()

    # Re-check the controller
    result = controllers.check_clocking_out_too_soon(
        employee=employee, store=store, limit_mins=10
    )
    assert result is False  # Clocking out after adequate time
