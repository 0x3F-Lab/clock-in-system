import logging
import api.exceptions as err
import api.utils as util

from typing import Union, Dict
from datetime import timedelta, datetime
from django.db import transaction
from django.db.models.functions import Coalesce
from django.db.models import Sum, Q, OuterRef, Subquery, IntegerField, Value
from django.utils.timezone import now, localtime, make_aware
from auth_app.models import User, Activity, Store
from clock_in_system.settings import (
    START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
    FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS,
)


logger = logging.getLogger("api")


def get_store_employee_names(
    store_id: Union[int, str, Store],
    only_active: bool = True,
    ignore_managers: bool = False,
    order: bool = True,
    order_by_first_name: bool = True,
    ignore_clocked_in: bool = False,
) -> Dict[int, str]:
    """
    Fetches a list of users with their IDs and full names.

    Args:
        store_id (int OR string OR Store object): The ID of the store to list all employees for. MUST BE PROVIDED.
        only_active (bool): Include only active users if True.
        ignore_managers (bool): Exclude managers if True.
        ignore_clocked_in (bool): Wether to ignore users who are clocked in.
        order (bool): Whether to order by the user's names, otherwise order by their id.
        order_by_first_name (bool): Order by first name if True, otherwise by last name.

    Returns:
        Dict[int, str]: A dictionary where the ID is the key and the value is the user's full name.
    """
    # Ensure store is provided
    if isinstance(store_id, Store):
        store = store_id
    elif isinstance(store_id, (int, str)) and str(store_id).isdigit():
        store = Store.objects.get(id=int(store_id))
    else:
        raise ValueError("Invalid store_id provided")

    # Get users associated with the store (ignore hidden users)
    users = User.objects.filter(store_access__store=store, is_hidden=False).distinct()

    # Apply filters
    if only_active:
        users = users.filter(is_active=True)
    if ignore_managers:
        users = users.filter(is_manager=False)

    # Filter out clocked-in users manually
    if ignore_clocked_in:
        users = [user for user in users if not user.is_clocked_in(store)]

    # Sort
    if order:
        users = sorted(
            users,
            key=lambda user: (
                (user.first_name.lower(), user.last_name.lower())
                if order_by_first_name
                else (user.last_name.lower(), user.first_name.lower())
            ),
        )

    return {user.id: f"{user.first_name} {user.last_name}" for user in users}


def handle_clock_in(employee_id: int, store_id: int, manual: bool = False) -> Activity:
    """
    Handles clocking in an employee by ID.

    Args:
        employee_id (int): The employee's ID.
        store_id (int): The store's ID for which the clocking event will register.
        manual (bool) = False: Whether the clock in is requested via manual clocking page or not. For logging purposes only.

    Returns:
        Activity: An activity object containing the information about the clock in.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Get the store
            store = Store.objects.get(id=store_id)

            # Check if user is inactive
            if not employee.is_active:
                raise err.InactiveUserError

            # Check if already clocked in
            elif employee.is_clocked_in(store=store):
                raise err.AlreadyClockedInError

            # Check if user is inactive
            elif not employee.is_active:
                raise err.InactiveUserError

            # Check user is associated with the store
            if not employee.is_associated_with_store(store):
                raise err.NotAssociatedWithStoreError

            # Check the store is active
            if not store.is_active:
                raise err.InactiveStoreError

            # Check if the employee is trying to clock in too soon after their last shift (default=30m)
            if check_new_shift_too_soon(employee=employee, store=store):
                raise err.StartingShiftTooSoonError

            time = localtime(now())  # Consistent timestamp

            # Create Activity record
            activity = Activity.objects.create(
                employee=employee,
                store=store,
                login_timestamp=time,
                login_time=util.round_datetime_minute(
                    time
                ),  # Default to round to nearest 15m
                is_public_holiday=util.is_public_holiday(time),
                deliveries=0,
            )

            logger.info(
                f"Employee ID {employee.id} ({employee.first_name} {employee.last_name}) CLOCKED IN under the store ID {store.id} [{store.code}]{' via MANUAL CLOCKING' if manual else ''}."
            )
            logger.debug(
                f"[CREATE: ACTIVITY (ID: {activity.id})] [{'MANUAL ' if manual else ''}CLOCK-IN] Employee ID {employee.id} ({employee.first_name} {employee.last_name}) -- Store ID: {store.id} [{store.code}] -- Login: {activity.login_time} ({activity.login_timestamp}) -- PUBLIC HOLIDAY: {activity.is_public_holiday}"
            )
            return activity

    except (
        err.AlreadyClockedInError,
        err.InactiveUserError,
        User.DoesNotExist,
        Store.DoesNotExist,
        err.StartingShiftTooSoonError,
        err.NotAssociatedWithStoreError,
        err.InactiveStoreError,
    ) as e:
        # Re-raise common errors
        raise e
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to clock in employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e


def handle_clock_out(
    employee_id: int, deliveries: int, store_id: int, manual: bool = False
) -> Activity:
    """
    Handles clocking out an employee by ID.

    Args:
        employee_id (int): The employee's ID.
        deliveries (int): Number of deliveries made during the shift.
        store_id (int): The store's ID for which the clocking event will register.
        manual (bool) = False: Whether the clock out is requested via manual clocking page or not. For logging purposes only.

    Returns:
        Activity: An activity object containing the information about the clock out.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(id=employee_id)

            # Get the store
            store = Store.objects.get(id=store_id)

            # Check if user is inactive
            if not employee.is_active:
                raise err.InactiveUserError

            # Check if not clocked in
            elif not employee.is_clocked_in(store=store):
                raise err.AlreadyClockedOutError

            # Check user is associated with the store
            if not employee.is_associated_with_store(store):
                raise err.NotAssociatedWithStoreError

            # Check the store is active
            if not store.is_active:
                raise err.InactiveStoreError

            # Fetch the last active clock-in record
            activity = employee.get_last_active_activity_for_store(store=store)

            # Check if the employee is trying to clock out too soon after their last shift (default=10m)
            if check_clocking_out_too_soon(employee=employee, store=store):
                raise err.ClockingOutTooSoonError

            time = localtime(now())
            activity.logout_timestamp = time
            activity.logout_time = util.round_datetime_minute(
                time
            )  # Default to round to nearest 15m
            activity.deliveries = deliveries
            activity.shift_length_mins = util.calculate_shift_length_mins(
                start=activity.login_time, end=activity.logout_time
            )
            activity.save()

            logger.info(
                f"Employee ID {employee.id} ({employee.first_name} {employee.last_name}) CLOCKED OUT under the store ID {store.id} [{store.code}]{' via MANUAL CLOCKING' if manual else ''}."
            )
            logger.debug(
                f"[UPDATE: ACTIVITY (ID: {activity.id})] [{'MANUAL ' if manual else ''}CLOCK-OUT] Employee ID {employee.id} ({employee.first_name} {employee.last_name}) -- Store ID: {store.id} [{store.code}] -- Login: {activity.login_time} ({activity.login_timestamp}) -- Logout: {activity.logout_time} ({activity.logout_timestamp}) -- Deliveries: {activity.deliveries} -- Shift Length: {activity.shift_length_mins}mins -- PUBLIC HOLIDAY: {activity.is_public_holiday}"
            )
            return activity

    except (
        err.AlreadyClockedOutError,
        User.DoesNotExist,
        Store.DoesNotExist,
        err.InactiveUserError,
        err.StartingShiftTooSoonError,
        err.NotAssociatedWithStoreError,
        err.InactiveStoreError,
    ) as e:
        # Re-raise common errors
        raise e
    except Exception as e:
        logger.error(
            f"Failed to clock out employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e


def get_employee_clocked_info(employee_id: int, store_id: int) -> dict:
    """
    Get detailed clocked information for an employee for a certain store.

    Args:
        employee_id (int): The ID of the employee.
        store_id (int): The ID of the store the employee is associated to.

    Returns:
        dict: A dictionary containing employee info and clocked-in details if applicable.
    """
    try:
        employee = User.objects.get(id=employee_id)
        store = Store.objects.get(id=store_id)

        # Check employee is not inactive
        if not employee.is_active:
            raise err.InactiveUserError

        # Check store is not inactive
        if not store.is_active:
            raise err.InactiveStoreError

        # Form the basic info
        clocked_in = employee.is_clocked_in(store=store)
        full_name = f"{employee.first_name} {employee.last_name}"
        info = {
            "employee_id": employee_id,
            "store_id": store_id,
            "name": full_name,
            "clocked_in": clocked_in,
        }

        # If the employee is logged in, add the activity info
        if clocked_in:
            # Fetch the last active clock-in record for the employee
            activity = employee.get_last_active_activity_for_store(store=store)

            if not activity:
                raise err.NoActiveClockingRecordError

            # Add the clock-in time to the info
            info["login_time"] = activity.login_time
            info["login_timestamp"] = activity.login_timestamp

        return info

    except (
        User.DoesNotExist,
        Store.DoesNotExist,
        Activity.DoesNotExist,
        err.InactiveUserError,
        err.InactiveStoreError,
    ) as e:
        raise e  # Re-raise error to be caught in view
    except err.NoActiveClockingRecordError:
        # If the user has no active clocking record (their clock-in activity is missing)
        logger.warning(
            f"Failed to get clocked status for employee with ID {employee_id} due to a missing active clocking record (activity)."
        )
        raise
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to get clocked information of employee with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e  # Re-raise error to be caught in view


def get_users_recent_shifts(user_id: int, store_id: int, time_limit_days: int = 7):
    """
    Retrieve the recent shifts a user has completed or is currently working on
    within the last `time_limit_days` (default is 7, max is 15, min is 1).

    Returns:
        List[Dict]: A list of dictionaries with keys:
            - employee_id
            - store_id
            - store_code
            - login_time
            - logout_time (can be None)
            - deliveries (can be None)
            - is_public_holiday
            - is_modified
    """
    try:
        # Ensure limit is within expectations
        time_limit_days = min(
            max(int(time_limit_days), 1), 15
        )  # Max 15 days, min 1 day

        # Get objects
        user = User.objects.get(id=user_id)
        store = Store.objects.get(id=store_id)

        # Validate store and user states
        if not user.is_active:
            raise err.InactiveUserError
        elif not store.is_active:
            raise err.InactiveStoreError
        elif not user.is_associated_with_store(store=store):
            raise err.NotAssociatedWithStoreError

        # Time threshold
        time_threshold = now() - timedelta(days=time_limit_days)

        # Fetch relevant activity records
        shifts = (
            Activity.objects.select_related("store")
            .filter(employee=user, store=store, login_timestamp__gte=time_threshold)
            .order_by("-login_timestamp")
        )

        # Format results
        result = []
        for shift in shifts:
            result.append(
                {
                    "employee_id": shift.employee.id,
                    "store_id": shift.store.id,
                    "store_code": shift.store.code,
                    "login_time": localtime(shift.login_time),
                    "logout_time": (
                        localtime(shift.logout_time) if shift.logout_time else None
                    ),
                    "deliveries": shift.deliveries if shift.deliveries else None,
                    "is_public_holiday": shift.is_public_holiday,
                    "is_modified": util.is_activity_modified(shift),
                }
            )

        return result

    except (
        User.DoesNotExist,
        Store.DoesNotExist,
        err.InactiveUserError,
        err.NotAssociatedWithStoreError,
        err.InactiveStoreError,
    ) as e:
        # Re-raise common errors
        raise e
    except Exception as e:
        logger.error(
            f"Failed to get user ID {user_id}'s recent shift information up to a limit of {time_limit_days} days for the store ID {store_id}, resulting in the error: {str(e)}"
        )
        raise e


def get_account_summaries(
    store_id,
    offset,
    limit,
    start_date,
    end_date,
    ignore_no_hours,
    sort_field,
    filter_names,
    allow_inactive_store: bool = False,
):
    """
    Retrieve a paginated list of employee account summaries for a specific store.

    Args:
        store_id (int or str): The ID of the store to filter employees by.
        offset (int): The number of records to skip (for pagination).
        limit (int): The maximum number of records to return.
        start_date (str): The start of the date range in YYYY-MM-DD format.
        end_date (str): The end of the date range in YYYY-MM-DD format.
        ignore_no_hours (bool): Whether to exclude employees with zero hours worked.
        sort_field (str): Field to sort by. One of "name", "hours", "age", "deliveries".
        filter_names (List[str]): List of employee names to include (case-insensitive match).
        allow_inactive_store (bool): Whether to list summaries for an inactive store or return InactiveStoreError. Default False.

    Returns:
        Tuple[List[dict], int]: A list of summary dictionaries and the total count.
    """
    try:
        # Get store object and ensure its active
        store = Store.objects.get(id=int(store_id))

        if not store.is_active and not allow_inactive_store:
            raise err.InactiveStoreError

        # Convert date strings
        start_dt = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = make_aware(datetime.strptime(end_date, "%Y-%m-%d"))

        # All employees for the store
        employees_qs = User.objects.filter(
            store_access__store_id=store.id,
            is_hidden=False,
        ).distinct()

        # Apply name filters
        if filter_names:
            name_filter = Q()
            for name in filter_names:
                name_filter |= Q(first_name__icontains=name) | Q(
                    last_name__icontains=name
                )
            employees_qs = employees_qs.filter(name_filter)

        # Subqueries for total_mins and deliveries per employee
        activity_base = Activity.objects.filter(
            store_id=store.id,
            login_time__date__gte=start_dt,
            login_time__date__lte=end_dt,
            employee=OuterRef("pk"),
        )

        # Annotate employees with total mins and deliveries
        employees_qs = employees_qs.annotate(
            total_mins=Coalesce(
                Subquery(
                    activity_base.values("employee")
                    .annotate(total=Sum("shift_length_mins"))
                    .values("total")[:1]
                ),
                Value(0),
                output_field=IntegerField(),
            ),
            deliveries=Coalesce(
                Subquery(
                    activity_base.values("employee")
                    .annotate(total=Sum("deliveries"))
                    .values("total")[:1]
                ),
                Value(0),
                output_field=IntegerField(),
            ),
        )

        # Ignore users with 0 mins if flag is set
        if ignore_no_hours:
            employees_qs = employees_qs.filter(total_mins__gt=0)

        # Sorting
        sort_map = {
            "name": ("first_name", "last_name", "-total_mins"),
            "hours": ("-total_mins", "first_name", "last_name"),
            "age": ("birth_date", "first_name", "last_name"),
            "deliveries": ("-deliveries", "first_name", "last_name"),
        }
        employees_qs = employees_qs.order_by(
            *sort_map.get(sort_field, sort_map["name"])
        )

        # Total count before pagination
        total_summaries = employees_qs.count()

        # Apply pagination (now DB-level)
        paginated_employees = employees_qs[offset : offset + limit]

        summary_list = []
        for employee in paginated_employees:
            # Calculate age based on employee's DOB & current date (rounded to whole numbers)
            age = None
            if employee.birth_date:
                today = now().date()
                age = (
                    today.year
                    - employee.birth_date.year
                    - (
                        (today.month, today.day)
                        < (employee.birth_date.month, employee.birth_date.day)
                    )
                )

            # Get all activities for this employee within the date range
            emp_activities = Activity.objects.filter(
                store_id=store.id,
                employee_id=employee.id,
                login_time__date__gte=start_dt,
                login_time__date__lte=end_dt,
            )

            # Calculate hours for weekdays, weekends, and public holidays
            mins_weekday = mins_weekend = mins_public_holiday = 0

            # Calculate the hours based on the activity's day type
            for act in emp_activities:
                # Skip shift if its not finished
                if act.logout_time is None:
                    continue

                # ENSURE TIME IS IN LOCAL TIMEZONE FOR CORRECT DAY ALLOCATION!
                login_time = localtime(act.login_time)
                shift_length = act.shift_length_mins or 0

                # Determine the day of the week
                if act.is_public_holiday:
                    mins_public_holiday += shift_length

                day_of_week = login_time.weekday()  # Monday=0, Sunday=6

                # Weekday (Mon-Fri)
                if day_of_week < 5:
                    mins_weekday += shift_length
                # Weekend (Sat-Sun)
                else:
                    mins_weekend += shift_length

            summary_list.append(
                {
                    "employee_id": employee.id,
                    "name": f"{employee.first_name} {employee.last_name}",
                    "hours_total": round(employee.total_mins / 60, 2),
                    "hours_weekday": round(mins_weekday / 60, 2),
                    "hours_weekend": round(mins_weekend / 60, 2),
                    "hours_public_holiday": round(mins_public_holiday / 60, 2),
                    "deliveries": employee.deliveries,
                    "age": age,  # Integer age or None
                    "acc_resigned": not employee.is_associated_with_store(store=store),
                    "acc_active": employee.is_active,
                    "acc_manager": employee.is_manager,
                }
            )

        return summary_list, total_summaries

    except (
        Store.DoesNotExist,
        err.InactiveStoreError,
        ValueError,
    ) as e:
        # Re-raise common errors
        raise e
    except Exception as e:
        logger.error(
            f"Failed to get account summaries for store ID {store_id} for period ({start_date} -> {end_date}), resulting in the error: {str(e)}"
        )
        raise e


def check_new_shift_too_soon(
    employee: User,
    store: Store,
    limit_mins: int = START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
) -> bool:
    """
    Check if the user attempts to start a new shift within time limits of their last clock-out.

    Args:
        employee (User): The User object of the employee.
        store (Store): The Store object of the store the employee is getting checked against.
        limit_mins (int): The minimum interval in minutes required between clock-out and clock-in. (Default = 30m)

    Returns:
        bool: Returns True if the employee is trying to clock in too soon after their last clock-out, otherwise False.
    """
    try:
        # Get the last clock-out activity for the employee
        last_activity = Activity.objects.filter(
            employee=employee, store=store, logout_timestamp__isnull=False
        ).last()

        if not last_activity:
            # No previous clock-out record found, allow clock-in
            return False

        # Calculate the time difference between the last clock-out and the attempted clock-in
        time_diff = localtime(now()) - last_activity.logout_timestamp

        # Check if the time difference is less than the allowed time gap (x_minutes)
        if time_diff < timedelta(minutes=limit_mins):
            return True

        return False

    except Exception as e:
        raise Exception(
            f"Error checking if employee {employee.id} is attempting to start a shift too soon: {str(e)}"
        )


def check_clocking_out_too_soon(
    employee: User,
    store: Store,
    limit_mins: int = FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS,
) -> bool:
    """
    Check if the user attempts to clock out within time limits after their last clock-in.

    Args:
        employee (User): The User object of the employee.
        store (Store): The Store object of the store the employee is getting checked against.
        limit_mins (int): The minimum interval in minutes required between consecutive clock-in and clock-outs. (Default = 15m)
                          Ensure this value equals that of the rounding minutes for shift lengths.

    Returns:
        bool: Returns True if the employee is trying to clock out too soon, otherwise False.
    """
    try:
        # Get the last activity for the employee
        last_activity = (
            Activity.objects.filter(employee=employee, store=store)
            .order_by("-login_timestamp")
            .first()
        )  # Order by latest clock-in/out

        if not last_activity:
            # No previous clock-in or clock-out record found, allow clock-in
            return False

        # Calculate the time difference between the last clock-in/out and the attempted action
        time_diff = localtime(now()) - last_activity.login_timestamp

        # Check if the time difference is less than the allowed time gap (x_minutes)
        if time_diff < timedelta(minutes=limit_mins):
            return True

        return False

    except Exception as e:
        raise Exception(
            f"Error checking if employee {employee.id} is attempting to clock in/out too soon: {str(e)}"
        )


def is_active_account(employee_id: int) -> bool:
    """
    Check if an account with the id is active or inactive.

    Args:
        employee_id (int): The ID of the employee.

    Returns:
        bool: True if the account is active, False otherwise.
    """
    try:
        employee = User.objects.get(id=employee_id)

        # Check employee is not inactive
        if employee.is_active:
            return True

        return False

    except User.DoesNotExist as e:
        raise e  # Re-raise error to be caught in view
    except Exception as e:
        # Catch-all exception
        logger.error(
            f"Failed to check if account is active with ID {employee_id}, resulting in the error: {str(e)}"
        )
        raise e  # Re-raise error to be caught in view
