import logging
import api.exceptions as err
import api.utils as util

from collections import defaultdict, OrderedDict
from datetime import timedelta, datetime, date, time
from typing import Union, Dict, List, Dict, Tuple, Union, Any
from datetime import timedelta, datetime
from django.conf import settings
from django.db import transaction, IntegrityError
from django.db.models import Prefetch
from django.db.models.functions import Coalesce, Concat
from django.utils.timezone import now, localtime, make_aware
from django.db.models import (
    Sum,
    Q,
    OuterRef,
    Subquery,
    IntegerField,
    Value,
    F,
    ExpressionWrapper,
    DurationField,
)
from auth_app.models import User, Activity, Store, Role, Shift, ShiftException


logger = logging.getLogger("api")


def get_store_employee_names(
    store_id: Union[int, str, Store],
    only_active: bool = True,
    ignore_managers: bool = False,
    order: bool = True,
    order_by_first_name: bool = True,
    ignore_clocked_in: bool = False,
) -> List[dict]:
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
        List[dict]: A list of dicts like {"id": 1, "name": "Alice Smith"} preserving order.
    """
    # Ensure store is provided
    if isinstance(store_id, Store):
        store = store_id
    elif isinstance(store_id, (int, str)) and str(store_id).isdigit():
        store = Store.objects.get(pk=int(store_id))
    else:
        raise ValueError("Invalid store_id provided")

    # Get users associated with the store (ignore hidden users)
    users = User.objects.filter(
        store_access__store_id=store.id, is_hidden=False
    ).distinct()

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

    return [
        {"id": user.id, "name": f"{user.first_name} {user.last_name}"} for user in users
    ]


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
            employee = User.objects.get(pk=employee_id)

            # Get the store
            store = Store.objects.get(pk=store_id)
            time = localtime(now())  # Consistent timestamp

            # Check if user is inactive
            if not employee.is_active:
                raise err.InactiveUserError

            # Check if already clocked in
            elif employee.is_clocked_in(store=store):
                raise err.AlreadyClockedInError

            # Check user is associated with the store
            elif not employee.is_associated_with_store(store):
                raise err.NotAssociatedWithStoreError

            # Check the store is active
            elif not store.is_active:
                raise err.InactiveStoreError

            # Check if the employee is trying to clock in too soon after their last shift (default=30m)
            elif check_new_shift_too_soon(employee=employee, store=store):
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
    employee_id: int,
    deliveries: int,
    store_id: int,
    manual: bool = False,
    allow_inactive_edits: bool = False,
) -> Activity:
    """
    Handles clocking out an employee by ID.

    Args:
        employee_id (int): The employee's ID.
        deliveries (int): Number of deliveries made during the shift.
        store_id (int): The store's ID for which the clocking event will register.
        manual (bool) = False: Whether the clock out is requested via manual clocking page or not. For logging purposes only.
        allow_inactive_edits (bool) = False: Whether to check for err.InactiveUserError or not (USEFUL FOR AUTOMATED TASKS)

    Returns:
        Activity: An activity object containing the information about the clock out.
    """
    try:
        # Start a database transaction (rolls back on error)
        with transaction.atomic():
            # Fetch the employee (errors if they dont exist)
            employee = User.objects.get(pk=employee_id)

            # Get the store
            store = Store.objects.get(pk=store_id)

            # Check if user is inactive
            if not employee.is_active and not allow_inactive_edits:
                raise err.InactiveUserError

            # Check the store is active
            elif not store.is_active:
                raise err.InactiveStoreError

            # Check if not clocked in
            elif not employee.is_clocked_in(store=store):
                raise err.AlreadyClockedOutError

            # Check user is associated with the store
            elif not employee.is_associated_with_store(store):
                raise err.NotAssociatedWithStoreError

            # Check if the employee is trying to clock out too soon after their last shift (default=10m)
            elif check_clocking_out_too_soon(employee=employee, store=store):
                raise err.ClockingOutTooSoonError

            # Fetch the last active clock-in record
            activity = employee.get_last_active_activity_for_store(store=store)

            time = localtime(now())
            activity.logout_timestamp = time
            activity.logout_time = util.round_datetime_minute(
                time
            )  # Default to round to nearest 15m
            activity.deliveries = deliveries
            activity.shift_length_mins = util.calculate_shift_length_mins(
                start=activity.login_time, end=activity.logout_time
            )

            with transaction.atomic():
                activity.save()

                # Check for exceptions
                link_activity_to_shift(activity=activity)

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
        err.ClockingOutTooSoonError,
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
        employee = User.objects.get(pk=employee_id)
        store = Store.objects.get(pk=store_id)

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


def get_user_activities(user_id: int, store_id: int, week: str = None):
    """
    Retrieve the week of actitivies the `user_id` is related (for the `store_id`) to starting on the monday of `week`.
    If `week` is not given, use current day.

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
        # Ensure a week is set and that its monday
        if week:
            try:
                raw_date = date.fromisoformat(week)
            except ValueError:
                raise Exception("Week provided is not in ISO format.")
        else:
            raw_date = localtime(now()).date()

        # Roll back to Monday if not provided
        week_start = raw_date - timedelta(days=raw_date.weekday())
        week_end = week_start + timedelta(days=6)

        # Convert week boundaries to datetime
        start_datetime = make_aware(
            datetime.combine(week_start, time.min)
        )  # Monday 00:00
        end_datetime = make_aware(
            datetime.combine(week_end, time.max)
        )  # Sunday 23:59:59.999999

        # Get objects
        user = User.objects.get(pk=user_id)
        store = Store.objects.get(pk=store_id)

        # Validate store and user states
        if not user.is_active:
            raise err.InactiveUserError
        elif not store.is_active:
            raise err.InactiveStoreError
        elif not user.is_associated_with_store(store=store):
            raise err.NotAssociatedWithStoreError

        # Fetch relevant activity records
        activities = (
            Activity.objects.select_related("store")
            .filter(
                employee_id=user.id,
                store_id=store.id,
                login_time__range=(start_datetime, end_datetime),
            )
            .order_by("-login_time")
        )

        # Format results
        results = defaultdict(list)
        for act in activities:
            login_dt = localtime(act.login_time)
            date_str = login_dt.date().isoformat()
            results[date_str].append(
                {
                    "employee_id": act.employee.id,
                    "store_id": act.store.id,
                    "store_code": act.store.code,
                    "login_time_str": login_dt.strftime("%H:%M"),
                    "logout_time_str": (
                        localtime(act.logout_time).strftime("%H:%M")
                        if act.logout_time
                        else None
                    ),
                    "deliveries": act.deliveries if act.deliveries else None,
                    "is_public_holiday": act.is_public_holiday,
                    "is_modified": util.is_activity_modified(act),
                }
            )

        # This DOES NOT guarantee ORDER -> Use OrderedDict(sorted(results.items(), reverse=True)) to get order
        return results

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
            f"Failed to get user ID {user_id}'s recent shift information for week {week} for the store ID {store_id}, resulting in the error: {str(e)}"
        )
        raise e


def get_all_employee_details(
    store_id: Union[str, int],
    offset: int,
    limit: int,
    sort_field: str,
    filter_names: List[str],
    hide_deactivated: bool = False,
    allow_inactive_store: bool = False,
) -> Tuple[List[dict], int]:
    """
    Returns a paginated list of employee details for a store.

    Args:
        store_id (int): Store ID.
        offset (int): Pagination offset.
        limit (int): Pagination limit.
        sort_field (str): "name", "age", or "acc_age".
        filter_names (List[str]): List of names (case-insensitive) to include.
        hide_deactivated (bool): If True, hide deactivated employees. Default False.
        allow_inactive_store (bool): Whether to list shifts for an inactive store or return InactiveStoreError. Default False.

    Returns:
        Tuple[List[dict], int]: (results, total count)
    """
    # Get and validate store
    store = Store.objects.get(pk=int(store_id))

    if not store.is_active and not allow_inactive_store:
        raise err.InactiveStoreError

    # Get all users for the store
    qs = User.objects.filter(
        store_access__store_id=store_id, is_hidden=False
    ).distinct()

    # Hide deactivated if requested
    if hide_deactivated:
        qs = qs.filter(is_active=True)

    # Name filtering
    if filter_names:
        # Annotate full_name
        qs = qs.annotate(full_name=Concat("first_name", Value(" "), "last_name"))

        name_filters = Q()
        for name in filter_names:
            name_filters |= Q(full_name__icontains=name)
        qs = qs.filter(name_filters)

    # Sorting
    sort_map = {
        "name": ("first_name", "last_name", "birth_date"),
        "age": ("birth_date", "first_name", "last_name"),
        "acc_age": ("created_at", "first_name", "last_name"),
    }
    qs = qs.order_by(*sort_map.get(sort_field, sort_map["name"]))

    # Total count before pagination
    total = qs.count()

    # Paginate on DB level
    qs = qs[offset : offset + limit]

    # Construct result
    results = []
    for emp in qs:
        results.append(
            {
                "id": emp.id,
                "first_name": emp.first_name,
                "last_name": emp.last_name,
                "email": emp.email,
                "phone_number": emp.phone_number or None,
                "dob": emp.birth_date.strftime("%d/%m/%Y") if emp.birth_date else None,
                "pin": emp.pin,
                "is_active": emp.is_active,
                "is_manager": emp.is_manager,
            }
        )

    return results, total


def get_all_shifts(
    store_id: Union[str, int],
    offset: int,
    limit: int,
    start_date: str,
    end_date: str,
    sort_field: str,
    filter_names: List[str],
    only_unfinished: bool = False,
    only_public_hol: bool = False,
    hide_deactivated: bool = False,
    hide_resigned: bool = False,
    allow_inactive_store: bool = False,
) -> Tuple[List[dict], int]:
    """
    Retrieves paginated shift activity records for a store.

    Args:
        store_id (int): The store ID.
        offset (int): Pagination offset.
        limit (int): Pagination limit.
        start_date (str): Filter start date (YYYY-MM-DD).
        end_date (str): Filter end date (YYYY-MM-DD).
        sort_field (str): One of "time", "name", "length", "delivery".
        filter_names (List[str]): Case-insensitive names to include.
        only_unfinished (bool): Filter for unfinished shifts only (no clock out time). Default False.
        only_public_hol (bool): Filter for public holidays only. Default False.
        hide_deactivated (bool): Exclude deactivated employees. Default False.
        hide_resigned (bool): Exclude resigned employees. Default False.
        allow_inactive_store (bool): Whether to list shifts for an inactive store or return InactiveStoreError. Default False.

    Returns:
        Tuple[List[dict], int]: List of results, and total count.
    """
    # Get store object and ensure its active
    store = Store.objects.get(pk=int(store_id))

    if not store.is_active and not allow_inactive_store:
        raise err.InactiveStoreError

    # Initial queryset
    qs = Activity.objects.select_related("employee").filter(
        store_id=store_id, employee__is_hidden=False
    )

    # Filter dates
    if start_date:
        qs = qs.filter(login_time__date__gte=start_date)
    if end_date:
        qs = qs.filter(login_time__date__lte=end_date)

    # Filter by names
    if filter_names:
        # Annotate full_name
        qs = qs.annotate(
            full_name=Concat("employee__first_name", Value(" "), "employee__last_name")
        )

        name_filters = Q()
        for name in filter_names:
            name_filters |= Q(full_name__icontains=name)
        qs = qs.filter(name_filters)

    # Apply extra filters
    if only_unfinished:
        qs = qs.filter(logout_time__isnull=True)
    if only_public_hol:
        qs = qs.filter(is_public_holiday=True)
    if hide_deactivated:
        qs = qs.filter(employee__is_active=True)
    if hide_resigned:
        qs = qs.filter(employee__store_access__store_id=store_id)

    # Sorting
    sort_map = {
        "time": ("-login_timestamp", "employee__first_name", "employee__last_name"),
        "name": ("employee__first_name", "employee__last_name", "-login_timestamp"),
        "length": (
            "-shift_length_mins",
            "-login_timestamp",
            "employee__first_name",
            "employee__last_name",
        ),
        "delivery": (
            "-deliveries",
            "-login_timestamp",
            "employee__first_name",
            "employee__last_name",
        ),
    }
    qs = qs.order_by(*sort_map.get(sort_field, sort_map["time"]))

    # Total count before pagination
    total = qs.count()

    # Apply pagination (now DB-level)
    qs = qs[offset : offset + limit]

    results = []
    for act in qs:
        hours_decimal = (act.shift_length_mins / 60.0) if act.shift_length_mins else 0.0
        results.append(
            {
                "id": act.id,
                "emp_first_name": act.employee.first_name,
                "emp_last_name": act.employee.last_name,
                "emp_active": act.employee.is_active,
                "emp_resigned": not act.employee.is_associated_with_store(
                    store=store_id
                ),
                "login_time": (
                    localtime(act.login_time).strftime("%H:%M")
                    if act.login_time
                    else None
                ),
                "logout_time": (
                    localtime(act.logout_time).strftime("%H:%M")
                    if act.logout_time
                    else None
                ),
                "is_public_holiday": act.is_public_holiday,
                "login_timestamp": (
                    localtime(act.login_timestamp).strftime("%d/%m/%Y %H:%M")
                    if act.login_timestamp
                    else None
                ),
                "logout_timestamp": (
                    localtime(act.logout_timestamp).strftime("%d/%m/%Y %H:%M")
                    if act.logout_timestamp
                    else None
                ),
                "deliveries": act.deliveries,
                "hours_worked": f"{hours_decimal:.2f}",
            }
        )

    return results, total


def get_account_summaries(
    store_id: Union[str, int],
    offset: int,
    limit: int,
    start_date: str,
    end_date: str,
    sort_field: str,
    filter_names: List[str],
    ignore_no_hours: bool = False,
    allow_inactive_store: bool = False,
) -> Tuple[List[dict], int]:
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
        filter_names (List[str]): List of employee names to include (case-insensitive match). Default False.
        allow_inactive_store (bool): Whether to list summaries for an inactive store or return InactiveStoreError. Default False.

    Returns:
        Tuple[List[dict], int]: A list of summary dictionaries and the total count.
    """
    try:
        # Get store object and ensure its active
        store = Store.objects.get(pk=int(store_id))

        # Convert date strings
        start_dt = make_aware(datetime.strptime(start_date, "%Y-%m-%d"))
        end_dt = make_aware(datetime.strptime(end_date, "%Y-%m-%d"))

        if not store.is_active and not allow_inactive_store:
            raise err.InactiveStoreError

        # Check if there are any exceptions for the store in the period
        elif util.check_store_exceptions_in_period(
            store_id=store.id, start_dt=start_dt, end_dt=end_dt
        ):
            raise err.ShiftExceptionExistsError

        # All employees for the store OR who have worked at the store within the period (if resigned)
        employees_qs = User.objects.filter(
            Q(store_access__store_id=store.id)
            | Q(
                activities__store_id=store.id,
                activities__login_time__date__gte=start_dt.date(),
                activities__login_time__date__lte=end_dt.date(),
            ),
            is_hidden=False,
        ).distinct()

        # Annotate full_name for better filtering
        employees_qs = employees_qs.annotate(
            full_name=Concat("first_name", Value(" "), "last_name")
        )

        # Apply name filters
        if filter_names:
            name_filter = Q()
            for name in filter_names:
                name_filter |= Q(full_name__icontains=name)
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
                day_of_week = login_time.weekday()  # Monday=0, Sunday=6

                # Public Holiday (MUTUALLY EXCLUSIVE TO REGULAR WEEK/WEEKEND DAYS)
                if act.is_public_holiday:
                    mins_public_holiday += shift_length
                # Weekday (Mon-Fri)
                elif day_of_week < 5:
                    mins_weekday += shift_length
                # Weekend (Sat-Sun)
                else:
                    mins_weekend += shift_length

            summary_list.append(
                {
                    "employee_id": employee.id,
                    "name": employee.full_name,
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
    limit_mins: int = settings.START_NEW_SHIFT_TIME_DELTA_THRESHOLD_MINS,
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
        last_activity = (
            Activity.objects.filter(
                employee_id=employee.id, store=store, logout_timestamp__isnull=False
            )
            .order_by("-logout_timestamp")
            .first()
        )

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
    limit_mins: int = settings.FINISH_SHIFT_TIME_DELTA_THRESHOLD_MINS,
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
        last_activity = employee.get_last_active_activity_for_store(store=store.id)

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
        employee = User.objects.get(pk=employee_id)

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


################################ SCHEDULING ################################


def get_all_store_schedules_legacy(
    store: Store,
    week: str,
    include_deleted: bool = False,
    hide_deactivated: bool = False,
    hide_resigned: bool = False,
    sort_field: str = "time",
    filter_names: List[str] = None,
    filter_roles: List[str] = None,
) -> Dict[str, Any]:
    """
    Get all of a store's schedule information for a given week.

    Args:
        store (Store obj): The store for which the schedule will be fetched
        week (str): The date of the start of the week for which the schedule will be obtained (YYYY-MM-DD). The start of the week is Monday.
        include_deleted (bool): If True, include Shifts with is_deleted=True
        hide_deactivated (bool): Exclude deactivated employees. Default False.
        hide_resigned (bool): Exclude resigned employees. Default False.
        sort_field (str): One of "time", "name", "length", "role_name".
        filter_names (List[str]): Case-insensitive names to include.
        filter_roles (List[str]): Case-insensitive roles to include.

    Returns:
        (Dict[str, Any]): A dictionary containing:
            - 'schedule': Dict[date, List[Dict]] mapping dates to lists of shifts,
            - 'week_start': date of the Monday starting the week,
            - 'prev_week': date of the previous week's Monday,
            - 'next_week': date of the next week's Monday.
    """
    if store is None or week is None:
        raise Exception("Store object or week is None.")

    try:
        week_start = date.fromisoformat(week)
        week_start = util.get_week_start(week_start)  # Ensure its a monday
    except ValueError:
        raise Exception("Week provided is not in ISO format.")

    week_end = week_start + timedelta(days=6)

    # Fetch shifts for the store during this week
    shifts = Shift.objects.filter(
        store=store, date__range=(week_start, week_end), employee__is_hidden=False
    ).select_related("employee", "role", "shift_shiftexception")

    # Optional filters
    if hide_deactivated:
        shifts = shifts.filter(employee__is_active=True)
    if hide_resigned:
        shifts = shifts.filter(employee__store_access__store_id=store.id)
    if not include_deleted:
        shifts = shifts.exclude(is_deleted=True)

    # Filter by employee name (case-insensitive)
    if filter_names:
        # Annotate full_name
        shifts = shifts.annotate(
            full_name=Concat("employee__first_name", Value(" "), "employee__last_name")
        )

        name_query = Q()
        for name in filter_names:
            name_query |= Q(full_name__icontains=name)
        shifts = shifts.filter(name_query)

    # Filter by role name (case-insensitive)
    if filter_roles:
        role_query = Q()
        for role in filter_roles:
            role_query |= Q(role__name__icontains=role)
        shifts = shifts.filter(role_query)

    if sort_field == "length":
        shifts = shifts.annotate(
            shift_length=ExpressionWrapper(
                F("end_time") - F("start_time"), output_field=DurationField()
            )
        )

    # Sorting logic
    sort_map = {
        "time": ("date", "start_time", "employee__first_name", "employee__last_name"),
        "name": ("date", "employee__first_name", "employee__last_name", "start_time"),
        "length": (
            "-shift_length",
            "date",
            "start_time",
            "employee__first_name",
            "employee__last_name",
        ),
        "role_name": (
            "date",
            "role__name",
            "start_time",
            "employee__first_name",
            "employee__last_name",
        ),
    }
    shifts = shifts.order_by(*sort_map.get(sort_field, sort_map["time"]))

    # Group shifts by date using a defaultdict
    grouped_shifts = defaultdict(list)

    for shift in shifts:
        grouped_shifts[shift.date].append(
            {
                "id": shift.id,
                "employee_name": f"{shift.employee.first_name} {shift.employee.last_name}",
                "start_time": shift.start_time.strftime("%H:%M"),
                "end_time": shift.end_time.strftime("%H:%M"),
                "role_name": shift.role.name if shift.role else None,
                "role_colour": shift.role.colour_hex if shift.role else None,
                "is_unscheduled": shift.is_unscheduled,
                "comment": shift.comment,
                "has_exception": hasattr(shift, "shift_shiftexception"),
            }
        )
        if shift.is_deleted:
            grouped_shifts[shift.date].append({"is_deleted": True})

    # Ensure all days are present even if no shifts exist
    schedule_data = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        # Ensure day is filled AND convert date key to a str
        schedule_data[day.isoformat()] = grouped_shifts.get(day, [])

    return {
        "schedule": schedule_data,
        "week_start": week_start,
        "prev_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
    }


def get_all_store_schedules(
    store: Store,
    week: str,
    offset: int,
    limit: int,
    include_deleted: bool = False,
    hide_deactivated: bool = False,
    hide_resigned: bool = False,
    sort_field: str = "name",
    filter_names: List[str] = None,
    filter_roles: List[str] = None,
) -> Dict[str, Any]:
    """
    Get all of a store's schedule information for a given week.

    Args:
        store (Store obj): The store for which the schedule will be fetched
        week (str): The date of the start of the week for which the schedule will be obtained (YYYY-MM-DD). The start of the week is Monday.
        offset (int): Pagination offset.
        limit (int): Pagination limit.
        include_deleted (bool): If True, include Shifts with is_deleted=True
        hide_deactivated (bool): Exclude deactivated employees. Default False.
        hide_resigned (bool): Exclude resigned employees. Default False.
        sort_field (str): One of "name", "age", "acc_age".
        filter_names (List[str]): Case-insensitive names to include.
        filter_roles (List[str]): Case-insensitive roles to include.

    Returns:
        {
            'schedule': {
                'Employee Name': {'id': employee.id, 'roster': {'1-1-2025': [shifts], ... }},
                ...
            },
            'week_start': ...,
            'prev_week': ...,
            'next_week': ...
        }
    """
    if store is None or week is None:
        raise Exception("Store object or week is None.")

    try:
        week_start = date.fromisoformat(week)
        week_start = util.get_week_start(week_start)  # Ensure Monday
    except ValueError:
        raise Exception("Week provided is not in ISO format.")

    week_end = week_start + timedelta(days=6)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]

    # Employees currently in the store (via StoreAccess)
    current_employees_qs = store.get_store_employees(include_hidden=False)

    # Employees with shifts in the target week (TO ENSURE RESIGNED EMPLOYEES ARE OBTAINED)
    shift_employee_ids = (
        Shift.objects.filter(
            store=store,
            date__range=(week_start, week_end),
        )
        .values_list("employee_id", flat=True)
        .distinct()
    )

    # Combine both querysets using union of Q objects
    employee_qs = User.objects.filter(
        Q(id__in=current_employees_qs.values_list("id", flat=True))
        | Q(id__in=shift_employee_ids)
    ).prefetch_related("store_access")

    # Exclude hidden users
    employee_qs = employee_qs.filter(is_hidden=False)

    # Optional filters
    if hide_deactivated:
        employee_qs = employee_qs.filter(is_active=True)
    if hide_resigned:
        employee_qs = employee_qs.filter(store_access__store_id=store.id)

    # Filter by name if specified
    if filter_names:
        # Annotate full_name
        employee_qs = employee_qs.annotate(
            full_name=Concat("first_name", Value(" "), "last_name")
        )
        name_query = Q()
        for name in filter_names:
            name_query |= Q(full_name__icontains=name)
        employee_qs = employee_qs.filter(name_query)

    # Add prefetch for shifts within appropriate range
    filtered_shifts = (
        Shift.objects.filter(
            store=store,
            date__range=(week_start, week_end),
        )
        .select_related("role", "shift_shiftexception")
        .order_by("date", "start_time")
    )

    # Filter out deleted shifts if requested
    if not include_deleted:
        filtered_shifts = filtered_shifts.filter(is_deleted=False)

    # Add role filter on shifts if given
    if filter_roles:
        role_query = Q()
        for role in filter_roles:
            role_query |= Q(role__name__icontains=role)
        filtered_shifts = filtered_shifts.filter(role_query)

    employee_qs = employee_qs.prefetch_related(
        Prefetch("shifts", queryset=filtered_shifts, to_attr="filtered_shifts")
    )

    sort_map = {
        "name": ("first_name", "last_name", "birth_date"),
        "age": ("birth_date", "first_name", "last_name"),
        "acc_age": ("created_at", "first_name", "last_name"),
    }
    employee_qs = employee_qs.order_by(*sort_map.get(sort_field, sort_map["name"]))

    # Apply pagination
    total = employee_qs.count()
    employees = employee_qs[offset : offset + limit]

    schedule = OrderedDict()

    for emp in employees:
        # Add each day of week to dict (in order)
        shifts = {day.isoformat(): [] for day in week_dates}

        for shift in getattr(emp, "filtered_shifts", []):
            day_key = shift.date.isoformat()
            shifts[day_key].append(
                {
                    "id": shift.id,
                    "start_time": shift.start_time.strftime("%H:%M"),
                    "end_time": shift.end_time.strftime("%H:%M"),
                    "role_name": shift.role.name if shift.role else None,
                    "role_colour": shift.role.colour_hex if shift.role else None,
                    "is_unscheduled": shift.is_unscheduled,
                    "comment": shift.comment,
                    "has_exception": hasattr(shift, "shift_shiftexception"),
                }
            )

        # Add to schedule dict
        schedule[f"{emp.first_name} {emp.last_name}"] = {
            "id": emp.id,
            "roster": shifts,
        }

    return {
        "schedule": schedule,
        "week_start": week_start,
        "prev_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
        "total": total,
        "offset": offset,
    }


def get_user_store_schedules(
    store: Store,
    user: User,
    week: str,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    """
    Get a user's store schedule for a month starting from a week ago from today.

    Args:
        store (Store obj): The store for which the schedule will be fetched.
        user (User obj): The user for which the specfic schedules will be fetched.
        week (str): The date of the start of the week for which the schedule will be obtained (YYYY-MM-DD). The start of the week is Monday.
        include_deleted (bool): If True, include Shifts with is_deleted=True

    Returns:
        (Dict[str, Any]): A dictionary containing:
            - 'schedule': Dict[date_str, List[Dict]] mapping only scheduled dates to lists of shifts.
    """
    if store is None or user is None:
        raise Exception("Store or User object is None.")

    try:
        week_start = date.fromisoformat(week)
        week_start = util.get_week_start(week_start)  # Ensure its a monday
    except ValueError:
        raise Exception("Week provided is not in ISO format.")

    week_end = week_start + timedelta(days=6)

    # Fetch shifts for the store during this week
    shifts = Shift.objects.filter(
        employee_id=user.id, store_id=store.id, date__range=(week_start, week_end)
    ).select_related("role")

    if not include_deleted:
        shifts = shifts.exclude(is_deleted=True)

    # Order the shifts
    shifts = shifts.order_by("store", "date", "start_time")

    # Group shifts by date using a defaultdict
    grouped_shifts = defaultdict(list)

    for shift in shifts:
        key = shift.date.isoformat()
        grouped_shifts[key].append(
            {
                "id": shift.id,
                "start_time": shift.start_time.strftime("%H:%M"),
                "end_time": shift.end_time.strftime("%H:%M"),
                "role_name": shift.role.name if shift.role else None,
                "role_colour": shift.role.colour_hex if shift.role else None,
                "is_unscheduled": shift.is_unscheduled,
            }
        )
        if include_deleted and shift.is_deleted:
            grouped_shifts[key].append({"is_deleted": True})

    # Ensure all days are present even if no shifts exist
    schedule_data = {}
    for i in range(7):
        day = week_start + timedelta(days=i)
        schedule_data[day.isoformat()] = grouped_shifts.get(day.isoformat(), [])

    return {
        "schedule": schedule_data,
        "week_start": week_start,
        "prev_week": week_start - timedelta(days=7),
        "next_week": week_start + timedelta(days=7),
    }


def get_store_exceptions(
    store: Union[Store, int, str], get_unapproved: bool, offset: int, limit: int
) -> Tuple[List[ShiftException], int]:
    """
    Returns approved and unapproved shift exceptions for a given store.
    If getting approved store exceptions, only get ones made less than a month ago.

    Args:
        store (Union[Store, int, str]): Store object or store ID to filter exceptions by.
        get_unapproved (bool): Whether to get APPROVED or UNAPPROVED exceptions.
        offset (int): Pagination offset.
        limit (int): Maximum number of exceptions to return per category.

    Returns:
        Tuple[List[ShiftException], int]: A list containing the exceptions of the selected TYPE and TOTAL items.

    Raises:
        Store.DoesNotExist: If a store ID is provided but no matching Store is found.
    """
    # Resolve store if ID or str is provided
    if not isinstance(store, Store):
        try:
            store = Store.objects.get(pk=int(store))
        except (ValueError, Store.DoesNotExist):
            raise Store.DoesNotExist

    # Base queryset scoped to the given store via shift or activity
    qs = ShiftException.objects.filter(
        Q(shift__store=store) | Q(activity__store=store)
    ).select_related(
        "shift",
        "shift__store",
        "shift__employee",
        "shift__role",
        "activity",
        "activity__store",
        "activity__employee",
    )

    # Filter by approval status
    qs = qs.filter(is_approved=not get_unapproved)

    # If getting approved exceptions -> Only get those made less than a month ago
    if not get_unapproved:
        cutoff = localtime(now()).date() - timedelta(days=30)
        qs = qs.filter(created_at__gte=cutoff)

    # Get total count before slicing
    total = qs.count()

    # Apply pagination
    objects = qs.order_by("-created_at")[offset : offset + limit]

    results = []
    for obj in objects:
        emp = obj.get_employee()
        info = {
            "id": obj.id,
            "reason": obj.get_reason_display(),
            "created_at": localtime(obj.created_at),
            "updated_at": localtime(obj.updated_at),
            "date": obj.get_date(),
            "store_code": obj.get_store().code,
            "emp_name": f"{emp.first_name} {emp.last_name}",
        }
        if obj.shift:
            start_dt = datetime.combine(info["date"], obj.shift.start_time)
            end_dt = datetime.combine(info["date"], obj.shift.end_time)
            shift_length_hr = round(abs((end_dt - start_dt).total_seconds()) / 3600, 2)
            info.update(
                {
                    "shift_start": obj.shift.start_time,
                    "shift_end": obj.shift.end_time,
                    "shift_length_hr": shift_length_hr,
                    "shift_role_name": obj.shift.role.name if obj.shift.role else None,
                    "shift_role_id": obj.shift.role.id if obj.shift.role else None,
                    "shift_comment": obj.shift.comment if obj.shift.comment else "",
                }
            )

        if obj.activity:
            info.update(
                {
                    "act_start": localtime(obj.activity.login_time).strftime("%H:%M"),
                    "act_start_timestamp": localtime(
                        obj.activity.login_timestamp
                    ).strftime("%H:%M:%S"),
                    "act_end": (
                        localtime(obj.activity.logout_time).strftime("%H:%M")
                        if obj.activity.logout_time
                        else None
                    ),
                    "act_end_timestamp": (
                        localtime(obj.activity.logout_timestamp).strftime("%H:%M:%S")
                        if obj.activity.logout_timestamp
                        else None
                    ),
                    "act_length_hr": round(obj.activity.shift_length_mins / 60, 2),
                    "act_pub_hol": obj.activity.is_public_holiday,
                }
            )

        results.append(info)

    return results, total


def approve_exception(
    exception: Union[ShiftException, int, str],
    override_role_id: Union[str, int, None] = None,
    comment: Union[str, None] = None,
) -> None:
    """
    Approves an exception and updates both the linked shift and/or activity when required.
    ENSURE THE ROLE ID IS ACCESSIBLE BY THE RELATED STORE BEFORE CALLING THIS FUNCTION, THIS IS NOT CHECKED IN THIS CONTROLLER.

    Args:
        exception (Union[ShiftException, int, str]): The exception to approve.
        override_role_id (Union[str, int, None]): The ID of the role to override the connected shift with. BE WARNED: THIS IS NOT CHECKED IF A STORE HAS ACCESS TO THE ROLE, THIS IS DONE IN THE API VIEW ITSELF.
        comment (Union[str, None]): The comment to replace on the shift with (if its different). COMMENT MUST BE FILTERED AND CHECKED BEFORE THIS FUNCTION.

    Raises:
        ShiftException.DoesNotExist: If the Exception does not exist.
        Role.DoesNotExist: If the override role id does not exist.
        err.IncompleteActivityError: If the activity the exception is linked to is incomplete.
        err.ShiftExceptionAlreadyApprovedError: If the exception is already approved.
        Exception: If there is a problem with the exception object itself.
    """
    # Resolve the exception object if not given
    if not isinstance(exception, ShiftException):
        try:
            exception = ShiftException.objects.select_related("shift", "activity").get(
                pk=int(exception)
            )
        except (ValueError, ShiftException.DoesNotExist):
            raise ShiftException.DoesNotExist

    # If the exception is already approved -> Cant re-approve
    if exception.is_approved:
        raise err.ShiftExceptionAlreadyApprovedError

    # If given role -> fetch Role object
    elif override_role_id:
        try:
            role = Role.objects.get(pk=int(override_role_id))
        except (Value, Role.DoesNotExist):
            raise Role.DoesNotExist

    with transaction.atomic():
        # Get middleman objects
        shift = exception.shift
        activity = exception.activity

        # When both are linked -> use activity as Source Of Truth (ShiftException.Reason.INCORRECTLY_CLOCKED)
        if shift and activity:
            if not activity.login_time or not activity.logout_time:
                raise err.IncompleteActivityError

            elif shift.date != localtime(activity.login_time).date():
                raise Exception(
                    "Exception linked ACTIVITY and SHIFT are on DIFFERENT DATES. This should not be possible."
                )

            updated = False
            new_start_time = localtime(activity.login_time).time()
            new_end_time = localtime(activity.logout_time).time()

            # Ensure shift times match activity times
            if shift.start_time != new_start_time:
                # Check if update would violate uniqueness due to soft-deleted shift
                conflicting = (
                    Shift.objects.filter(
                        employee_id=shift.employee_id,
                        store_id=shift.store_id,
                        date=localtime(activity.login_time).date(),
                        start_time=new_start_time,
                        is_deleted=True,
                    )
                    .exclude(pk=shift.pk)
                    .first()
                )
                if conflicting:
                    logger.debug(
                        f"[DELETE: SHIFT (ID: {conflicting.id})] Deleted due to it interfering with an exception approval (it was already soft-deleted)"
                    )
                    conflicting.delete()

                # Update the shift
                shift.start_time = new_start_time
                updated = True

            if shift.end_time != new_end_time:
                shift.end_time = new_end_time
                updated = True
            if override_role_id and shift.role != role:
                shift.role = role  # Only update role if its given AND it changes
                updated = True
            if comment and shift.comment != comment:
                shift.comment = comment
                updated = True
            if exception.reason == ShiftException.Reason.NO_SHIFT:
                shift.is_unscheduled = True
                updated = True

            if updated:
                shift.save()

        # When user clocked in without being rostered -> create shift (ShiftException.Reason.NO_SHIFT)
        elif not shift and activity:
            if not activity.login_time or not activity.logout_time:
                raise err.IncompleteActivityError

            shift_data = {
                "employee": activity.employee,
                "store": activity.store,
                "date": localtime(activity.login_time).date(),
                "start_time": localtime(activity.login_time).time(),
                "end_time": localtime(activity.logout_time).time(),
            }

            # IF IT FAILS TO CREATE SHIFT DUE TO ONE ALREADY EXISTING BUT WITH (is_deleted=True), DELETE IT AND TRY AGAIN
            try:
                new_shift = Shift.objects.create(**shift_data)
            except IntegrityError:
                existing = Shift.objects.filter(
                    employee_id=shift_data["employee"].id,
                    store_id=shift_data["store"].id,
                    date=shift_data["date"],
                    start_time=shift_data["start_time"],
                    is_deleted=True,
                ).first()
                if existing:
                    logger.debug(
                        f"[DELETE: SHIFT (ID: {existing.id})] Deleted due to it interfering with an exception approval (it was already soft-deleted)"
                    )
                    existing.delete()
                    # Retry creating shift
                    new_shift = Shift.objects.create(**shift_data)
                else:
                    raise  # re-raise the original IntegrityError

            # Update role if given
            updated = False
            if override_role_id:
                new_shift.role = role
                updated = True
            if exception.reason == ShiftException.Reason.NO_SHIFT:
                new_shift.is_unscheduled = True
                updated = True
            if updated:
                new_shift.save()

            # Update exception to link to newly created shift
            exception.shift = new_shift

        # When user was rostered by didnt clock in -> "delete" the shift (visually) (ShiftException.Reason.MISSED_SHIFT)
        elif shift and not activity:
            shift.is_deleted = True
            shift.save()

        # Exception int properly linked
        else:
            raise Exception(
                "ShiftException is not properly linked between a shift and an activity."
            )

        # Save approval status
        exception.is_approved = True
        exception.save()


def link_activity_to_shift(
    activity: Union[Activity, int, str, None] = None,
    shift: Union[Shift, int, str, None] = None,
) -> Tuple[Union[ShiftException.Reason, None], bool]:
    """
    Check for a perfect link between an activity (actual shift) and a shift (the roster for the shift).
    If no perfect link exists (i.e. either doesnt exist, or slightly wrong) then create a ShiftException. Either option MUST be provided.

    Args:
        activity (Activity, int, str): The activity object or ID to start the link from.
        shift (shift, int, str): The shift object or ID to start the link from.

    Returns:
        Tuple[Union[ShiftException.Reason, None], bool]: The exception reason if one is created OR None if a perfect link exists AND if an exception is generated or not (alr exists).

    Raises:
        SyntaxError: If neither activity or shift is provided.
        Activity.DoesNotExist: If the function cannot find the Activity from a provided ID.
        Shift.DoesNotExist: If the function cannot find the Shift from a provided ID.
        err.IncompleteActivityError: If the activity linking OR linked to is not complete.
    """
    # Resolve activity and shift if ID or str is provided
    if activity and not isinstance(activity, Activity):
        try:
            activity = Activity.objects.get(pk=int(activity))
        except (ValueError, Activity.DoesNotExist):
            raise Activity.DoesNotExist
    elif shift and not isinstance(shift, Shift):
        try:
            shift = Shift.objects.get(pk=int(shift))
        except (ValueError, Shift.DoesNotExist):
            raise Shift.DoesNotExist

    # Require a transaction due to multiple concurrent saves in certain cases
    with transaction.atomic():
        if activity:
            if not activity.logout_time:
                raise err.IncompleteActivityError

            # Check for existing exception (use getattr as it throws errors if it doesnt exist)
            existing_exception = getattr(activity, "activity_shiftexception", None)

            # Get shifts for same user/store/day (DONT FILTER DB LEVEL, as realistically at most 2 shifts per user per day per store -> more work to filter on DB level)
            shifts = Shift.objects.filter(
                store_id=activity.store_id,
                employee_id=activity.employee_id,
                date=activity.login_time.date(),
                is_deleted=False,
            ).prefetch_related("shift_shiftexception")

            # Preload other activities ONCE -> Used to check if shift is valid (doesnt already have a perfect match) -> AS PERFECT MATCHES ARENT ALWAYS LINKED TO AN EXCEPTION
            other_activities = (
                Activity.objects.filter(
                    store_id=activity.store_id,
                    employee_id=activity.employee_id,
                    login_time__date=activity.login_time.date(),
                )
                .exclude(pk=activity.id)
                .prefetch_related("activity_shiftexception")
            )

            # Filter shifts that do NOT have an full exception (have both linked shift and activity) — BUT allow the one linked to this activity's exception
            valid_shifts = [
                s
                for s in shifts
                if util.is_valid_linking_shift_candidate(
                    possible_shift=s,
                    existing_exception=existing_exception,
                    other_activities=other_activities,
                )
            ]

            # If no shifts left, treat as NO_SHIFT
            if not valid_shifts:
                created = create_shiftexception_link(
                    activity=activity, reason=ShiftException.Reason.NO_SHIFT
                )
                return ShiftException.Reason.NO_SHIFT, created

            # Pick the best match
            best_shift = min(
                valid_shifts,
                key=lambda s: abs(
                    util.ensure_aware_datetime(datetime.combine(s.date, s.start_time))
                    - localtime(activity.login_time)
                ),
            )

            # If best shift is one with an existing exception WITH NO ACTIVITY -> set to current exsiting_exception (ensures exception gets updated)
            best_shift_exception = getattr(best_shift, "shift_shiftexception", None)
            if (
                not existing_exception
                and best_shift_exception
                and not best_shift_exception.activity
            ):
                existing_exception = best_shift_exception

            # If it already has a related exception
            if existing_exception:
                updated = False

                # If it doesnt have a shift related to exception -> add best_shift
                if not existing_exception.shift:
                    existing_exception.shift = best_shift
                    updated = True

                # Check if the related shift has perfect clocking times
                if util.check_perfect_shift_activity_timings(
                    activity=activity, shift=existing_exception.shift
                ):
                    # If its an incomplete exception -> add the given activity to exception
                    if not existing_exception.activity:
                        existing_exception.activity = activity
                        updated = True

                    # If its unapproved -> automatically approve it
                    if not existing_exception.is_approved:
                        existing_exception.is_approved = True
                        updated = True
                        logger.info(
                            f"Automatically marked EXCEPTION ID {existing_exception.id} as APPROVED due to the activity being manually fixed."
                        )
                        logger.debug(
                            f"[UPDATE: SHIFTEXCEPTION (ID: {existing_exception.id})] Approved: NO → Yes"
                        )

                    if updated:
                        existing_exception.save()
                    return None, False

                else:
                    if updated:
                        existing_exception.save()
                    created = create_shiftexception_link(
                        activity=activity,
                        shift=existing_exception.shift,
                        reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
                    )
                    return ShiftException.Reason.INCORRECTLY_CLOCKED, created

            # Has no related exception -> using best_shift, check if it matches clocking times
            if not util.check_perfect_shift_activity_timings(
                activity=activity, shift=best_shift
            ):
                created = create_shiftexception_link(
                    activity=activity,
                    shift=best_shift,
                    reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
                )
                return ShiftException.Reason.INCORRECTLY_CLOCKED, created

            # Else, perfectly clocked all around -> no need to do anything
            return None, False

        elif shift:
            # Check for existing exception (use getattr as it throws errors if it doesnt exist)
            existing_exception = getattr(shift, "shift_shiftexception", None)

            # Get activities for same user/store/day (DONT FILTER DB LEVEL, as realistically at most 2 activities per user per day per store -> more work to filter on DB level)
            activities = Activity.objects.filter(
                store_id=shift.store_id,
                employee_id=shift.employee_id,
                login_time__date=shift.date,
            ).prefetch_related("activity_shiftexception")

            # Preload other shifts ONCE -> Used to check if activity is valid (doesnt already have a perfect match) -> AS PERFECT MATCHES ARENT ALWAYS LINKED TO AN EXCEPTION
            other_shifts = (
                Shift.objects.filter(
                    store_id=shift.store_id,
                    employee_id=shift.employee_id,
                    date=shift.date,
                    is_deleted=False,
                )
                .exclude(pk=shift.id)
                .prefetch_related("shift_shiftexception")
            )

            # Filter valid activities using preloaded shifts
            valid_activities = [
                a
                for a in activities
                if util.is_valid_linking_activity_candidate(
                    possible_activity=a,
                    existing_exception=existing_exception,
                    other_shifts=other_shifts,
                )
            ]

            # If no activities left, treat as MISSED_SHIFT
            if not valid_activities:
                created = create_shiftexception_link(
                    shift=shift, reason=ShiftException.Reason.MISSED_SHIFT
                )
                return ShiftException.Reason.MISSED_SHIFT, created

            # Pick the best match
            best_activity = min(
                valid_activities,
                key=lambda a: abs(
                    localtime(a.login_time)
                    - util.ensure_aware_datetime(
                        datetime.combine(shift.date, shift.start_time)
                    )
                ),
            )

            # If best activity is one with an existing exception WITH NO SHIFT -> set to current exsiting_exception (ensures exception gets updated)
            best_activity_exception = getattr(
                best_activity, "activity_shiftexception", None
            )
            if (
                not existing_exception
                and best_activity_exception
                and not best_activity_exception.activity
            ):
                existing_exception = best_activity_exception

            # If it already has a related exception
            if existing_exception:
                updated = False

                # If it doesnt have a shift related to exception -> add best_shift
                if not existing_exception.activity:
                    existing_exception.activity = best_activity
                    updated = True

                # Check if the related shift has perfect clocking times
                if util.check_perfect_shift_activity_timings(
                    shift=shift, activity=existing_exception.activity
                ):
                    # If its an incomplete exception -> add the given shift to exception
                    if not existing_exception.shift:
                        existing_exception.shift = shift
                        updated = True

                    # If its unapproved -> automatically approve it
                    if not existing_exception.is_approved:
                        existing_exception.is_approved = True
                        updated = True
                        logger.info(
                            f"Automatically marked EXCEPTION ID {existing_exception.id} as APPROVED due to the activity being manually fixed."
                        )
                        logger.debug(
                            f"[UPDATE: SHIFTEXCEPTION (ID: {existing_exception.id})] Approved: NO → Yes"
                        )

                    if updated:
                        existing_exception.save()
                    return None, False

                # Has non-perfect clocking times
                else:
                    if updated:
                        existing_exception.save()
                    created = create_shiftexception_link(
                        activity=existing_exception.activity,
                        shift=shift,
                        reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
                    )
                    return ShiftException.Reason.INCORRECTLY_CLOCKED, created

            # Has no related exception -> using best_shift, check if it matches clocking times
            if not util.check_perfect_shift_activity_timings(
                activity=best_activity, shift=shift
            ):
                created = create_shiftexception_link(
                    activity=best_activity,
                    shift=shift,
                    reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
                )
                return ShiftException.Reason.INCORRECTLY_CLOCKED, created

            # Else, perfectly clocked all around -> no need to do anything
            return None, False

        else:
            raise SyntaxError("Activity OR Shift object MUST BE PASSED.")


def create_shiftexception_link(
    reason: ShiftException.Reason,
    activity: Union[Activity, None] = None,
    shift: Union[Shift, None] = None,
) -> bool:
    """
    Create a ShiftException based on an activity and/or shift

    Args:
        activity (Activity, None): The activity object to link.
        shift (shift, None): The shift object to link.

    Returns:
        bool: Whether or not a ShiftException was created

    Raises:
        SyntaxError: If neither activity or shift is provided.
    """
    if not activity and not shift:
        raise SyntaxError("Cannot pass both activity and shift object.")

    # Check an exception doesnt already exist
    if activity:
        try:
            excep = ShiftException.objects.get(activity=activity)
            excep.is_approved = False
            excep.reason = reason

            # Check that BOTH ACTIVITY AND SHIFT are assigned IF given both
            if shift:
                excep.shift = shift

            excep.save()
            return False
        except ShiftException.DoesNotExist:
            pass

    # Check BOTH if BOTH given (prevents violation of DB unique contraints)
    if shift:
        try:
            excep = ShiftException.objects.get(shift=shift)
            excep.is_approved = False
            excep.reason = reason

            # Check that BOTH ACTIVITY AND SHIFT are assigned IF given both
            if activity:
                excep.activity = activity

            excep.save()
            return False
        except ShiftException.DoesNotExist:
            pass

    # Create exception
    excep = ShiftException.objects.create(shift=shift, activity=activity, reason=reason)

    # Log it
    if activity:
        logger.info(
            f"Created an ShiftException with reason {reason.name} for employee ID {activity.employee_id} in the Store ID {activity.store_id}."
        )
    else:
        logger.info(
            f"Created an ShiftException with reason {reason.name} for employee ID {shift.employee_id} in the Store ID {shift.store_id}."
        )
    logger.debug(
        f"[CREATE: SHIFTEXCEPTION (ID: {excep.id})] Shift ID: {shift.id if shift else 'N/A'} -- Activity: {activity.id if activity else 'N/A'} -- Reason: {reason.upper()}"
    )
    return True


def copy_week_schedule(
    store: Store,
    source_week: datetime.date,
    target_week: datetime.date,
    override_shifts: bool = False,
    include_unscheduled: bool = False,
) -> Dict[str, int]:
    """
    Copy non-conflicting shifts from source week to target week.
    Optionally overrides existing shifts in the target week.

    Args:
        store (Store): Store instance
        source_week (datetime.date): Monday of the source week
        target_week (datetime.date): Monday of the target week
        override_shifts (bool): Whether to overwrite existing shifts on conflict
        include_unscheduled (bool): Whether to include unscheduled shifts in copy process.

    Returns:
        Dict[str, int]: Counts of 'created', 'overridden', 'skipped', and 'total'
    """
    # Ensure dates are at the start of the week
    source_week = util.get_week_start(source_week)
    target_week = util.get_week_start(target_week)

    # Determine week ranges
    source_range = (source_week, source_week + timedelta(days=6))
    target_range = (target_week, target_week + timedelta(days=6))

    # Fetch shifts in source week
    source_shifts = Shift.objects.filter(
        store_id=store.id,
        is_deleted=False,
        is_unscheduled=include_unscheduled,
        date__range=source_range,
    )

    # Prefetch all target week shifts, grouped by (employee_id, date) -> Faster collision checking instead of DB queries
    target_shifts = Shift.objects.filter(store_id=store.id, date__range=target_range)

    shift_map = defaultdict(list)
    for s in target_shifts:
        shift_map[(s.employee_id, s.date)].append(s)

    count_created = 0
    count_updated = 0
    count_skipped = 0
    new_shifts = []

    for src_shift in source_shifts:
        dest_date = target_week + timedelta(days=(src_shift.date - source_week).days)
        shift_start = src_shift.start_time
        shift_end = src_shift.end_time
        existing_shifts = shift_map.get((src_shift.employee_id, dest_date), [])

        # Check for any overlaps (within gap threshold)
        colliding_shifts = [
            s
            for s in existing_shifts
            if util.schedule_copy_do_shifts_collide(
                datetime.combine(s.date, s.start_time),
                datetime.combine(s.date, s.end_time),
                datetime.combine(dest_date, shift_start),
                datetime.combine(dest_date, shift_end),
            )
        ]

        if colliding_shifts:
            if override_shifts:
                # Hard delete colliding shifts
                Shift.objects.filter(id__in=[s.id for s in colliding_shifts]).delete()

                # Create new shift
                new_shifts.append(
                    Shift(
                        store=store,
                        employee=src_shift.employee,
                        role=src_shift.role,
                        date=dest_date,
                        start_time=shift_start,
                        end_time=shift_end,
                    )
                )
                count_updated += 1
            else:
                count_skipped += 1
        else:
            new_shifts.append(
                Shift(
                    store=store,
                    employee=src_shift.employee,
                    role=src_shift.role,
                    date=dest_date,
                    start_time=shift_start,
                    end_time=shift_end,
                )
            )
            count_created += 1

    try:
        with transaction.atomic():
            if new_shifts:
                Shift.objects.bulk_create(new_shifts)

    except IntegrityError as e:
        logger.error(
            f"IntegrityError occurred during week copy from {source_week} -> {target_week} [Override: {'YES' if override_shifts else 'NO'}]: {e}"
        )
        raise e

    return {
        "created": count_created,
        "updated": count_updated,
        "skipped": count_skipped,
        "total": count_created + count_updated + count_skipped,
    }
