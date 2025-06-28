import logging
import api.exceptions as err
import api.utils as util

from collections import defaultdict
from datetime import timedelta, datetime, date, time
from typing import Union, Dict, List, Dict, Tuple, Union, Any
from datetime import timedelta, datetime
from django.db import transaction, IntegrityError
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

            elif employee.has_activity_on_date(store=store, date=time.date()):
                raise err.AlreadyWorkedTodayError

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


def get_all_store_schedules(
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
        store=store, date__range=(week_start, week_end)
    ).select_related("employee", "role")

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

    # Order the shifts
    shifts = shifts.order_by(
        "date", "start_time", "employee__first_name", "employee__last_name"
    )

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
            info.update(
                {
                    "shift_start": obj.shift.start_time,
                    "shift_end": obj.shift.end_time,
                    "shift_role_name": obj.shift.role.name if obj.shift.role else None,
                    "shift_role_id": obj.shift.role.id if obj.shift.role else None,
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
                    "act_length_hr": round(obj.activity.shift_length_mins / 60, 1),
                    "act_pub_hol": obj.activity.is_public_holiday,
                }
            )

        results.append(info)

    return results, total


def approve_exception(
    exception: Union[ShiftException, int, str],
    override_role_id: Union[str, int, None] = None,
) -> None:
    """
    Approves an exception and updates both the linked shift and/or activity when required.
    ENSURE THE ROLE ID IS ACCESSIBLE BY THE RELATED STORE BEFORE CALLING THIS FUNCTION, THIS IS NOT CHECKED IN THIS CONTROLLER.

    Args:
        exception (Union[ShiftException, int, str]): The exception to approve.
        override_role_id (Union[str, int, None]): The ID of the role to override the connected shift with. BE WARNED: THIS IS NOT CHECKED IF A STORE HAS ACCESS TO THE ROLE, THIS IS DONE IN THE API VIEW ITSELF.

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

            # Ensure shift times match activity times
            updated = False
            if shift.start_time != activity.login_time.time():
                shift.start_time = localtime(activity.login_time).time()
                updated = True
            if shift.end_time != activity.logout_time.time():
                shift.end_time = localtime(activity.logout_time).time()
                updated = True

            # Only update role if its given AND it changes
            if override_role_id and shift.role != role:
                shift.role = role
                updated = True

            if updated:
                shift.save()

        # When user clocked in without being rostered -> create shift (ShiftException.Reason.NO_SHIFT)
        elif not shift and activity:
            if not activity.login_time or not activity.logout_time:
                raise err.IncompleteActivityError

            new_shift = Shift.objects.create(
                employee=activity.employee,
                store=activity.store,
                date=localtime(activity.login_time).date(),
                start_time=localtime(activity.login_time).time(),
                end_time=localtime(activity.logout_time).time(),
            )

            # Update role if given
            if override_role_id:
                new_shift.role = role
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
) -> Union[ShiftException.Reason, None]:
    """
    Check for a perfect link between an activity (actual shift) and a shift (the roster for the shift).
    If no perfect link exists (i.e. either doesnt exist, or slightly wrong) then create a ShiftException. Either option MUST be provided.

    Args:
        activity (Activity, int, str): The activity object or ID to start the link from.
        shift (shift, int, str): The shift object or ID to start the link from.

    Returns:
        Union[ShiftException.Reason, None]: The exception reason if one is created OR None if a perfect link exists.

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

    # NOTE: There is ONLY 1 of shift/activity PER DAY, so no need to check through multiple a day for a user for a certain store

    # Given ACTIVITY -> look for the shift
    if activity:
        # Check activity is FINISHED
        if not activity.logout_time:
            raise err.IncompleteActivityError

        shifts = Shift.objects.filter(
            store_id=activity.store_id,
            employee_id=activity.employee_id,
            date=activity.login_time.date(),
            is_deleted=False,
        )

        if len(shifts) > 1:
            logger.critical(
                f"Found {len(shifts)} linked SHIFTS to ACTIVITY ID {activity.id}. This should not be possible and has caused an error when checking for exceptions."
            )
            raise Exception(
                "More than 1 shift was found when trying to link an activity."
            )

        # Worked with no scheduled shift
        elif len(shifts) == 0:
            create_shiftexception_link(
                activity=activity, reason=ShiftException.Reason.NO_SHIFT
            )
            return ShiftException.Reason.NO_SHIFT

        elif not check_perfect_shift_activity_timings(
            activity=activity, shift=shifts[0]
        ):
            create_shiftexception_link(
                activity=activity,
                shift=shifts[0],
                reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
            )
            return ShiftException.Reason.INCORRECTLY_CLOCKED

        # Check for existing exceptions (update it to be approved since its a PERFECT LINK)
        try:
            excep = ShiftException.objects.get(activity=activity)
            if not excep.is_approved:
                excep.is_approved = True
                if not excep.shift:
                    excep.shift = shifts[0]
                excep.save()
                logger.info(
                    f"Automatically marked EXCEPTION ID {excep.id} as APPROVED due to the activity being manually fixed."
                )
        except ShiftException.DoesNotExist:
            pass

        return None

    # Given SHIFT -> look for the activity
    elif shift:
        activities = Activity.objects.filter(
            store_id=shift.store_id,
            employee_id=shift.employee_id,
            login_time__date=shift.date,
        )

        if len(activities) > 1:
            logger.critical(
                f"Found {len(activities)} linked ACTIVITIES to SHIFT ID {shift.id}. This should not be possible and has caused an error when checking for exceptions."
            )
            raise Exception(
                "More than 1 activity was found when trying to link a shift."
            )

        # Had a rostered Shift but did not work
        elif len(activities) == 0:
            create_shiftexception_link(
                shift=shift, reason=ShiftException.Reason.MISSED_SHIFT
            )
            return ShiftException.Reason.MISSED_SHIFT

        # Check activity is FINISHED
        elif not activities[0].logout_time:
            raise err.IncompleteActivityError

        elif not check_perfect_shift_activity_timings(
            activity=activities[0], shift=shift
        ):
            create_shiftexception_link(
                shift=shift,
                activity=activities[0],
                reason=ShiftException.Reason.INCORRECTLY_CLOCKED,
            )
            return ShiftException.Reason.INCORRECTLY_CLOCKED

        # Check for existing exceptions (update it to be approved since its a PERFECT LINK)
        try:
            excep = ShiftException.objects.get(shift=shift)
            if not excep.is_approved:
                excep.is_approved = True
                if not excep.activity:
                    excep.activity = activities[0]
                excep.save()
                logger.info(
                    f"Automatically marked EXCEPTION ID {excep.id} as APPROVED due to the activity being manually fixed."
                )
        except ShiftException.DoesNotExist:
            pass

        return None

    else:
        raise SyntaxError("Activity OR Shift object MUST BE PASSED.")


def check_perfect_shift_activity_timings(activity: Activity, shift: Shift) -> bool:
    """
    Check if the provided activity and shift are perfectly matched in terms of timings of clocking in/out. (Rounded of course)

    Args:
        activity (Activity): The activity object to compare.
        shift (Shift): The shift object to compare.

    Returns:
        bool: If there exists a perfect link between the two. If either is slightly off then it returns False.
    """
    # If activity is not finished -> IGNORE
    if not activity.logout_time:
        return True

    # Check start time matches (use rounded login_time)
    if shift.start_time != activity.login_time.time():
        return False

    # Check end time matches (use rounded logout_time)
    elif shift.end_time != activity.logout_time.time():
        return False

    return True


def create_shiftexception_link(
    reason: ShiftException.Reason,
    activity: Union[Activity, None] = None,
    shift: Union[Shift, None] = None,
):
    """
    Create a ShiftException based on an activity and/or shift

    Args:
        activity (Activity, None): The activity object to link.
        shift (shift, None): The shift object to link.

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
            excep.save()
            return
        except ShiftException.DoesNotExist:
            pass

    elif shift:
        try:
            excep = ShiftException.objects.get(shift=shift)
            excep.is_approved = False
            excep.reason = reason
            excep.save()
            return
        except ShiftException.DoesNotExist:
            pass

    # Create exception
    ShiftException.objects.create(shift=shift, activity=activity, reason=reason)

    # Log it
    logger.info(
        f"Created an ShiftException with reason {reason.name} for employee ID {activity.employee_id} in the Store ID {activity.store_id}."
    )
    return


def copy_week_schedule(
    store: Store,
    source_week: datetime.date,
    target_week: datetime.date,
    override_shifts: bool = False,
) -> Dict[str, int]:
    """
    Copy non-conflicting shifts from source week to target week.
    Optionally overrides existing shifts in the target week.

    Args:
        store (Store): Store instance
        source_week (datetime.date): Monday of the source week
        target_week (datetime.date): Monday of the target week
        override_shifts (bool): Whether to overwrite existing shifts on conflict

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
    source_shifts = Shift.objects.filter(store_id=store.id, date__range=source_range)

    # Prefetch existing shifts in the target week for faster conflict checking
    target_shifts = Shift.objects.filter(store_id=store.id, date__range=target_range)

    # Index by employee, date
    existing_shifts_map = {(s.employee_id, s.date): s for s in target_shifts}

    count_created = 0
    count_updated = 0
    count_skipped = 0
    new_shifts = []
    shifts_to_override = []

    # Go through every shift in the source week and copy them (if required)
    for src_shift in source_shifts:
        destination_date = target_week + timedelta(
            days=(src_shift.date - source_week).days
        )

        # Check for conflicts
        key = (src_shift.employee_id, destination_date)
        conflict = key in existing_shifts_map

        if conflict:
            if override_shifts:
                target_shift = existing_shifts_map[key]
                if (
                    target_shift.start_time != src_shift.start_time
                    or target_shift.end_time != src_shift.end_time
                    or target_shift.role_id != src_shift.role_id
                ):
                    target_shift.start_time = src_shift.start_time
                    target_shift.end_time = src_shift.end_time
                    target_shift.role = src_shift.role
                    shifts_to_override.append(target_shift)
                    count_updated += 1
                else:
                    # Unchanged -> Ignore
                    count_skipped += 1
            else:
                # Override disabled -> Ignore
                count_skipped += 1

        else:
            new_shifts.append(
                Shift(
                    store=store,
                    employee=src_shift.employee,
                    role=src_shift.role,
                    date=destination_date,
                    start_time=src_shift.start_time,
                    end_time=src_shift.end_time,
                )
            )
            count_created += 1

    try:
        with transaction.atomic():
            if new_shifts:
                Shift.objects.bulk_create(new_shifts)

            if shifts_to_override:
                Shift.objects.bulk_update(
                    shifts_to_override, ["start_time", "end_time", "role"]
                )

    except IntegrityError as e:
        logger.error(
            f"IntegrityError occured when trying to copy shifts {source_week} -> {target_week} [override: {'YES' if override_shifts else 'NO'}]: {e}"
        )
        raise e

    return {
        "created": count_created,
        "updated": count_updated,
        "skipped": count_skipped,
        "total": count_created + count_updated + count_skipped,
    }
